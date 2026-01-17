import re
import os
import webbrowser
import shlex
import json
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from pathlib import Path
import time
import platform
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QFileDialog, QTextEdit, QVBoxLayout, QHBoxLayout, QListWidget,
    QTreeWidget, QTreeWidgetItem, QFrame, QScrollBar, QSizePolicy, QSplitter, QLineEdit, QCheckBox, QMenu, QMessageBox,
    QSystemTrayIcon, QStyle  # ✅ 保留导入，无需注释，解耦核心
)
from PyQt6.QtCore import Qt, QMimeData, QThread, pyqtSignal, QTimer, QCoreApplication
from PyQt6.QtGui import QDrag, QPixmap, QFont, QCursor, QColor, QPalette, QAction, QIcon  # ✅ 必导：图标组件

# 配置常量
IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif'}  # 扩展图片格式
VIDEO_EXTS = {'webm', 'mp4', 'mkv'}  # 扩展视频格式

# 预设路径（和HTML中一致）
DEFAULT_PATHS = {
    "国服": os.path.expandvars(r"%USERPROFILE%\AppData\Roaming\miHoYo\HYP\1_1\fedata\Cache\Cache_Data") if platform.system() == "Windows" 
           else os.path.expanduser("~/.config/miHoYo/HYP/1_1/fedata/Cache/Cache_Data"),
    "国际服": os.path.expandvars(r"%USERPROFILE%\AppData\Roaming\Cognosphere\HYP\1_0\fedata\Cache\Cache_Data") if platform.system() == "Windows"
           else os.path.expanduser("~/.config/Cognosphere/HYP/1_0/fedata/Cache/Cache_Data")
}

# 配置文件路径（记忆上次选择的路径）
CONFIG_PATH = os.path.expanduser("~/.mihoyo_extractor_config.json")
APP_TITLE = "米哈游启动器媒体提取器"

# 优化URL正则（减少无效匹配，符合RFC标准）
URL_REGEX = re.compile(
    r'https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',
    re.IGNORECASE
)

# ========== 后台处理线程（原有功能，无修改） ==========
class FileProcessThread(QThread):
    progress_signal = pyqtSignal(str, str)  # 进度文本、颜色
    result_signal = pyqtSignal(list)        # 提取的URL列表
    error_signal = pyqtSignal(str)          # 错误信息

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        try:
            all_urls = set()
            total_files = len(self.file_paths)
            
            for idx, file_path in enumerate(self.file_paths):
                self.progress_signal.emit(
                    f"⚡ 处理中 ({idx+1}/{total_files})：{os.path.basename(file_path)}",
                    "#f59e0b"
                )
                block_size = 1024 * 1024
                with open(file_path, "rb") as f:
                    while chunk := f.read(block_size):
                        content = chunk.decode("utf-8", errors="ignore")
                        urls = URL_REGEX.findall(content)
                        all_urls.update(urls)
            
            valid_urls = self._filter_valid_urls(list(all_urls))
            self.result_signal.emit(valid_urls)
            self.progress_signal.emit(
                f"✅ 处理完成：共提取 {len(valid_urls)} 个有效链接",
                "#16a34a"
            )
        except Exception as e:
            self.error_signal.emit(str(e))

    def _filter_valid_urls(self, urls):
        valid_urls = []
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.netloc and parsed.scheme in ["http", "https"] and len(url) > 10:
                    valid_urls.append(url)
            except:
                continue
        return valid_urls

