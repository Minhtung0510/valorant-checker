from __future__ import annotations

import asyncio
import concurrent.futures
import html
import json
import logging
import os
import queue
import threading
import tkinter as tk
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import requests

from app_runtime import app_data_dir, executable_dir
from license_core import get_machine_id
from license_store import activate_license, clear_license, load_valid_license


DATA_DIR = app_data_dir()
os.environ.setdefault("LOG_DIR", str(DATA_DIR / "logs"))

import main as checker  # noqa: E402


BG = "#0f1923"
PANEL = "#182431"
PANEL_DARK = "#0d1520"
TEXT = "#ece8e1"
MUTED = "#8b978f"
ACCENT = "#ff4655"
SUCCESS = "#4caf50"
WARNING = "#ffb74d"
BORDER = "#243447"
CARD = "#14202c"
INPUT = "#0a111c"
DANGER = "#ef5350"
BLUE = "#40c4ff"

SETTINGS_PATH = DATA_DIR / "settings.json"


class GuiLogHandler(logging.Handler):
    def __init__(self, event_queue: queue.Queue):
        super().__init__()
        self.event_queue = event_queue

    def emit(self, record: logging.LogRecord) -> None:
        self.event_queue.put(("log", self.format(record)))


class ValorantCheckerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Valorant Checker")
        self.root.geometry("1120x780")
        self.root.minsize(980, 680)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.event_queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.report_path: Path | None = None
        self.license = None

        self.accounts_var = tk.StringVar()
        self.proxies_var = tk.StringVar()
        self.browser_var = tk.StringVar(value=self._default_browser_path())
        self.extension_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(Path.home() / "Desktop" / "Check-done"))
        self.concurrency_var = tk.IntVar(value=2)
        self.accounts_count_var = tk.StringVar(value="Chưa import")
        self.proxies_count_var = tk.StringVar(value="Chưa import")
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_text_var = tk.StringVar(value="0 / 0")
        self.run_status_var = tk.StringVar(value="Sẵn sàng")
        self.progress_canvas: tk.Canvas | None = None
        self.progress_fill: int | None = None
        self.result_canvas: tk.Canvas | None = None
        self.result_rows_frame: tk.Frame | None = None
        self.result_header_vars: list[tk.StringVar] = []
        self.total_stat_var = tk.StringVar(value="0")
        self.active_stat_var = tk.StringVar(value="0")
        self.banned_stat_var = tk.StringVar(value="0")
        self.error_stat_var = tk.StringVar(value="0")
        self.result_counts = {"total": 0, "active": 0, "banned": 0, "error": 0}
        self.result_row_count = 0

        self._configure_styles()
        self._load_settings()
        self.root.after(100, self._initial_route)
        self.root.after(100, self._process_events)

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Title.TLabel", background=BG, foreground=ACCENT, font=("Segoe UI Semibold", 24))
        style.configure("PanelTitle.TLabel", background=PANEL, foreground=ACCENT, font=("Segoe UI Semibold", 24))
        style.configure("Section.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI Semibold", 12))
        style.configure("Accent.TButton", background=ACCENT, foreground="white", padding=(16, 10))
        style.map("Accent.TButton", background=[("active", "#d83a49"), ("disabled", "#5a343c")])
        style.configure("Success.TButton", background=SUCCESS, foreground="white", padding=(16, 10))
        style.map("Success.TButton", background=[("active", "#388e3c"), ("disabled", "#36533a")])
        style.configure("TButton", padding=(12, 8))
        style.configure("TEntry", fieldbackground=PANEL_DARK, foreground=TEXT, insertcolor=TEXT)
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=PANEL_DARK, bordercolor=PANEL_DARK)

    @staticmethod
    def _tk_label(parent, text="", fg=TEXT, bg=None, font=None, **kwargs) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=bg or parent.cget("bg"),
            fg=fg,
            font=font or ("Segoe UI", 10),
            anchor="w",
            **kwargs,
        )

    @staticmethod
    def _card(parent, **kwargs) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=CARD,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            highlightthickness=1,
            bd=0,
            **kwargs,
        )

    @staticmethod
    def _entry(parent, variable: tk.StringVar, readonly: bool = False) -> tk.Entry:
        entry = tk.Entry(
            parent,
            textvariable=variable,
            bg=INPUT,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground="#2a3a4a",
            highlightcolor=ACCENT,
            readonlybackground=INPUT,
            disabledbackground=INPUT,
            disabledforeground=MUTED,
            font=("Segoe UI", 10),
        )
        if readonly:
            entry.configure(state="readonly")
        return entry

    @staticmethod
    def _button(parent, text: str, command=None, variant: str = "secondary", width: int | None = None) -> tk.Button:
        palette = {
            "primary": (ACCENT, "#ff6674", "white"),
            "success": (SUCCESS, "#5bc85f", "white"),
            "secondary": ("#223244", "#2b4058", TEXT),
            "ghost": (CARD, "#1d2b3a", MUTED),
            "danger": (DANGER, "#ff6b6b", "white"),
        }
        bg, active_bg, fg = palette.get(variant, palette["secondary"])
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            disabledforeground="#667382",
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
        )

    @staticmethod
    def _default_browser_path() -> str:
        candidates = [
            executable_dir() / "browser" / "orbita-browser-145" / "chrome.exe",
            Path.home() / "Downloads" / "Gologin" / "All-Browsers" / "orbita-browser-145" / "chrome.exe",
            Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "GoLogin" / "orbita-browser" / "chrome.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return str(candidates[0])

    def _load_settings(self) -> None:
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.accounts_var.set(settings.get("accounts_file", ""))
        self.proxies_var.set(settings.get("proxies_file", ""))
        self.browser_var.set(settings.get("browser_path", self.browser_var.get()))
        self.extension_var.set(settings.get("extension_path", ""))
        self.output_var.set(settings.get("output_dir", self.output_var.get()))
        self.concurrency_var.set(int(settings.get("concurrency", 2)))

    def _save_settings(self) -> None:
        value = {
            "accounts_file": self.accounts_var.get(),
            "proxies_file": self.proxies_var.get(),
            "browser_path": self.browser_var.get(),
            "extension_path": self.extension_var.get(),
            "output_dir": self.output_var.get(),
            "concurrency": int(self.concurrency_var.get()),
        }
        temp_path = SETTINGS_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temp_path.replace(SETTINGS_PATH)

    def _clear_root(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()

    def _initial_route(self) -> None:
        stored, _message = load_valid_license()
        if stored:
            self.license = stored
            self.show_main_screen()
        else:
            self.show_license_screen()

    def show_license_screen(self) -> None:
        self._clear_root()
        frame = tk.Frame(self.root, bg=BG, padx=36, pady=36)
        frame.pack(fill="both", expand=True)

        center = self._card(frame)
        center.place(relx=0.5, rely=0.5, anchor="center", width=700, height=470)
        inner = tk.Frame(center, bg=CARD, padx=32, pady=32)
        inner.pack(fill="both", expand=True)

        self._tk_label(
            inner,
            "VALORANT CHECKER",
            fg=ACCENT,
            bg=CARD,
            font=("Segoe UI Semibold", 25),
        ).pack(anchor="w")
        self._tk_label(
            inner,
            text="Kích hoạt license để sử dụng ứng dụng",
            fg=MUTED,
            bg=CARD,
        ).pack(anchor="w", pady=(4, 26))

        self._tk_label(inner, "Machine ID", bg=CARD, font=("Segoe UI Semibold", 10)).pack(anchor="w")
        machine_row = tk.Frame(inner, bg=CARD)
        machine_row.pack(fill="x", pady=(7, 18))
        machine_var = tk.StringVar(value=get_machine_id())
        self._entry(machine_row, machine_var, readonly=True).pack(side="left", fill="x", expand=True, ipady=9)

        def copy_machine() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(machine_var.get())
            status_var.set("Đã copy Machine ID")

        self._button(machine_row, "Copy", copy_machine, "secondary").pack(side="left", padx=(8, 0))

        self._tk_label(inner, "License key", bg=CARD, font=("Segoe UI Semibold", 10)).pack(anchor="w")
        key_text = tk.Text(
            inner,
            height=6,
            wrap="word",
            bg=INPUT,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            padx=10,
            pady=10,
            font=("Consolas", 9),
        )
        key_text.pack(fill="x", pady=(7, 14))
        status_var = tk.StringVar(value="Nhập key do admin cung cấp")
        status_label = tk.Label(inner, textvariable=status_var, bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        status_label.pack(anchor="w")

        def activate() -> None:
            validation = activate_license(key_text.get("1.0", "end").strip())
            if not validation.valid:
                status_label.configure(fg=ACCENT)
                status_var.set(validation.message)
                return
            stored, message = load_valid_license()
            if not stored:
                status_label.configure(fg=ACCENT)
                status_var.set(message)
                return
            self.license = stored
            self.show_main_screen()

        self._button(inner, "Kích hoạt", activate, "primary").pack(anchor="w", pady=(20, 0))

    def show_main_screen(self) -> None:
        self._clear_root()
        outer = tk.Frame(self.root, bg=BG, padx=24, pady=22)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", pady=(0, 14))
        title_block = tk.Frame(header, bg=BG)
        title_block.pack(side="left", fill="x", expand=True)
        self._tk_label(
            title_block,
            "VALORANT CHECKER",
            fg=ACCENT,
            bg=BG,
            font=("Segoe UI Semibold", 28),
        ).pack(anchor="w")
        self._tk_label(
            title_block,
            "Desktop checker • license gated • ephemeral browser profiles",
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(2, 0))

        license_text = "License"
        if self.license:
            license_text = f"{self.license.claims.customer}  |  Hết hạn: {self.license.expiry_text}"
        right_header = tk.Frame(header, bg=BG)
        right_header.pack(side="right")
        tk.Label(
            right_header,
            text=license_text,
            bg="#111d29",
            fg=MUTED,
            padx=14,
            pady=8,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 10))
        self._button(right_header, "Đăng xuất key", self.logout_license, "ghost").pack(side="left")

        config = self._card(outer)
        config.pack(fill="x", pady=(0, 14))
        config_inner = tk.Frame(config, bg=CARD, padx=18, pady=18)
        config_inner.pack(fill="x")
        config_inner.columnconfigure(1, weight=1)
        config_inner.columnconfigure(4, weight=1)

        self._path_row(config_inner, 0, 0, "Accounts TXT", self.accounts_var, self.choose_accounts, self.accounts_count_var)
        self._path_row(config_inner, 1, 0, "Proxies TXT", self.proxies_var, self.choose_proxies, self.proxies_count_var)
        self._path_row(config_inner, 0, 3, "Orbita chrome.exe", self.browser_var, self.choose_browser)
        self._path_row(config_inner, 1, 3, "Thư mục output", self.output_var, self.choose_output)
        self._path_row(config_inner, 2, 3, "OMO extension", self.extension_var, self.choose_extension)

        self._tk_label(config_inner, "Concurrency", bg=CARD, fg=MUTED, font=("Segoe UI Semibold", 9)).grid(
            row=2, column=0, sticky="w", pady=(12, 0), padx=(0, 10)
        )
        conc_row = tk.Frame(config_inner, bg=CARD)
        conc_row.grid(row=2, column=1, sticky="w", pady=(12, 0))
        self._button(conc_row, "-", lambda: self._change_concurrency(-1), "secondary", width=3).pack(side="left")
        tk.Label(
            conc_row,
            textvariable=self.concurrency_var,
            bg=INPUT,
            fg=TEXT,
            width=4,
            padx=10,
            pady=9,
            font=("Segoe UI Semibold", 10),
        ).pack(side="left", padx=6)
        self._button(conc_row, "+", lambda: self._change_concurrency(1), "secondary", width=3).pack(side="left")

        controls = tk.Frame(config_inner, bg=CARD)
        controls.grid(row=3, column=3, columnspan=3, sticky="e", pady=(12, 0))
        self.start_button = self._button(controls, "Bắt đầu", self.start_run, "success", width=12)
        self.start_button.pack(side="left")
        self.proxy_button = self._button(controls, "Check Proxy", self.start_proxy_check, "primary", width=12)
        self.proxy_button.pack(side="left", padx=(8, 0))
        self.stop_button = self._button(controls, "Dừng", self.stop_run, "danger", width=10)
        self.stop_button.configure(state="disabled")
        self.stop_button.pack(side="left", padx=8)
        self.report_button = self._button(controls, "Mở HTML", self.open_report, "secondary", width=11)
        self.report_button.configure(state="disabled")
        self.report_button.pack(side="left")

        stats_row = tk.Frame(outer, bg=BG)
        stats_row.pack(fill="x", pady=(0, 14))
        self._stat_card(stats_row, "TOTAL", self.total_stat_var, BLUE).pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._stat_card(stats_row, "ACTIVE", self.active_stat_var, SUCCESS).pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._stat_card(stats_row, "BAD", self.banned_stat_var, DANGER).pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._stat_card(stats_row, "ERROR", self.error_stat_var, WARNING).pack(side="left", fill="x", expand=True)

        progress_card = self._card(outer)
        progress_card.pack(fill="x", pady=(0, 14))
        progress_inner = tk.Frame(progress_card, bg=CARD, padx=14, pady=12)
        progress_inner.pack(fill="x")
        progress_row = tk.Frame(progress_inner, bg=CARD)
        progress_row.pack(fill="x", pady=(0, 9))
        self._tk_label(progress_row, textvariable=self.run_status_var, bg=CARD, font=("Segoe UI Semibold", 10)).pack(side="left")
        self._tk_label(progress_row, textvariable=self.progress_text_var, fg=MUTED, bg=CARD, font=("Segoe UI", 9)).pack(side="right")
        self.progress_canvas = tk.Canvas(progress_inner, height=12, bg=INPUT, highlightthickness=0)
        self.progress_canvas.pack(fill="x")
        self.progress_fill = self.progress_canvas.create_rectangle(0, 0, 0, 12, fill=ACCENT, width=0)
        self.progress_canvas.bind("<Configure>", lambda _event: self._render_progress())

        content = tk.Frame(outer, bg=BG)
        content.pack(fill="both", expand=True)

        result_panel = self._card(content)
        result_panel.pack(fill="both", expand=True, pady=(0, 14))
        log_panel = self._card(content)
        log_panel.pack(fill="both", expand=False)

        result_inner = tk.Frame(result_panel, bg=CARD, padx=12, pady=12)
        result_inner.pack(fill="both", expand=True)
        top_result = tk.Frame(result_inner, bg=CARD)
        top_result.pack(fill="x", pady=(0, 8))
        self._tk_label(top_result, "Kết quả", bg=CARD, font=("Segoe UI Semibold", 11)).pack(side="left")
        self._tk_label(top_result, "Status cập nhật realtime theo từng account", fg=MUTED, bg=CARD, font=("Segoe UI", 9)).pack(side="right")

        self._build_result_table(result_inner)

        log_inner = tk.Frame(log_panel, bg=CARD, padx=12, pady=12)
        log_inner.pack(fill="both", expand=True)
        self._tk_label(log_inner, "Log", bg=CARD, font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 8))
        self.log_text = tk.Text(
            log_inner,
            height=5,
            bg=INPUT,
            fg="#c6d0d8",
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            padx=10,
            pady=10,
            font=("Cascadia Mono", 9),
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

        self._refresh_file_counts()
        self._attach_log_handler()

    def _path_row(
        self,
        parent,
        row: int,
        column: int,
        label: str,
        variable: tk.StringVar,
        command,
        count_var: tk.StringVar | None = None,
    ) -> None:
        self._tk_label(parent, label, fg=MUTED, bg=CARD, font=("Segoe UI Semibold", 9)).grid(
            row=row, column=column, sticky="w", padx=(0, 10), pady=7
        )
        entry_row = tk.Frame(parent, bg=CARD)
        entry_row.grid(row=row, column=column + 1, sticky="ew", pady=7)
        self._entry(entry_row, variable).pack(side="left", fill="x", expand=True, ipady=8)
        if count_var:
            tk.Label(
                entry_row,
                textvariable=count_var,
                bg=CARD,
                fg=MUTED,
                font=("Segoe UI", 9),
                padx=8,
            ).pack(side="left")
        self._button(parent, "Chọn", command, "secondary", width=8).grid(
            row=row, column=column + 2, padx=(8, 18), pady=7
        )

    def _stat_card(self, parent, label: str, value_var: tk.StringVar, color: str) -> tk.Frame:
        frame = self._card(parent)
        inner = tk.Frame(frame, bg=CARD, padx=16, pady=12)
        inner.pack(fill="x")
        tk.Label(inner, text=label, bg=CARD, fg=MUTED, font=("Segoe UI Semibold", 8)).pack(anchor="w")
        tk.Label(inner, textvariable=value_var, bg=CARD, fg=color, font=("Segoe UI Semibold", 20)).pack(anchor="w")
        return frame

    def _change_concurrency(self, delta: int) -> None:
        value = max(1, min(10, int(self.concurrency_var.get()) + delta))
        self.concurrency_var.set(value)

    def _build_result_table(self, parent: tk.Frame) -> None:
        table = tk.Frame(parent, bg=INPUT, highlightbackground=BORDER, highlightthickness=1, bd=0)
        table.pack(fill="both", expand=True)
        columns = [
            ("Account", 2),
            ("Status", 2),
            ("Skins", 1),
            ("Rank", 1),
            ("Region", 1),
            ("Thông tin", 3),
        ]

        header = tk.Frame(table, bg="#162432")
        header.pack(fill="x")
        self.result_header_vars = []
        for index, (title, weight) in enumerate(columns):
            header.columnconfigure(index, weight=weight, uniform="result_table")
            title_var = tk.StringVar(value=title)
            self.result_header_vars.append(title_var)
            tk.Label(
                header,
                textvariable=title_var,
                bg="#162432",
                fg=MUTED,
                padx=12,
                pady=9,
                font=("Segoe UI Semibold", 9),
                anchor="w",
            ).grid(row=0, column=index, sticky="ew")

        self.result_canvas = tk.Canvas(table, bg=INPUT, highlightthickness=0, bd=0)
        self.result_canvas.pack(fill="both", expand=True)
        self.result_rows_frame = tk.Frame(self.result_canvas, bg=INPUT)
        window_id = self.result_canvas.create_window((0, 0), window=self.result_rows_frame, anchor="nw")

        for index, (_title, weight) in enumerate(columns):
            self.result_rows_frame.columnconfigure(index, weight=weight, uniform="result_table")

        def sync_scrollregion(_event=None) -> None:
            if self.result_canvas:
                self.result_canvas.configure(scrollregion=self.result_canvas.bbox("all"))

        def sync_width(event) -> None:
            if self.result_canvas:
                self.result_canvas.itemconfigure(window_id, width=event.width)

        self.result_rows_frame.bind("<Configure>", sync_scrollregion)
        self.result_canvas.bind("<Configure>", sync_width)
        self.result_canvas.bind("<Enter>", lambda _event: self.result_canvas.bind_all("<MouseWheel>", self._on_result_mousewheel))
        self.result_canvas.bind("<Leave>", lambda _event: self.result_canvas.unbind_all("<MouseWheel>"))

    def _set_result_headers(self, titles: tuple[str, str, str, str, str, str]) -> None:
        for variable, title in zip(self.result_header_vars, titles):
            variable.set(title)

    def _on_result_mousewheel(self, event) -> None:
        if self.result_canvas:
            self.result_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _clear_result_rows(self) -> None:
        if not self.result_rows_frame:
            return
        for child in self.result_rows_frame.winfo_children():
            child.destroy()
        self.result_counts = {"total": 0, "active": 0, "banned": 0, "error": 0}
        self.result_row_count = 0
        self._sync_stats()

    def _sync_stats(self) -> None:
        self.total_stat_var.set(str(self.result_counts["total"]))
        self.active_stat_var.set(str(self.result_counts["active"]))
        self.banned_stat_var.set(str(self.result_counts["banned"]))
        self.error_stat_var.set(str(self.result_counts["error"]))

    def _append_table_row(self, values: list[str], tag: str) -> None:
        if not self.result_rows_frame:
            return
        row_index = self.result_row_count
        self.result_row_count += 1
        row_bg = "#0b1420" if row_index % 2 == 0 else "#0e1926"
        status_color = {
            "active": SUCCESS,
            "banned": DANGER,
            "error": WARNING,
        }.get(tag, MUTED)

        row = tk.Frame(self.result_rows_frame, bg=row_bg)
        row.grid(row=row_index, column=0, columnspan=6, sticky="ew")
        for index, weight in enumerate((2, 2, 1, 1, 1, 3)):
            row.columnconfigure(index, weight=weight, uniform="result_table")

        for index, value in enumerate(values):
            if index == 1:
                pill = tk.Label(
                    row,
                    text=value,
                    bg=status_color,
                    fg="white",
                    padx=10,
                    pady=3,
                    font=("Segoe UI Semibold", 8),
                    anchor="w",
                )
                pill.grid(row=0, column=index, sticky="w", padx=12, pady=7)
            else:
                tk.Label(
                    row,
                    text=value,
                    bg=row_bg,
                    fg=TEXT if index != 5 else "#c9d4df",
                    padx=12,
                    pady=10,
                    font=("Segoe UI", 9),
                    anchor="w",
                ).grid(row=0, column=index, sticky="ew")

        if self.result_canvas:
            self.result_canvas.update_idletasks()
            self.result_canvas.configure(scrollregion=self.result_canvas.bbox("all"))

    def _append_result_row(self, result: checker.Result, tag: str, rank: str, message: str) -> None:
        self._append_table_row(
            [
                result.username,
                result.status_label,
                str(result.skins_count),
                rank,
                result.region.upper(),
                message,
            ],
            tag,
        )

    def _set_progress(self, value: float) -> None:
        self.progress_var.set(max(0, min(100, value)))
        self._render_progress()

    def _render_progress(self) -> None:
        if not self.progress_canvas or self.progress_fill is None:
            return
        width = max(1, self.progress_canvas.winfo_width())
        height = max(1, self.progress_canvas.winfo_height())
        fill_width = width * (float(self.progress_var.get()) / 100)
        self.progress_canvas.coords(self.progress_fill, 0, 0, fill_width, height)

    def _attach_log_handler(self) -> None:
        for handler in checker.logger.handlers:
            if isinstance(handler, GuiLogHandler):
                return
        handler = GuiLogHandler(self.event_queue)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S"))
        checker.logger.addHandler(handler)

    def choose_accounts(self) -> None:
        path = filedialog.askopenfilename(title="Chọn accounts.txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.accounts_var.set(path)
            self._refresh_file_counts()

    def choose_proxies(self) -> None:
        path = filedialog.askopenfilename(title="Chọn proxies.txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.proxies_var.set(path)
            self._refresh_file_counts()

    def choose_browser(self) -> None:
        path = filedialog.askopenfilename(title="Chọn Orbita chrome.exe", filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            self.browser_var.set(path)

    def choose_extension(self) -> None:
        path = filedialog.askdirectory(title="Chọn thư mục extension có manifest.json")
        if path:
            self.extension_var.set(path)

    def choose_output(self) -> None:
        path = filedialog.askdirectory(title="Chọn thư mục output")
        if path:
            self.output_var.set(path)

    def _refresh_file_counts(self) -> None:
        accounts_path = Path(self.accounts_var.get()) if self.accounts_var.get() else None
        proxies_path = Path(self.proxies_var.get()) if self.proxies_var.get() else None
        accounts = checker.load_accounts(accounts_path) if accounts_path and accounts_path.exists() else []
        proxies = checker.load_proxies(proxies_path) if proxies_path and proxies_path.exists() else []
        self.accounts_count_var.set(f"{len(accounts)} account" if accounts_path else "Chưa import")
        self.proxies_count_var.set(f"{len(proxies)} proxy" if proxies_path else "Chưa import")

    def _validate_run(self) -> bool:
        stored, message = load_valid_license()
        if not stored:
            messagebox.showerror("License", message)
            self.show_license_screen()
            return False

        accounts_path = Path(self.accounts_var.get())
        browser_path = Path(self.browser_var.get())
        if not accounts_path.is_file():
            messagebox.showwarning("Thiếu account", "Hãy import file accounts.txt.")
            return False
        if not checker.load_accounts(accounts_path):
            messagebox.showwarning("Sai định dạng", "File account không có dòng hợp lệ dạng username:password.")
            return False
        if not browser_path.is_file():
            messagebox.showwarning("Thiếu Orbita", "Không tìm thấy file Orbita chrome.exe.")
            return False
        if self.extension_var.get():
            extension_path = Path(self.extension_var.get())
            if not extension_path.is_dir() or not (extension_path / "manifest.json").is_file():
                messagebox.showwarning(
                    "Sai extension",
                    "Hãy chọn thư mục extension đã giải nén và có file manifest.json.",
                )
                return False
        if self.proxies_var.get() and not Path(self.proxies_var.get()).is_file():
            messagebox.showwarning("Sai file proxy", "File proxy đã chọn không tồn tại.")
            return False
        return True

    def _validate_proxy_check(self) -> bool:
        stored, message = load_valid_license()
        if not stored:
            messagebox.showerror("License", message)
            self.show_license_screen()
            return False

        if not self.proxies_var.get():
            messagebox.showwarning("Thiếu proxy", "Hãy import file proxies.txt trước.")
            return False

        proxies_path = Path(self.proxies_var.get())
        if not proxies_path.is_file():
            messagebox.showwarning("Sai file proxy", "File proxy đã chọn không tồn tại.")
            return False

        if not checker.load_proxies(proxies_path):
            messagebox.showwarning("Không có proxy", "File proxy không có dòng hợp lệ dạng ip:port:user:password hoặc ip:port.")
            return False

        return True

    def start_run(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self._validate_run():
            return

        self._save_settings()
        self.cancel_event = threading.Event()
        self.report_path = None
        self._set_progress(0)
        self.progress_text_var.set("0 / 0")
        self.run_status_var.set("Đang khởi tạo...")
        self.start_button.configure(state="disabled")
        self.proxy_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.report_button.configure(state="disabled")
        self._clear_result_rows()
        self._set_result_headers(("Account", "Status", "Skins", "Rank", "Region", "Info"))

        accounts_file = Path(self.accounts_var.get())
        account_total = len(checker.load_accounts(accounts_file))
        self.result_counts["total"] = account_total
        self.total_stat_var.set(str(account_total))
        proxies_file = Path(self.proxies_var.get()) if self.proxies_var.get() else DATA_DIR / "empty_proxies.txt"
        if not proxies_file.exists():
            proxies_file.write_text("", encoding="utf-8")
        output_dir = Path(self.output_var.get())
        browser_path = Path(self.browser_var.get())
        extension_path = Path(self.extension_var.get()) if self.extension_var.get() else None
        concurrency = int(self.concurrency_var.get())

        def progress(result: checker.Result, done: int, total: int) -> None:
            self.event_queue.put(("result", result, done, total))

        def worker() -> None:
            try:
                summary = asyncio.run(
                    checker.run_checker(
                        accounts_file=accounts_file,
                        proxies_file=proxies_file,
                        output_dir=output_dir,
                        concurrency=concurrency,
                        browser_path=browser_path,
                        extension_path=extension_path,
                        progress_callback=progress,
                        cancel_event=self.cancel_event,
                    )
                )
                self.event_queue.put(("finished", summary))
            except Exception as exc:
                self.event_queue.put(("fatal", str(exc)))

        self.worker = threading.Thread(target=worker, name="checker-worker", daemon=True)
        self.worker.start()

    @staticmethod
    def _proxy_to_line(proxy: checker.ProxyInfo) -> str:
        if proxy.username or proxy.password:
            return f"{proxy.host}:{proxy.port}:{proxy.username}:{proxy.password}"
        return f"{proxy.host}:{proxy.port}"

    @staticmethod
    def _check_one_proxy(proxy: checker.ProxyInfo, timeout: float = 12.0) -> dict:
        proxy_line = ValorantCheckerApp._proxy_to_line(proxy)
        started = time.perf_counter()
        proxies = {"http": proxy.http_url, "https": proxy.http_url}
        headers = {"User-Agent": "Mozilla/5.0 ValorantChecker/1.0"}
        session = requests.Session()
        session.trust_env = False

        failures: list[str] = []
        connectivity_targets = (
            ("Riot HTTPS", "https://auth.riotgames.com/authorize"),
            ("Google HTTPS", "https://www.google.com/generate_204"),
        )
        per_request_timeout = max(3.0, min(6.0, timeout / 2))

        for label, url in connectivity_targets:
            try:
                response = session.get(
                    url,
                    proxies=proxies,
                    timeout=per_request_timeout,
                    headers=headers,
                    allow_redirects=False,
                )
                if response.status_code != 407 and response.status_code < 500:
                    ip = ""
                    try:
                        ip_response = session.get(
                            "https://icanhazip.com/",
                            proxies=proxies,
                            timeout=3.0,
                            headers=headers,
                        )
                        if ip_response.ok:
                            ip = ip_response.text.strip()[:64]
                    except requests.RequestException:
                        pass

                    return {
                        "ok": True,
                        "proxy": proxy_line,
                        "server": proxy.server,
                        "latency_ms": int((time.perf_counter() - started) * 1000),
                        "ip": ip,
                        "check": f"{label} ({response.status_code})",
                        "error": "",
                    }
                failures.append(f"{label}: HTTP {response.status_code}")
            except requests.RequestException as exc:
                reason = exc.__class__.__name__
                failures.append(f"{label}: {reason}")

        return {
            "ok": False,
            "proxy": proxy_line,
            "server": proxy.server,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "ip": "",
            "check": "",
            "error": "; ".join(failures)[:160] or "No response",
        }

    @staticmethod
    def _write_proxy_report(output_dir: Path, results: list[dict]) -> Path:
        ts = datetime.now().strftime("%d%m%Y_%H%M%S")
        run_dir = output_dir / f"proxy_check_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)

        live = [r for r in results if r["ok"]]
        dead = [r for r in results if not r["ok"]]
        (run_dir / "live_proxies.txt").write_text("\n".join(r["proxy"] for r in live), encoding="utf-8")
        (run_dir / "dead_proxies.txt").write_text("\n".join(r["proxy"] for r in dead), encoding="utf-8")

        rows = "\n".join(
            f"<tr><td>{html.escape(r['proxy'])}</td><td class=\"{'ok' if r['ok'] else 'bad'}\">"
            f"{'LIVE' if r['ok'] else 'DEAD'}</td><td>{r['latency_ms']}ms</td>"
            f"<td>{html.escape(r['ip'])}</td><td>{html.escape(r.get('check') or r['error'])}</td></tr>"
            for r in results
        )
        report = f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Proxy Check - {datetime.now():%d/%m/%Y %H:%M}</title>
<style>
body{{background:#0f1923;color:#ece8e1;font-family:Segoe UI,Arial,sans-serif;padding:24px}}
h1{{color:#ff4655}}.stats{{display:flex;gap:12px;margin:16px 0}}
.stat{{background:#14202c;border:1px solid #243447;padding:14px 18px;border-radius:10px;min-width:120px}}
.n{{font-size:28px;font-weight:700}}.l{{color:#8b978f;font-size:12px;text-transform:uppercase}}
table{{width:100%;border-collapse:collapse;background:#0a111c;border:1px solid #243447}}
th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid #162432}}
th{{background:#162432;color:#8b978f;font-size:12px;text-transform:uppercase}}
.ok{{color:#4caf50;font-weight:700}}.bad{{color:#ef5350;font-weight:700}}
</style>
</head>
<body>
<h1>Proxy Check</h1>
<div class="stats">
  <div class="stat"><div class="n">{len(results)}</div><div class="l">Total</div></div>
  <div class="stat"><div class="n" style="color:#4caf50">{len(live)}</div><div class="l">Live</div></div>
  <div class="stat"><div class="n" style="color:#ef5350">{len(dead)}</div><div class="l">Dead</div></div>
</div>
<table>
<thead><tr><th>Proxy</th><th>Status</th><th>Latency</th><th>Exit IP</th><th>Details</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</body>
</html>"""
        path = run_dir / "index.html"
        path.write_text(report, encoding="utf-8")
        return path

    def start_proxy_check(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self._validate_proxy_check():
            return

        self._save_settings()
        self.cancel_event = threading.Event()
        self.report_path = None
        self._set_progress(0)
        self.progress_text_var.set("0 / 0")
        self.run_status_var.set("Đang check proxy...")
        self.start_button.configure(state="disabled")
        self.proxy_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.report_button.configure(state="disabled")
        self._clear_result_rows()
        self._set_result_headers(("Proxy", "Status", "Latency", "Exit IP", "Server", "Error"))

        proxies_file = Path(self.proxies_var.get())
        proxies = checker.load_proxies(proxies_file)
        total = len(proxies)
        output_dir = Path(self.output_var.get())
        concurrency = max(1, min(10, int(self.concurrency_var.get())))
        self.result_counts["total"] = total
        self.total_stat_var.set(str(total))

        def worker() -> None:
            results: list[dict] = []
            done = 0
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                    future_map = {executor.submit(self._check_one_proxy, proxy): proxy for proxy in proxies}
                    for future in concurrent.futures.as_completed(future_map):
                        if self.cancel_event.is_set():
                            for pending in future_map:
                                pending.cancel()
                            break
                        result = future.result()
                        results.append(result)
                        done += 1
                        self.event_queue.put(("proxy_result", result, done, total))

                report_path = self._write_proxy_report(output_dir, results) if results else None
                self.event_queue.put(("proxy_finished", report_path, results, self.cancel_event.is_set()))
            except Exception as exc:
                self.event_queue.put(("fatal", str(exc)))

        self.worker = threading.Thread(target=worker, name="proxy-check-worker", daemon=True)
        self.worker.start()

    def stop_run(self) -> None:
        if self.worker and self.worker.is_alive():
            self.cancel_event.set()
            self.run_status_var.set("Đang dừng và đóng browser...")
            self.stop_button.configure(state="disabled")

    def _process_events(self) -> None:
        try:
            while True:
                event = self.event_queue.get_nowait()
                kind = event[0]
                if kind == "log" and hasattr(self, "log_text") and self.log_text.winfo_exists():
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", event[1] + "\n")
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")
                elif kind == "result":
                    _kind, result, done, total = event
                    self._add_result(result)
                    self._set_progress((done / total) * 100 if total else 0)
                    self.progress_text_var.set(f"{done} / {total}")
                    self.run_status_var.set(f"Đã xử lý {done}/{total}")
                elif kind == "proxy_result":
                    _kind, result, done, total = event
                    self._add_proxy_result(result)
                    self._set_progress((done / total) * 100 if total else 0)
                    self.progress_text_var.set(f"{done} / {total}")
                    self.run_status_var.set(f"Checked {done}/{total} proxies")
                elif kind == "finished":
                    self._finish_run(event[1])
                elif kind == "proxy_finished":
                    self._finish_proxy_check(event[1], event[2], event[3])
                elif kind == "fatal":
                    self._finish_with_error(event[1])
        except queue.Empty:
            pass
        self.root.after(100, self._process_events)

    def _add_result(self, result: checker.Result) -> None:
        rank = checker.RANK_NAMES[result.tier] if 0 <= result.tier < len(checker.RANK_NAMES) else str(result.tier)
        message = result.error or f"{result.game_name}#{result.tag_line}"
        if result.status == "active":
            tag = "active"
        elif result.status in ("banned", "time_ban", "flagged"):
            tag = "banned"
        else:
            tag = "error"
        self.result_counts[tag] += 1
        self._sync_stats()
        self._append_result_row(result, tag, rank, message)

    def _add_proxy_result(self, result: dict) -> None:
        tag = "active" if result["ok"] else "banned"
        self.result_counts[tag] += 1
        self._sync_stats()
        self._append_table_row(
            [
                result["proxy"],
                "LIVE" if result["ok"] else "DEAD",
                f"{result['latency_ms']} ms",
                result["ip"] or "-",
                result["server"],
                result.get("check") or result["error"] or "OK",
            ],
            tag,
        )

    def _finish_run(self, summary: checker.CheckerRunSummary) -> None:
        self.report_path = summary.report_path
        self.start_button.configure(state="normal")
        self.proxy_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        if self.report_path:
            self.report_button.configure(state="normal")
        if summary.cancelled:
            self.run_status_var.set(f"Đã dừng. Lưu {len(summary.results)} kết quả.")
        else:
            self.run_status_var.set(f"Hoàn tất {len(summary.results)} account")
            self._set_progress(100)

    def _finish_proxy_check(self, report_path: Path | None, results: list[dict], cancelled: bool) -> None:
        self.report_path = report_path
        self.start_button.configure(state="normal")
        self.proxy_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        if self.report_path:
            self.report_button.configure(state="normal")

        live_count = sum(1 for result in results if result["ok"])
        dead_count = len(results) - live_count
        if cancelled:
            self.run_status_var.set(f"Stopped. Saved {len(results)} proxy results.")
        else:
            self.run_status_var.set(f"Completed: {live_count} live / {dead_count} dead")
            self._set_progress(100)

    def _finish_with_error(self, message: str) -> None:
        self.start_button.configure(state="normal")
        self.proxy_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.run_status_var.set("Có lỗi nghiêm trọng")
        messagebox.showerror("Checker error", message)

    def open_report(self) -> None:
        if not self.report_path or not self.report_path.exists():
            messagebox.showwarning("Chưa có báo cáo", "Không tìm thấy file HTML kết quả.")
            return
        try:
            os.startfile(self.report_path)
        except OSError as exc:
            messagebox.showerror("Không mở được HTML", str(exc))

    def logout_license(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Đang chạy", "Dừng checker trước khi đăng xuất key.")
            return
        clear_license()
        self.license = None
        self.show_license_screen()

    def on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Đang chạy", "Checker đang chạy. Dừng và thoát ứng dụng?"):
                return
            self.cancel_event.set()
            self.run_status_var.set("Đang đóng browser và dọn profile...")
            self._wait_for_worker_shutdown(0)
            return
        self.root.destroy()

    def _wait_for_worker_shutdown(self, attempt: int) -> None:
        if self.worker and self.worker.is_alive() and attempt < 150:
            self.root.after(100, lambda: self._wait_for_worker_shutdown(attempt + 1))
            return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ValorantCheckerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
