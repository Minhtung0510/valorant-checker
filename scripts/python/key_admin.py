from __future__ import annotations

import json
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from app_runtime import executable_dir
from license_core import create_license_key, normalize_machine_id


BG = "#0f1923"
PANEL = "#182431"
TEXT = "#ece8e1"
MUTED = "#8b978f"
ACCENT = "#ff4655"
SUCCESS = "#4caf50"


class KeyManagerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Valorant Checker - Key Manager")
        self.root.geometry("820x720")
        self.root.minsize(760, 650)
        self.root.configure(bg=BG)

        self.private_key_path = executable_dir() / "license_private_key.pem"
        self.records_path = executable_dir() / "key_records.json"

        self.customer_var = tk.StringVar()
        self.days_var = tk.IntVar(value=30)
        self.machine_var = tk.StringVar()
        self.note_var = tk.StringVar()
        self.expiry_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Sẵn sàng")

        self._configure_styles()
        self._build_ui()
        self._update_expiry_preview()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Title.TLabel", background=BG, foreground=ACCENT, font=("Segoe UI Semibold", 22))
        style.configure("Accent.TButton", background=ACCENT, foreground="white", padding=(16, 10))
        style.map("Accent.TButton", background=[("active", "#d83a49")])
        style.configure("TButton", padding=(12, 8))
        style.configure("TEntry", fieldbackground="#0d1520", foreground=TEXT, insertcolor=TEXT)
        style.configure("TSpinbox", fieldbackground="#0d1520", foreground=TEXT, insertcolor=TEXT)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="KEY MANAGER", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Tạo license có chữ ký, thời hạn và khóa theo Machine ID.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 18))

        key_state = "Đã tìm thấy private key" if self.private_key_path.exists() else "Thiếu license_private_key.pem"
        key_color = SUCCESS if self.private_key_path.exists() else ACCENT
        key_label = tk.Label(outer, text=key_state, bg=BG, fg=key_color, font=("Segoe UI Semibold", 10))
        key_label.pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(outer, style="Panel.TFrame", padding=20)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self._field(form, 0, "Khách hàng", self.customer_var)

        ttk.Label(form, text="Thời hạn (ngày)", style="Panel.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 14), pady=8)
        days = ttk.Spinbox(form, from_=1, to=3650, textvariable=self.days_var, width=12, command=self._update_expiry_preview)
        days.grid(row=1, column=1, sticky="ew", pady=8)
        days.bind("<KeyRelease>", lambda _event: self._update_expiry_preview())

        ttk.Label(form, text="Hết hạn dự kiến", style="Panel.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 14), pady=8)
        ttk.Label(form, textvariable=self.expiry_var, style="Panel.TLabel").grid(row=2, column=1, sticky="w", pady=8)

        self._field(form, 3, "Machine ID", self.machine_var)
        ttk.Label(
            form,
            text="Để trống nếu key dùng được trên mọi máy. Khuyến nghị nhập Machine ID của khách.",
            background=PANEL,
            foreground=MUTED,
            font=("Segoe UI", 9),
        ).grid(row=4, column=1, sticky="w", pady=(0, 8))

        self._field(form, 5, "Ghi chú", self.note_var)

        button_row = ttk.Frame(form, style="Panel.TFrame")
        button_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        ttk.Button(button_row, text="Tạo key", style="Accent.TButton", command=self.generate_key).pack(side="left")
        ttk.Button(button_row, text="Xóa form", command=self.clear_form).pack(side="left", padx=10)

        ttk.Label(outer, text="License key", style="TLabel").pack(anchor="w", pady=(20, 8))
        self.key_text = tk.Text(
            outer,
            height=7,
            wrap="word",
            bg="#0d1520",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            padx=12,
            pady=12,
            font=("Consolas", 10),
        )
        self.key_text.pack(fill="both", expand=True)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Copy key", command=self.copy_key).pack(side="left")
        ttk.Button(actions, text="Mở thư mục admin", command=self.open_admin_folder).pack(side="left", padx=10)
        ttk.Label(actions, textvariable=self.status_var, style="Muted.TLabel").pack(side="right")

    @staticmethod
    def _field(parent: ttk.Frame, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 14), pady=8)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=8)

    def _update_expiry_preview(self) -> None:
        try:
            days = max(1, int(self.days_var.get()))
            expires_at = int(time.time()) + days * 86400
            self.expiry_var.set(datetime.fromtimestamp(expires_at).strftime("%d/%m/%Y %H:%M"))
        except (ValueError, tk.TclError):
            self.expiry_var.set("Thời hạn không hợp lệ")

    def generate_key(self) -> None:
        if not self.private_key_path.exists():
            messagebox.showerror(
                "Thiếu private key",
                f"Không tìm thấy:\n{self.private_key_path}\n\nHãy chạy generate_license_keypair.py trước khi build.",
            )
            return

        customer = self.customer_var.get().strip()
        if not customer:
            messagebox.showwarning("Thiếu thông tin", "Nhập tên khách hàng hoặc mã đơn hàng.")
            return

        try:
            days = max(1, int(self.days_var.get()))
        except (ValueError, tk.TclError):
            messagebox.showwarning("Sai thời hạn", "Thời hạn phải là số ngày lớn hơn 0.")
            return

        expires_at = int(time.time()) + days * 86400
        machine_id = normalize_machine_id(self.machine_var.get())
        try:
            license_key, claims = create_license_key(
                self.private_key_path,
                customer=customer,
                expires_at=expires_at,
                machine_id=machine_id,
                note=self.note_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Không tạo được key", str(exc))
            return

        self.key_text.delete("1.0", "end")
        self.key_text.insert("1.0", license_key)
        self._append_record(license_key, claims.__dict__)
        self.status_var.set(f"Đã tạo key {claims.key_id}")

    def _append_record(self, license_key: str, claims: dict) -> None:
        try:
            records = json.loads(self.records_path.read_text(encoding="utf-8")) if self.records_path.exists() else []
            records.append({"license_key": license_key, **claims})
            self.records_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            self.status_var.set("Key đã tạo nhưng không lưu được lịch sử")

    def copy_key(self) -> None:
        value = self.key_text.get("1.0", "end").strip()
        if not value:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.status_var.set("Đã copy key")

    def clear_form(self) -> None:
        self.customer_var.set("")
        self.machine_var.set("")
        self.note_var.set("")
        self.key_text.delete("1.0", "end")
        self.status_var.set("Sẵn sàng")

    def open_admin_folder(self) -> None:
        try:
            import os

            os.startfile(executable_dir())
        except OSError as exc:
            messagebox.showerror("Không mở được thư mục", str(exc))


def main() -> None:
    root = tk.Tk()
    KeyManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