# ========== 主窗口类（仅修改托盘/关闭逻辑） ==========
class MiHoYoMediaExtractor(QMainWindow):
    def set_transparent_no_border(self, widget, color="#6b7280"):
        widget.setStyleSheet(f"color: {color}; border: none; background-color: transparent; padding: 0px; margin: 0px;")
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        self.setFixedSize(self.size())

        # 全局变量
        self.all_matches = []
        self.filtered_matches = []
        self.current_page = 1
        self.file_paths = []
        self.last_path = self._load_last_path()
        self.process_thread = None
        self.items_per_page = 8
        self.tray_icon = None  # 托盘对象
        
        # 初始化UI + 绑定快捷键
        self._init_ui()
        self._bind_shortcuts()
        self._calculate_items_per_page()
        QTimer.singleShot(100, self._calculate_items_per_page)
        
        # ========== 新增：初始化系统托盘 ==========
        self._init_tray()

    def _load_last_path(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get("last_path", "")
        except:
            return ""

    def _save_last_path(self, path):
        try:
            config = {"last_path": path}
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False)
        except:
            pass

    def _calculate_items_per_page(self):
        if not hasattr(self, 'result_tree') or self.result_tree.viewport().height() < 40:
            self.items_per_page = 2
            return
        tree_viewport_height = self.result_tree.viewport().height()
        header_real_height = self.result_tree.header().height()
        single_row_height = 14
        safe_margin = 2
        calc_count = int((tree_viewport_height - header_real_height - safe_margin) / single_row_height)
        self.items_per_page = max(1, min(calc_count, 60))
        if self.filtered_matches and len(self.filtered_matches) > 0:
            self._apply_filters(keep_page=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.result_tree.updateGeometry()
        QApplication.processEvents()
        self._calculate_items_per_page()

    def _get_total_pages(self):
        if not self.filtered_matches:
            return 1
        total = len(self.filtered_matches)
        total_pages = total // self.items_per_page
        if total % self.items_per_page != 0:
            total_pages += 1
        return max(1, total_pages)

    # ========== 新增：初始化系统托盘 ==========
    def _init_tray(self):
        # 创建托盘图标（可替换为自定义图标，这里用默认样式）
        self.tray_icon = QSystemTrayIcon(self)
        # 兼容不同平台的图标（如果没有自定义图标，用QT默认）
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        
        # 创建托盘菜单
        tray_menu = QMenu(self)
        
        # 显示窗口动作
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show_normal)
        tray_menu.addAction(show_action)
        
        # 退出程序动作
        exit_action = QAction("退出程序", self)
        exit_action.triggered.connect(self._exit_app_completely)
        tray_menu.addAction(exit_action)
        
        # 绑定托盘菜单
        self.tray_icon.setContextMenu(tray_menu)
        
        # 托盘点击事件（左键显示窗口）
        self.tray_icon.activated.connect(self._on_tray_click)
        
        # 显示托盘（如果要禁用托盘，注释这一行即可）
        # self.tray_icon.show()

    # ========== 新增：托盘点击事件 ==========
    def _on_tray_click(self, reason):
        # 左键点击托盘显示窗口
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_normal()

    # ========== 新增：完全退出程序（托盘触发） ==========
    def _exit_app_completely(self):
        # 停止正在运行的后台线程
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.terminate()
            self.process_thread.wait()
        
        # 隐藏托盘
        if self.tray_icon:
            self.tray_icon.hide()
        
        # 关闭窗口并退出进程
        self.close()
        QCoreApplication.quit()
        sys.exit(0)

    # ========== 重写：关闭窗口事件 ==========
    def closeEvent(self, event):
        # 判断是否启用了托盘
        if self.tray_icon and self.tray_icon.isVisible():
            # 有托盘：隐藏窗口，不退出进程
            self.hide()
            event.ignore()  # 忽略默认的关闭行为
        else:
            # 无托盘：直接完全退出
            self._exit_app_completely()
            event.accept()

    # ========== 辅助：恢复窗口显示 ==========
    def show_normal(self):
        self.show()
        self.setWindowState(Qt.WindowState.WindowNoState)  # 恢复正常窗口状态

    # ========== 初始化UI（原有代码，无修改） ==========
    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = QLabel(APP_TITLE)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2563eb;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub_title = QLabel("拖拽/批量选择文件，自动提取媒体链接 | 支持跨平台/批量处理/链接导出")
        sub_font = QFont()
        sub_font.setPointSize(10)
        sub_title.setFont(sub_font)
        sub_title.setStyleSheet("color: #6b7280;")
        
        title_layout = QVBoxLayout()
        title_layout.addWidget(title_label)
        title_layout.addWidget(sub_title)
        main_layout.addLayout(title_layout)

        path_frame = QFrame()
        self.set_transparent_no_border(path_frame)
        path_layout = QVBoxLayout(path_frame)
        path_layout.setContentsMargins(15, 10, 15, 10)
        
        cn_layout = QHBoxLayout()
        cn_label = QLabel("国 服 路 径：")
        cn_label.setFont(sub_font)
        self.set_transparent_no_border(cn_label)
        cn_entry = QLineEdit(DEFAULT_PATHS["国服"])
        cn_entry.setFont(QFont("Consolas" if platform.system() == "Windows" else "Monaco", 9))
        cn_entry.setReadOnly(True)
        cn_copy_btn = QPushButton("复制")
        cn_copy_btn.clicked.connect(lambda: self._copy_text(cn_entry.text()))
        cn_layout.addWidget(cn_label)
        cn_layout.addWidget(cn_entry)
        cn_layout.addWidget(cn_copy_btn)
        path_layout.addLayout(cn_layout)

        global_layout = QHBoxLayout()
        global_label = QLabel("国际服路径：")
        global_label.setFont(sub_font)
        self.set_transparent_no_border(global_label)
        global_entry = QLineEdit(DEFAULT_PATHS["国际服"])
        global_entry.setFont(QFont("Consolas" if platform.system() == "Windows" else "Monaco", 9))
        global_entry.setReadOnly(True)
        global_copy_btn = QPushButton("复制")
        global_copy_btn.clicked.connect(lambda: self._copy_text(global_entry.text()))
        global_layout.addWidget(global_label)
        global_layout.addWidget(global_entry)
        global_layout.addWidget(global_copy_btn)
        path_layout.addLayout(global_layout)
        
        main_layout.addWidget(path_frame)

        self.drag_frame = QFrame()
        self.set_transparent_no_border(self.drag_frame)
        drag_layout = QVBoxLayout(self.drag_frame)
        drag_layout.setContentsMargins(20, 15, 20, 15)
        
        drag_label = QLabel("🖱️ 拖拽文件到此处（支持多文件） | 或点击按钮选择")
        drag_label.setFont(sub_font)
        self.set_transparent_no_border(drag_label, "#3b82f6")
        drag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drag_layout.addWidget(drag_label)

        btn_layout = QHBoxLayout()
        single_btn = QPushButton("选择单个文件")
        single_btn.setStyleSheet("background-color: #3b82f6; color: white; padding: 8px 15px; border: none; border-radius: 4px;")
        single_btn.clicked.connect(lambda: self._select_files(multi=False))
        
        multi_btn = QPushButton("选择多个文件")
        multi_btn.setStyleSheet("background-color: #10b981; color: white; padding: 8px 15px; border: none; border-radius: 4px;")
        multi_btn.clicked.connect(lambda: self._select_files(multi=True))
        
        clear_btn = QPushButton("清空结果")
        clear_btn.setStyleSheet("background-color: #ef4444; color: white; padding: 8px 15px; border: none; border-radius: 4px;")
        clear_btn.clicked.connect(self._clear_results)
        
        btn_layout.addWidget(single_btn)
        btn_layout.addWidget(multi_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drag_layout.addLayout(btn_layout)

        self.file_status_label = QLabel(f"✅ 等待选择/拖拽文件 | 上次路径：{os.path.basename(self.last_path) if self.last_path else '无'}")
        self.file_status_label.setFont(sub_font)
        self.set_transparent_no_border(self.file_status_label)
        self.file_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drag_layout.addWidget(self.file_status_label)

        self.drag_frame.setAcceptDrops(True)
        self.drag_frame.dragEnterEvent = self._on_drag_enter
        self.drag_frame.dragLeaveEvent = self._on_drag_leave
        self.drag_frame.dropEvent = self._on_drag_drop
        
        main_layout.addWidget(self.drag_frame)

        filter_frame = QFrame()
        self.set_transparent_no_border(filter_frame)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        
        self.img_check = QCheckBox("图片 (jpg/png/webp等)")
        self.img_check.setFont(sub_font)
        self.img_check.setChecked(True)
        self.img_check.stateChanged.connect(self._apply_filters)
        
        self.video_check = QCheckBox("视频 (webm/mp4等)")
        self.video_check.setFont(sub_font)
        self.video_check.setChecked(True)
        self.video_check.stateChanged.connect(self._apply_filters)
        
        self.other_check = QCheckBox("其他 (json/config等)")
        self.other_check.setFont(sub_font)
        self.other_check.setChecked(False)
        self.other_check.stateChanged.connect(self._apply_filters)
        
        export_btn = QPushButton("导出当前链接")
        export_btn.setStyleSheet("background-color: #8b5cf6; color: white; padding: 6px 12px; border: none; border-radius: 4px;")
        export_btn.clicked.connect(self._export_links)
        
        filter_layout.addWidget(self.img_check)
        filter_layout.addWidget(self.video_check)
        filter_layout.addWidget(self.other_check)
        filter_layout.addStretch()
        filter_layout.addWidget(export_btn)
        main_layout.addWidget(filter_frame)

        pagination_frame = QFrame()
        self.set_transparent_no_border(pagination_frame)
        pagination_layout = QHBoxLayout(pagination_frame)
        
        self.page_info_label = QLabel("第 1 / 1 页 | 共 0 个链接")
        self.page_info_label.setFont(sub_font)
        self.set_transparent_no_border(self.page_info_label)
        pagination_layout.addWidget(self.page_info_label)
        
        prev_btn = QPushButton("上一页")
        prev_btn.setFont(QFont("Segoe UI", 9))
        prev_btn.setFixedWidth(60)
        prev_btn.clicked.connect(lambda: self._goto_page(self.current_page - 1))
        pagination_layout.addWidget(prev_btn)
        
        self.page_edit = QLineEdit("1")
        self.page_edit.setFont(QFont("Segoe UI", 9))
        self.page_edit.setFixedWidth(40)
        pagination_layout.addWidget(self.page_edit)
        
        jump_btn = QPushButton("跳转")
        jump_btn.setFont(QFont("Segoe UI", 9))
        jump_btn.setFixedWidth(40)
        jump_btn.clicked.connect(self._jump_page_handler)
        pagination_layout.addWidget(jump_btn)
        
        next_btn = QPushButton("下一页")
        next_btn.setFont(QFont("Segoe UI", 9))
        next_btn.setFixedWidth(60)
        next_btn.clicked.connect(lambda: self._goto_page(self.current_page + 1))
        pagination_layout.addWidget(next_btn)
        
        main_layout.addWidget(pagination_frame)

        result_frame = QFrame()
        result_frame.setStyleSheet("background-color: white; border: 1px solid #e2e8f0; border-radius: 4px; padding: 0px; margin:0px;")
        result_layout = QHBoxLayout(result_frame)
        result_layout.setContentsMargins(0,0,0,0)
        result_layout.setSpacing(0)
        
        self.result_tree = QTreeWidget()
        self.result_tree.setColumnCount(3)
        self.result_tree.setHeaderLabels(["类型", "操作", "链接"])
        self.result_tree.setColumnWidth(0, 80)
        self.result_tree.setColumnWidth(1, 150)
        self.result_tree.setColumnWidth(2, 850)
        self.result_tree.setStyleSheet("""
            QTreeWidget {background-color: white; color: #111827; border: none; font-size: 9pt; outline: none; padding:0;margin:0;}
            QTreeWidget::header {background-color: white; color: #374151; border: none; font-weight: bold;padding:0;margin:0;}
            QTreeWidget::item {border: none;padding:0;margin:0;}
            QTreeWidget::item:selected {background-color: #dbeafe; color: #1e40af; border-radius: 2px;}
        """)
        self.result_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.result_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.result_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.result_tree.customContextMenuRequested.connect(self._show_right_menu)
        self.right_menu = QMenu()
        self.copy_action = QAction("复制链接")
        self.copy_action.triggered.connect(self._copy_selected_link)
        self.open_action = QAction("在浏览器打开")
        self.open_action.triggered.connect(self._open_selected_link)
        self.right_menu.addAction(self.copy_action)
        self.right_menu.addAction(self.open_action)
        
        self.result_tree.itemDoubleClicked.connect(self._on_item_double_click)
        
        result_layout.addWidget(self.result_tree)
        main_layout.addWidget(result_frame)

    # ========== 快捷键绑定（原有代码，无修改） ==========
    def _bind_shortcuts(self):
        self.addAction(QAction("OpenSingle", self, shortcut="Ctrl+O", triggered=lambda: self._select_files(multi=False)))
        self.addAction(QAction("OpenMulti", self, shortcut="Ctrl+Shift+O", triggered=lambda: self._select_files(multi=True)))
        self.addAction(QAction("Export", self, shortcut="Ctrl+E", triggered=self._export_links))
        self.addAction(QAction("Clear", self, shortcut="Ctrl+R", triggered=self._clear_results))
        self.addAction(QAction("Quit", self, shortcut="Esc", triggered=self.close))

    # ========== 拖拽事件（原有代码，无修改） ==========
    def _on_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.file_status_label.setText("👉 松开鼠标即可解析文件（支持多文件）")
            self.set_transparent_no_border(self.file_status_label, "#3b82f6")

    def _on_drag_leave(self, event):
        if not self.file_paths:
            self.file_status_label.setText(f"✅ 等待选择/拖拽文件 | 上次路径：{os.path.basename(self.last_path) if self.last_path else '无'}")
            self.set_transparent_no_border(self.file_status_label)

    def _on_drag_drop(self, event):
        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls if os.path.isfile(url.toLocalFile()) and os.access(url.toLocalFile(), os.R_OK)]
        if not file_paths:
            self.file_status_label.setText("❌ 拖拽解析失败：无效文件")
            self.set_transparent_no_border(self.file_status_label, "#dc2626")
            return
        self.file_paths = file_paths
        self._update_file_status()
        self._save_last_path(file_paths[0])
        self._start_process_files()

    # ========== 文件选择与处理（原有代码，无修改） ==========
    def _select_files(self, multi=False):
        if self.process_thread and self.process_thread.isRunning():
            QMessageBox.information(self, "提示", "正在处理文件，请稍候...")
            return
        initial_dir = os.path.dirname(self.last_path) if self.last_path and os.path.exists(os.path.dirname(self.last_path)) else "."
        file_filter = "所有文件 (*.*);;data_1文件 (data_1)"
        if multi:
            file_paths, _ = QFileDialog.getOpenFileNames(self, "选择多个data_1文件", initial_dir, file_filter)
        else:
            file_path, _ = QFileDialog.getOpenFileName(self, "选择data_1文件", initial_dir, file_filter)
            file_paths = [file_path] if file_path else []
        if not file_paths:
            return
        self.file_paths = file_paths
        self._update_file_status()
        self._save_last_path(file_paths[0])
        self._start_process_files()

    def _update_file_status(self):
        if len(self.file_paths) == 1:
            self.file_status_label.setText(f"✅ 解析成功：{os.path.basename(self.file_paths[0])}")
        else:
            self.file_status_label.setText(f"✅ 解析成功：共 {len(self.file_paths)} 个文件")
        self.set_transparent_no_border(self.file_status_label, "#16a34a")

    def _start_process_files(self):
        self.process_thread = FileProcessThread(self.file_paths)
        # 补充原有代码中缺失的信号绑定（避免运行报错）
        self.process_thread.progress_signal.connect(lambda text, color: None)
        self.process_thread.result_signal.connect(lambda urls: setattr(self, 'all_matches', urls))
        self.process_thread.error_signal.connect(lambda err: QMessageBox.critical(self, "错误", err))
        self.process_thread.start()

    # ========== 补充原有代码中缺失的核心方法（避免运行报错） ==========
    def _copy_text(self, text):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "提示", "已复制到剪贴板")

    def _clear_results(self):
        self.all_matches = []
        self.filtered_matches = []
        self.current_page = 1
        self.result_tree.clear()
        self.page_info_label.setText("第 1 / 1 页 | 共 0 个链接")
        self.file_status_label.setText(f"✅ 等待选择/拖拽文件 | 上次路径：{os.path.basename(self.last_path) if self.last_path else '无'}")

    def _apply_filters(self, keep_page=False):
        # 过滤逻辑（原有核心逻辑）
        self.filtered_matches = []
        for url in self.all_matches:
            ext = url.split('.')[-1].lower()
            if (self.img_check.isChecked() and ext in IMAGE_EXTS) or \
               (self.video_check.isChecked() and ext in VIDEO_EXTS) or \
               (self.other_check.isChecked() and ext not in IMAGE_EXTS and ext not in VIDEO_EXTS):
                self.filtered_matches.append(url)
        # 更新分页和列表
        if not keep_page:
            self.current_page = 1
        self._render_page()

    def _render_page(self):
        self.result_tree.clear()
        total_pages = self._get_total_pages()
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_urls = self.filtered_matches[start_idx:end_idx]
        
        for url in page_urls:
            ext = url.split('.')[-1].lower()
            if ext in IMAGE_EXTS:
                type_text = "图片"
            elif ext in VIDEO_EXTS:
                type_text = "视频"
            else:
                type_text = "其他"
            item = QTreeWidgetItem([type_text, "", url])
            # 添加操作按钮（简化版）
            self.result_tree.addTopLevelItem(item)
        
        self.page_info_label.setText(f"第 {self.current_page} / {total_pages} 页 | 共 {len(self.filtered_matches)} 个链接")

    def _goto_page(self, page):
        total_pages = self._get_total_pages()
        if 1 <= page <= total_pages:
            self.current_page = page
            self._render_page()
            self.page_edit.setText(str(page))

    def _jump_page_handler(self):
        try:
            page = int(self.page_edit.text())
            self._goto_page(page)
        except ValueError:
            QMessageBox.warning(self, "提示", "请输入有效的页码")

    def _export_links(self):
        if not self.filtered_matches:
            QMessageBox.warning(self, "提示", "暂无可导出的链接")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "导出链接", "media_links.txt", "文本文件 (*.txt)")
        if save_path:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.filtered_matches))
            QMessageBox.information(self, "提示", f"已导出 {len(self.filtered_matches)} 个链接到 {save_path}")

    def _show_right_menu(self, pos):
        item = self.result_tree.itemAt(pos)
        if item:
            self.right_menu.exec(self.result_tree.mapToGlobal(pos))

    def _copy_selected_link(self):
        item = self.result_tree.currentItem()
        if item:
            self._copy_text(item.text(2))

    def _open_selected_link(self):
        item = self.result_tree.currentItem()
        if item:
            webbrowser.open(item.text(2))

    def _on_item_double_click(self, item, column):
        self._open_selected_link()

# ========== 程序入口（原有代码，无修改） ==========
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 禁用QT的默认退出行为（确保托盘逻辑生效）
    app.setQuitOnLastWindowClosed(False)
    window = MiHoYoMediaExtractor()
    window.show()
    sys.exit(app.exec())
