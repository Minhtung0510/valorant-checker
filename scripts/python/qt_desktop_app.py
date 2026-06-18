from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
    QWidget, QFileDialog,
)

from app_runtime import app_data_dir, resource_path


DATA_DIR = app_data_dir()
os.environ.setdefault("LOG_DIR", str(DATA_DIR / "logs"))
import main as checker  # noqa: E402

SETTINGS_PATH = DATA_DIR / "settings.json"


QSS = """
* { font-family: 'Segoe UI'; color: #e9eef5; }
QMainWindow, QWidget#root { background: #081421; }
QFrame#sidebar { background: #091827; border-right: 1px solid #1b3045; }
QFrame#card { background: #0e1d2d; border: 1px solid #20364c; border-radius: 10px; }
QFrame#actionBar { background: #102235; border: 1px solid #263e55; border-radius: 9px; }
QLabel#brand { font-size: 22px; font-weight: 800; color: #ff5263; }
QLabel#pageTitle { font-size: 22px; font-weight: 700; }
QLabel#section { font-size: 13px; font-weight: 700; }
QLabel#muted { color: #8294a8; }
QLabel#number { background: #ff4655; border-radius: 5px; padding: 7px; font-weight: 800; }
QPushButton { background: #162a3d; border: 1px solid #29445e; border-radius: 7px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #1d3850; border-color: #3e668a; }
QPushButton#nav { text-align: left; background: transparent; border: 0; padding: 12px 16px; color: #9fb0c1; }
QPushButton#nav:hover { background: #10243a; color: white; }
QPushButton#nav:checked { background: #241d2c; border: 1px solid #663241; color: white; }
QPushButton#start { background: #43b84d; border: 0; color: white; }
QPushButton#start:hover { background: #55ca60; }
QPushButton#danger { background: #e94f59; border: 0; color: white; }
QPushButton#accent { background: #ff4655; border: 0; color: white; }
QLineEdit, QTextEdit, QTableWidget { background: #07111d; border: 1px solid #223a50; border-radius: 6px; padding: 8px; selection-background-color: #ff4655; }
QLineEdit:focus, QTextEdit:focus { border-color: #4b789d; }
QComboBox { background: #102235; color: #e9eef5; border: 1px solid #29445e; border-radius: 6px; padding: 8px 28px 8px 10px; }
QComboBox:hover, QComboBox:focus { background: #162d43; border-color: #4b789d; }
QComboBox::drop-down { border: 0; width: 24px; }
QComboBox QAbstractItemView { background: #102235; color: #e9eef5; border: 1px solid #35536d; outline: 0; padding: 4px; selection-background-color: #1f6fa8; selection-color: #ffffff; }
QComboBox QAbstractItemView::item { min-height: 30px; padding: 5px 9px; }
QProgressBar { background: #07111d; border: 0; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: #3daee9; border-radius: 4px; }
QHeaderView::section { background: #102235; color: #9db0c3; border: 0; border-bottom: 1px solid #263e55; padding: 9px; }
QTableWidget { gridline-color: #182c3e; }
"""


class Bridge(QObject):
    result = Signal(object, int, int)
    finished = Signal(object)
    failed = Signal(str)
    log = Signal(str)


class QtLogHandler(logging.Handler):
    def __init__(self, bridge: Bridge):
        super().__init__()
        self.bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        self.bridge.log.emit(self.format(record))


class CheckerThread(QThread):
    def __init__(self, bridge: Bridge, options: dict, cancel_event: threading.Event):
        super().__init__()
        self.bridge = bridge
        self.options = options
        self.cancel_event = cancel_event

    def run(self) -> None:
        try:
            def progress(result, done, total):
                self.bridge.result.emit(result, done, total)

            summary = asyncio.run(checker.run_checker(
                **self.options,
                progress_callback=progress,
                cancel_event=self.cancel_event,
            ))
            self.bridge.finished.emit(summary)
        except Exception as exc:
            self.bridge.failed.emit(str(exc))


class PathRow(QWidget):
    def __init__(self, label: str, mode: str = "file"):
        super().__init__()
        self.mode = mode
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        name = QLabel(label)
        name.setObjectName("muted")
        name.setFixedWidth(88)
        self.edit = QLineEdit()
        self.edit.textChanged.connect(self.edit.setToolTip)
        self.edit.editingFinished.connect(lambda: self.edit.setCursorPosition(0))
        choose = QPushButton("Chọn")
        choose.clicked.connect(self.pick)
        layout.addWidget(name)
        layout.addWidget(self.edit, 1)
        layout.addWidget(choose)

    def set_value(self, value: str):
        self.edit.setText(value)
        self.edit.setToolTip(value)
        self.edit.setCursorPosition(0)

    def pick(self):
        if self.mode == "dir":
            value = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        else:
            value, _ = QFileDialog.getOpenFileName(self, "Chọn file")
        if value:
            self.set_value(value)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Valorant Checker")
        self.resize(1440, 900)
        self.setMinimumSize(1120, 720)
        self.setWindowIcon(QIcon(str(resource_path("assets/app-mark.png"))))
        self.bridge = Bridge()
        self.cancel_event = threading.Event()
        self.worker: CheckerThread | None = None
        self.report_path: Path | None = None
        self.nav_buttons: list[QPushButton] = []
        self._build_shell()
        self._connect_bridge()
        self._load_settings()
        self._attach_logger()

    def _build_shell(self):
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame(objectName="sidebar")
        sidebar.setFixedWidth(225)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 25, 20, 20)
        logo = QLabel()
        pix = QPixmap(str(resource_path("assets/app-mark.png"))).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo.setPixmap(pix)
        brand = QLabel("VALORANT\nCHECKER", objectName="brand")
        brand_row = QHBoxLayout()
        brand_row.addWidget(logo)
        brand_row.addWidget(brand, 1)
        side.addLayout(brand_row)


        for index, title in enumerate(("Dashboard", "Kết quả", "Nhật ký", "Hướng dẫn", "Giới thiệu")):
            button = QPushButton(title, objectName="nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.show_page(i))
            self.nav_buttons.append(button)
            side.addWidget(button)
        side.addStretch()



        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(26, 20, 26, 20)
        top = QHBoxLayout()
        self.page_title = QLabel("Dashboard", objectName="pageTitle")
        top.addWidget(self.page_title)
        top.addStretch()
        main_layout.addLayout(top)
        self.pages = QStackedWidget()
        main_layout.addWidget(self.pages, 1)
        self.pages.addWidget(self._dashboard_page())
        self.pages.addWidget(self._results_page())
        self.pages.addWidget(self._logs_page())
        self.pages.addWidget(self._guide_page())
        self.pages.addWidget(self._about_page())
        shell.addWidget(sidebar)
        shell.addWidget(main, 1)
        self.show_page(0)

    def _card(self):
        frame = QFrame(objectName="card")
        frame.setLayout(QVBoxLayout())
        frame.layout().setContentsMargins(18, 16, 18, 16)
        return frame

    def _heading(self, number, title, subtitle):
        row = QHBoxLayout()
        row.addWidget(QLabel(number, objectName="number"))
        copy = QVBoxLayout()
        copy.addWidget(QLabel(title, objectName="section"))
        copy.addWidget(QLabel(subtitle, objectName="muted"))
        row.addLayout(copy, 1)
        return row

    def _dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        cards = QHBoxLayout()
        source = self._card()
        source.layout().addLayout(self._heading("01", "DỮ LIỆU ĐẦU VÀO", "Account, proxy và tốc độ xử lý"))
        self.accounts = PathRow("Accounts TXT")
        self.proxies = PathRow("Proxies TXT")
        source.layout().addWidget(self.accounts)
        duplicate_row = QHBoxLayout()
        self.duplicate_status = QLabel("Chưa kiểm tra trùng", objectName="muted")
        duplicate_btn = QPushButton("Kiểm tra trùng")
        duplicate_btn.clicked.connect(lambda: self.check_duplicate_accounts(True))
        duplicate_row.addWidget(self.duplicate_status)
        duplicate_row.addStretch()
        duplicate_row.addWidget(duplicate_btn)
        source.layout().addLayout(duplicate_row)
        source.layout().addWidget(self.proxies)
        conc = QHBoxLayout()
        conc.addWidget(QLabel("Concurrency", objectName="muted"))
        self.concurrency = QLineEdit("2")
        self.concurrency.setFixedWidth(90)
        self.concurrency.setAlignment(Qt.AlignCenter)
        conc.addWidget(self.concurrency)
        conc.addWidget(QLabel("Nhập từ 1 đến 10 luồng", objectName="muted"))
        conc.addStretch()
        source.layout().addLayout(conc)
        cards.addWidget(source, 1)

        runtime = self._card()
        runtime.layout().addLayout(self._heading("02", "TRÌNH DUYỆT & OUTPUT", "Orbita, captcha và nơi lưu kết quả"))
        self.browser = PathRow("Orbita")
        self.output = PathRow("Output", "dir")
        self.extension = PathRow("Extension", "dir")
        runtime.layout().addWidget(self.browser)
        runtime.layout().addWidget(self.output)
        runtime.layout().addWidget(self.extension)
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("NopeCHA Key", objectName="muted"))
        self.nopecha = QLineEdit()
        self.nopecha.setEchoMode(QLineEdit.Password)
        self.nopecha_toggle = QPushButton("Hiện")
        self.nopecha_toggle.setFixedWidth(64)
        self.nopecha_toggle.clicked.connect(self.toggle_nopecha_key)
        key_row.addWidget(self.nopecha, 1)
        key_row.addWidget(self.nopecha_toggle)
        runtime.layout().addLayout(key_row)
        self.config_status = QLabel()
        self.config_status.setWordWrap(True)
        runtime.layout().addWidget(self.config_status)
        self.browser.edit.textChanged.connect(self.update_config_status)
        self.extension.edit.textChanged.connect(self.update_config_status)
        self.nopecha.textChanged.connect(self.update_config_status)
        cards.addWidget(runtime, 1)
        layout.addLayout(cards)

        actions = QFrame(objectName="actionBar")
        bar = QHBoxLayout(actions)
        self.status = QLabel("Sẵn sàng kiểm tra tài khoản")
        self.start_btn = QPushButton("▶  Bắt đầu", objectName="start")
        self.start_btn.clicked.connect(self.start_check)
        proxy_btn = QPushButton("Check Proxy", objectName="accent")
        proxy_btn.clicked.connect(lambda: QMessageBox.information(self, "Đang thực hiện", "Trang kiểm tra proxy đang được chuyển sang giao diện mới."))
        self.stop_btn = QPushButton("■  Dừng", objectName="danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_check)
        self.html_btn = QPushButton("▣  Xem kết quả")
        self.html_btn.setEnabled(False)
        self.html_btn.clicked.connect(self.open_html)
        bar.addWidget(self.status)
        bar.addStretch()
        for button in (self.start_btn, proxy_btn, self.stop_btn, self.html_btn):
            bar.addWidget(button)
        layout.addWidget(actions)

        stats = QHBoxLayout()
        self.stat_labels = {}
        for key, title, color in (("total", "TOTAL", "#40c4ff"), ("active", "ACTIVE", "#4caf50"), ("bad", "BAD", "#ff5263"), ("error", "ERROR", "#ffad42")):
            card = self._card()
            card.layout().addWidget(QLabel(title, objectName="muted"))
            value = QLabel("0")
            value.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {color}")
            card.layout().addWidget(value)
            self.stat_labels[key] = value
            stats.addWidget(card)
        layout.addLayout(stats)
        progress_card = self._card()
        self.progress_text = QLabel("0 / 0", objectName="muted")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        progress_card.layout().addWidget(self.progress_text)
        progress_card.layout().addWidget(self.progress)
        layout.addWidget(progress_card)
        preview = self._card()
        preview_heading = QHBoxLayout()
        preview_heading.addWidget(QLabel("Kết quả gần nhất", objectName="section"))
        preview_heading.addStretch()
        preview_heading.addWidget(QLabel("Nhấn đúp một account để xem chi tiết", objectName="muted"))
        preview.layout().addLayout(preview_heading)
        self.preview_empty = self._empty_state("Chưa có kết quả", "Bắt đầu kiểm tra để xem dữ liệu tài khoản tại đây.")
        preview.layout().addWidget(self.preview_empty, 1)
        self.preview_table = self._make_table()
        self.preview_table.hide()
        preview.layout().addWidget(self.preview_table)
        layout.addWidget(preview, 1)
        return page

    def _make_table(self):
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(("Account", "Status", "Skins", "Rank", "Region", "Thông tin", "Thời gian"))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.cellDoubleClicked.connect(self.show_result_details)
        return table

    def _results_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        card = self._card()
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("TẤT CẢ KẾT QUẢ", objectName="section"))
        title_row.addStretch()
        title_row.addWidget(QLabel("Lọc status", objectName="muted"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("Tất cả", "all")
        self.status_filter.addItem("Active", "active")
        self.status_filter.addItem("Verify rank", "verify")
        self.status_filter.addItem("Restricted", "restricted")
        self.status_filter.addItem("Banned", "banned")
        self.status_filter.addItem("Error", "error")
        self.status_filter.view().setStyleSheet(
            "background-color: #102235; color: #e9eef5; border: 1px solid #35536d; "
            "outline: 0; selection-background-color: #1f6fa8; selection-color: white;"
        )
        self.status_filter.currentIndexChanged.connect(self.filter_results)
        title_row.addWidget(self.status_filter)
        clear_btn = QPushButton("Xóa kết quả", objectName="danger")
        clear_btn.clicked.connect(self.clear_results)
        title_row.addWidget(clear_btn)
        card.layout().addLayout(title_row)
        card.layout().addWidget(QLabel("Dữ liệu cập nhật realtime • nhấn đúp một account để xem chi tiết", objectName="muted"))
        self.results_empty = self._empty_state("Chưa có dữ liệu", "Kết quả kiểm tra account sẽ xuất hiện tại đây.")
        card.layout().addWidget(self.results_empty, 1)
        self.results_table = self._make_table()
        self.results_table.hide()
        card.layout().addWidget(self.results_table)
        layout.addWidget(card)
        return page

    def _empty_state(self, title: str, description: str):
        box = QFrame()
        layout = QVBoxLayout(box)
        layout.addStretch()
        icon = QLabel("◇")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 38px; color: #526b82")
        heading = QLabel(title)
        heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet("font-size: 16px; font-weight: 700; color: #b7c4d1")
        detail = QLabel(description, objectName="muted")
        detail.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)
        layout.addWidget(heading)
        layout.addWidget(detail)
        layout.addStretch()
        return box

    def _settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)

        grid = QGridLayout()
        browser_card = self._card()
        browser_card.layout().addLayout(self._heading("01", "TRÌNH DUYỆT", "Thiết lập Orbita và tiện ích captcha"))
        self.settings_browser = PathRow("Orbita")
        self.settings_extension = PathRow("Extension", "dir")
        browser_card.layout().addWidget(self.settings_browser)
        browser_card.layout().addWidget(self.settings_extension)
        grid.addWidget(browser_card, 0, 0)

        captcha_card = self._card()
        captcha_card.layout().addLayout(self._heading("02", "CAPTCHA", "Khóa dịch vụ NopeCHA"))
        captcha_row = QHBoxLayout()
        captcha_row.addWidget(QLabel("NopeCHA Key", objectName="muted"))
        self.settings_nopecha = QLineEdit()
        captcha_row.addWidget(self.settings_nopecha, 1)
        captcha_card.layout().addLayout(captcha_row)
        grid.addWidget(captcha_card, 0, 1)

        performance_card = self._card()
        performance_card.layout().addLayout(self._heading("03", "HIỆU NĂNG", "Số account xử lý đồng thời"))
        perf_row = QHBoxLayout()
        perf_row.addWidget(QLabel("Concurrency mặc định", objectName="muted"))
        self.settings_concurrency = QLineEdit("2")
        self.settings_concurrency.setFixedWidth(90)
        self.settings_concurrency.setAlignment(Qt.AlignCenter)
        perf_row.addWidget(self.settings_concurrency)
        perf_row.addWidget(QLabel("Từ 1 đến 10", objectName="muted"))
        perf_row.addStretch()
        performance_card.layout().addLayout(perf_row)
        grid.addWidget(performance_card, 1, 0)

        output_card = self._card()
        output_card.layout().addLayout(self._heading("04", "KẾT QUẢ", "Nơi lưu dữ liệu sau khi kiểm tra"))
        self.settings_output = PathRow("Output", "dir")
        output_card.layout().addWidget(self.settings_output)
        self.auto_open_output = QCheckBox("Tự động mở thư mục kết quả khi hoàn tất")
        output_card.layout().addWidget(self.auto_open_output)
        grid.addWidget(output_card, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        app_card = self._card()
        app_card.layout().addLayout(self._heading("05", "ỨNG DỤNG", "Lưu và khôi phục cấu hình"))
        self.auto_save_settings = QCheckBox("Tự động lưu cấu hình trước khi chạy")
        self.auto_save_settings.setChecked(True)
        self.cleanup_profiles = QCheckBox("Xóa browser profile tạm sau khi hoàn tất")
        self.cleanup_profiles.setChecked(True)
        app_card.layout().addWidget(self.auto_save_settings)
        app_card.layout().addWidget(self.cleanup_profiles)
        buttons = QHBoxLayout()
        buttons.addStretch()
        reset = QPushButton("Khôi phục mặc định")
        reset.clicked.connect(self.reset_settings)
        save = QPushButton("Lưu cài đặt", objectName="start")
        save.clicked.connect(self.save_settings_page)
        buttons.addWidget(reset)
        buttons.addWidget(save)
        app_card.layout().addLayout(buttons)
        layout.addWidget(app_card)
        layout.addStretch()
        return page

    def _guide_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        intro = self._card()
        intro.layout().addWidget(QLabel("HƯỚNG DẪN BẮT ĐẦU", objectName="section"))
        intro.layout().addWidget(QLabel("Chuẩn bị dữ liệu đúng định dạng trước khi chạy checker.", objectName="muted"))
        layout.addWidget(intro)

        required = QHBoxLayout()
        account = self._card()
        account_title = QLabel("ACCOUNT TXT — BẮT BUỘC")
        account_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #ff5968")
        account.layout().addWidget(account_title)
        account.layout().addWidget(QLabel("Mỗi tài khoản nằm trên một dòng:", objectName="muted"))
        account_format = QLineEdit("username:password")
        account_format.setReadOnly(True)
        account.layout().addWidget(account_format)
        required.addWidget(account)

        proxy = self._card()
        proxy_title = QLabel("PROXY TXT — BẮT BUỘC")
        proxy_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffad42")
        proxy.layout().addWidget(proxy_title)
        proxy.layout().addWidget(QLabel("Mỗi proxy nằm trên một dòng:", objectName="muted"))
        proxy_format = QLineEdit("ip:port:user:password  hoặc  ip:port")
        proxy_format.setReadOnly(True)
        proxy.layout().addWidget(proxy_format)
        proxy.layout().addWidget(QLabel("Proxy phải hoạt động và phù hợp với region của account.", objectName="muted"))
        required.addWidget(proxy)
        layout.addLayout(required)

        steps = self._card()
        steps.layout().addWidget(QLabel("CÁC BƯỚC THỰC HIỆN", objectName="section"))
        step_texts = (
            "1. Chọn file Accounts TXT và Proxies TXT.",
            "2. Chọn đúng file Orbita chrome.exe.",
            "3. Chọn thư mục output để lưu kết quả.",
            "4. Nhập NopeCHA Key và chọn extension nếu sử dụng captcha solver.",
            "5. Nhập Concurrency từ 1 đến 10; nên bắt đầu với 1–3.",
            "6. Nhấn Bắt đầu và theo dõi tiến độ trên Dashboard hoặc Nhật ký.",
        )
        for text in step_texts:
            label = QLabel(text)
            label.setContentsMargins(4, 5, 4, 5)
            steps.layout().addWidget(label)
        layout.addWidget(steps)
        layout.addStretch()
        return page

    def _about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        card = self._card()
        card.layout().addStretch()
        mark = QLabel()
        mark.setAlignment(Qt.AlignCenter)
        mark.setPixmap(QPixmap(str(resource_path("assets/app-mark.png"))).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        card.layout().addWidget(mark)
        title = QLabel("Valorant-Checker 1.0")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #ff5263")
        card.layout().addWidget(title)
        description = QLabel(
            "Công cụ hỗ trợ kiểm tra và tổng hợp thông tin tài khoản Valorant nhanh chóng "
            "trên một giao diện trực quan. Ứng dụng giúp theo dõi tiến độ và quản lý kết quả "
            "tập trung, thuận tiện hơn trong quá trình làm việc."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignCenter)
        description.setMaximumWidth(720)
        description.setStyleSheet("color: #9fb0c1; font-size: 13px; line-height: 1.5")
        description_box = QHBoxLayout()
        description_box.addStretch()
        description_box.addWidget(description)
        description_box.addStretch()
        card.layout().addLayout(description_box)
        developer = QLabel("Người phát triển:  mmb")
        developer.setAlignment(Qt.AlignCenter)
        developer.setStyleSheet("font-size: 14px; font-weight: 700; margin-top: 16px")
        card.layout().addWidget(developer)
        support = QLabel("Kênh hỗ trợ:")
        support.setAlignment(Qt.AlignCenter)
        support.setObjectName("muted")
        card.layout().addWidget(support)
        card.layout().addStretch()
        layout.addWidget(card)
        return page

    def _logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        card = self._card()
        card.layout().addWidget(QLabel("NHẬT KÝ REALTIME", objectName="section"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        card.layout().addWidget(self.log_view)
        layout.addWidget(card)
        return page

    def _placeholder(self, title, text):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        card = self._card()
        card.layout().addStretch()
        heading = QLabel(title)
        heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet("font-size: 25px; font-weight: 700")
        description = QLabel(text, objectName="muted")
        description.setAlignment(Qt.AlignCenter)
        card.layout().addWidget(heading)
        card.layout().addWidget(description)
        card.layout().addStretch()
        layout.addWidget(card)
        return page

    def _connect_bridge(self):
        self.bridge.result.connect(self.on_result)
        self.bridge.finished.connect(self.on_finished)
        self.bridge.failed.connect(self.on_failed)
        self.bridge.log.connect(self.append_log)

    def _attach_logger(self):
        handler = QtLogHandler(self.bridge)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S"))
        checker.logger.addHandler(handler)

    def show_page(self, index):
        titles = ("Dashboard", "Kết quả", "Nhật ký", "Hướng dẫn", "Giới thiệu")
        self.pages.setCurrentIndex(index)
        self.page_title.setText(titles[index])
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

    def _load_settings(self):
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        self.accounts.set_value(data.get("accounts_file", str(Path(__file__).parent / "accounts.txt")))
        self.proxies.set_value(data.get("proxies_file", ""))
        self.browser.set_value(data.get("browser_path", ""))
        self.output.set_value(data.get("output_dir", str(Path.home() / "Desktop" / "Check-done")))
        self.extension.set_value(data.get("extension_path", ""))
        self.concurrency.setText(str(data.get("concurrency", 2)))
        self.nopecha.setText(data.get("nopecha_api_key", ""))
        self.update_config_status()

    def toggle_nopecha_key(self):
        hidden = self.nopecha.echoMode() == QLineEdit.Password
        self.nopecha.setEchoMode(QLineEdit.Normal if hidden else QLineEdit.Password)
        self.nopecha_toggle.setText("Ẩn" if hidden else "Hiện")

    def update_config_status(self):
        browser_ok = Path(self.browser.edit.text()).is_file()
        extension_text = self.extension.edit.text().strip()
        extension_ok = bool(extension_text) and Path(extension_text).is_dir() and (Path(extension_text) / "manifest.json").is_file()
        key_ok = bool(self.nopecha.text().strip())

        def badge(ok: bool, label: str, missing: str):
            color = "#55c96b" if ok else "#ffad42"
            text = label if ok else missing
            return f'<span style="color:{color}">●</span> {text}'

        parts = [
            badge(browser_ok, "Orbita sẵn sàng", "Chưa tìm thấy Orbita"),
            badge(extension_ok, "Extension hợp lệ", "Extension chưa hợp lệ"),
            badge(key_ok, "Đã nhập NopeCHA Key", "Chưa nhập NopeCHA Key"),
        ]
        self.config_status.setText("&nbsp;&nbsp;&nbsp;".join(parts))

    def clear_results(self):
        for table in (self.preview_table, self.results_table):
            table.setRowCount(0)
            table.hide()
        self.preview_empty.show()
        self.results_empty.show()
        for key in ("total", "active", "bad", "error"):
            self.stat_labels[key].setText("0")
        self.progress.setValue(0)
        self.progress_text.setText("0 / 0")
        self.report_path = None
        self.html_btn.setEnabled(False)
        self.status.setText("Đã xóa kết quả")

    def _duplicate_account_info(self):
        path = Path(self.accounts.edit.text())
        if not path.is_file():
            return 0, 0, []
        seen: set[str] = set()
        duplicates: list[str] = []
        valid_count = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            account = checker.Account.parse(line)
            if not account:
                continue
            valid_count += 1
            key = account.username.strip().casefold()
            if key in seen:
                duplicates.append(account.username)
            else:
                seen.add(key)
        return valid_count, len(seen), duplicates

    def check_duplicate_accounts(self, show_dialog=True):
        path = Path(self.accounts.edit.text())
        if not path.is_file():
            self.duplicate_status.setText("Chưa chọn file account hợp lệ")
            self.duplicate_status.setStyleSheet("color: #ffad42")
            if show_dialog:
                QMessageBox.warning(self, "Kiểm tra trùng", "Hãy chọn file Accounts TXT hợp lệ.")
            return

        total, unique, duplicates = self._duplicate_account_info()
        if duplicates:
            self.duplicate_status.setText(f"{len(duplicates)} dòng trùng • sẽ chạy {unique}/{total} account")
            self.duplicate_status.setStyleSheet("color: #ffad42")
            if show_dialog:
                names = "\n".join(f"• {name}" for name in duplicates[:10])
                more = f"\n… và {len(duplicates) - 10} dòng khác" if len(duplicates) > 10 else ""
                QMessageBox.information(
                    self,
                    "Account trùng",
                    f"Tìm thấy {len(duplicates)} dòng trùng theo username.\n"
                    f"Khi chạy sẽ giữ dòng đầu và bỏ qua dòng sau.\n\n{names}{more}",
                )
        else:
            self.duplicate_status.setText(f"Không có account trùng • {unique} account")
            self.duplicate_status.setStyleSheet("color: #55c96b")
            if show_dialog:
                QMessageBox.information(self, "Kiểm tra trùng", f"Không phát hiện account trùng trong {unique} account.")

    @staticmethod
    def _status_group(status: str):
        if status == "active":
            return "active"
        if status == "competitive_verify":
            return "verify"
        if status == "competitive_restricted":
            return "restricted"
        if status in ("banned", "time_ban", "flagged"):
            return "banned"
        return "error"

    def filter_results(self):
        selected = self.status_filter.currentData()
        for row in range(self.results_table.rowCount()):
            item = self.results_table.item(row, 1)
            status = item.data(Qt.ItemDataRole.UserRole) if item else ""
            visible = selected == "all" or self._status_group(status) == selected
            self.results_table.setRowHidden(row, not visible)

    def show_result_details(self, row, _column):
        table = self.sender()
        account_item = table.item(row, 0) if isinstance(table, QTableWidget) else None
        result = account_item.data(Qt.ItemDataRole.UserRole) if account_item else None
        if not result:
            return

        tier = checker.RANK_NAMES[result.tier] if 0 <= result.tier < len(checker.RANK_NAMES) else f"Rank {result.tier}"
        rank = f"{tier} • {result.rr} RR" if result.tier else "Unrated"
        riot_id = f"{result.game_name}#{result.tag_line}" if result.game_name else "—"
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Chi tiết account • {result.username}")
        dialog.setMinimumWidth(560)
        layout = QVBoxLayout(dialog)
        heading = QLabel("CHI TIẾT ACCOUNT", objectName="section")
        layout.addWidget(heading)
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        details = (
            ("Account", result.username),
            ("Riot ID", riot_id),
            ("Status", result.status_label),
            ("Rank", rank),
            ("Level", str(result.level)),
            ("Region", result.region.upper() or "—"),
            ("Country", result.country or "—"),
            ("Skins", str(result.skins_count)),
            ("Email verified", "Có" if result.email_verified else "Không"),
            ("Phone verified", "Có" if result.phone_verified else "Không"),
            ("Ngày tạo", result.created_at or "—"),
            ("Thông tin", result.error or "Không có lỗi"),
        )
        for name, value in details:
            value_label = QLabel(value)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setWordWrap(True)
            form.addRow(QLabel(name, objectName="muted"), value_label)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _save_settings(self, concurrency):
        data = {
            "accounts_file": self.accounts.edit.text(), "proxies_file": self.proxies.edit.text(),
            "browser_path": self.browser.edit.text(), "output_dir": self.output.edit.text(),
            "extension_path": self.extension.edit.text(), "concurrency": concurrency,
            "nopecha_api_key": self.nopecha.text(),
        }
        SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_settings_page(self):
        try:
            concurrency = int(self.settings_concurrency.text().strip())
            if not 1 <= concurrency <= 10:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Concurrency", "Concurrency phải là số từ 1 đến 10.")
            return
        self.browser.edit.setText(self.settings_browser.edit.text())
        self.extension.edit.setText(self.settings_extension.edit.text())
        self.output.edit.setText(self.settings_output.edit.text())
        self.concurrency.setText(str(concurrency))
        self.nopecha.setText(self.settings_nopecha.text())
        self._save_settings(concurrency)
        QMessageBox.information(self, "Cài đặt", "Đã lưu cài đặt.")

    def reset_settings(self):
        self.settings_browser.edit.clear()
        self.settings_extension.edit.clear()
        self.settings_output.edit.setText(str(Path.home() / "Desktop" / "Check-done"))
        self.settings_concurrency.setText("2")
        self.settings_nopecha.clear()
        self.auto_open_output.setChecked(False)
        self.auto_save_settings.setChecked(True)
        self.cleanup_profiles.setChecked(True)

    def start_check(self):
        if self.worker and self.worker.isRunning():
            return
        try:
            concurrency = int(self.concurrency.text().strip())
            if not 1 <= concurrency <= 10:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Concurrency", "Concurrency phải là số từ 1 đến 10.")
            return
        accounts = Path(self.accounts.edit.text())
        browser = Path(self.browser.edit.text())
        if not accounts.is_file() or not browser.is_file():
            QMessageBox.warning(self, "Thiếu dữ liệu", "Hãy chọn Accounts TXT và Orbita chrome.exe hợp lệ.")
            return
        self.check_duplicate_accounts(False)
        proxies = Path(self.proxies.edit.text()) if self.proxies.edit.text() else DATA_DIR / "empty_proxies.txt"
        if not proxies.exists():
            proxies.write_text("", encoding="utf-8")
        self._save_settings(concurrency)
        os.environ["NOPECHA_API_KEY"] = self.nopecha.text()
        os.environ.pop("GOLOGIN_TOKEN", None)
        self.cancel_event = threading.Event()
        self.report_path = None
        for table in (self.preview_table, self.results_table):
            table.setRowCount(0)
            table.hide()
        self.preview_empty.show()
        self.results_empty.show()
        self.html_btn.setEnabled(False)
        total = len(checker.load_accounts(accounts))
        self.stat_labels["total"].setText(str(total))
        for key in ("active", "bad", "error"):
            self.stat_labels[key].setText("0")
        self.progress.setValue(0)
        self.status.setText("Đang khởi tạo checker...")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        options = dict(
            accounts_file=accounts, proxies_file=proxies, output_dir=Path(self.output.edit.text()),
            concurrency=concurrency, browser_path=browser,
            extension_path=Path(self.extension.edit.text()) if self.extension.edit.text() else None,
        )
        self.worker = CheckerThread(self.bridge, options, self.cancel_event)
        self.worker.start()

    def stop_check(self):
        self.cancel_event.set()
        self.status.setText("Đang dừng và đóng browser...")
        self.stop_btn.setEnabled(False)

    def on_result(self, result, done, total):
        tier = checker.RANK_NAMES[result.tier] if 0 <= result.tier < len(checker.RANK_NAMES) else f"Rank {result.tier}"
        rank = f"{tier} • {result.rr}RR" if result.tier else "Unrated"
        values = (result.username, result.status_label, str(result.skins_count), rank, result.region.upper(), result.error or result.game_name, "Vừa xong")
        status_colors = {
            "active": ("#55c96b", "#122d25"),
            "competitive_verify": ("#ffd166", "#332b16"),
            "competitive_restricted": ("#ffad42", "#352416"),
            "banned": ("#ff5b68", "#351820"),
            "time_ban": ("#ff5b68", "#351820"),
            "flagged": ("#ff8a50", "#352018"),
        }
        foreground, background = status_colors.get(result.status, ("#b9c6d3", "#182532"))
        self.preview_empty.hide()
        self.results_empty.hide()
        self.preview_table.show()
        self.results_table.show()
        for table in (self.preview_table, self.results_table):
            row = table.rowCount()
            table.insertRow(row)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, result)
                if column == 1:
                    item.setForeground(QColor(foreground))
                    item.setBackground(QColor(background))
                    item.setData(Qt.ItemDataRole.UserRole, result.status)
                table.setItem(row, column, item)
        self.filter_results()
        active = int(self.stat_labels["active"].text())
        bad = int(self.stat_labels["bad"].text())
        error = int(self.stat_labels["error"].text())
        if result.ok and result.status == "active": active += 1
        elif result.status in ("banned", "time_ban", "flagged", "competitive_verify", "competitive_restricted"): bad += 1
        else: error += 1
        self.stat_labels["active"].setText(str(active))
        self.stat_labels["bad"].setText(str(bad))
        self.stat_labels["error"].setText(str(error))
        self.progress.setValue(round(done * 100 / max(total, 1)))
        self.progress_text.setText(f"{done} / {total}")
        self.status.setText(f"Đang xử lý • {done}/{total}")

    def on_finished(self, summary):
        self.report_path = summary.report_path
        self.status.setText("Đã hoàn thành" if not summary.cancelled else "Đã dừng")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.html_btn.setEnabled(bool(self.report_path))

    def on_failed(self, message):
        self.status.setText("Có lỗi xảy ra")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "Checker", message)

    def append_log(self, text):
        self.log_view.append(text)

    def open_html(self):
        if self.report_path and self.report_path.exists():
            os.startfile(self.report_path)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.cancel_event.set()
            self.worker.wait(5000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

