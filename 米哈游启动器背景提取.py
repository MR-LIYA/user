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
    QSystemTrayIcon  # ✅ 保留导入，无需注释，解耦核心
)
from PyQt6.QtCore import Qt, QMimeData, QThread, pyqtSignal, QTimer
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

# ========== 主窗口类（完美解耦 | 一键禁用托盘 | 仅需注释1行） ==========
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
        self.tray_icon = None  # ✅ 保留声明，无需注释，智能判断
        
        # 初始化UI + 绑定快捷键
        self._init_ui()
        self._bind_shortcuts()
        self._calculate_items_per_page()
        QTimer.singleShot(100, self._calculate_items_per_page)

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

    # ========== 初始化UI（完整无删减，无修改） ==========
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

    # ========== 快捷键绑定（完整，无修改） ==========
    def _bind_shortcuts(self):
        self.addAction(QAction("OpenSingle", self, shortcut="Ctrl+O", triggered=lambda: self._select_files(multi=False)))
        self.addAction(QAction("OpenMulti", self, shortcut="Ctrl+Shift+O", triggered=lambda: self._select_files(multi=True)))
        self.addAction(QAction("Export", self, shortcut="Ctrl+E", triggered=self._export_links))
        self.addAction(QAction("Clear", self, shortcut="Ctrl+R", triggered=self._clear_results))
        self.addAction(QAction("Quit", self, shortcut="Esc", triggered=self.close))

    # ========== 拖拽事件（完整，无修改） ==========
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

    # ========== 文件选择与处理（完整，无修改） ==========
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
        self.process_thread.progress_signal.connect(self._update_process_progress)
        self.process_thread.result_signal.connect(self._handle_process_result)
        self.process_thread.error_signal.connect(self._handle_process_error)
        self.process_thread.start()

    def _update_process_progress(self, text, color):
        self.file_status_label.setText(text)
        self.set_transparent_no_border(self.file_status_label, color)

    def _handle_process_result(self, valid_urls):
        self.all_matches = valid_urls
        self.current_page = 1
        self._calculate_items_per_page()
        self._apply_filters()
        if not valid_urls:
            QMessageBox.information(self, "提示", "未在选中文件中找到有效媒体链接！")

    def _handle_process_error(self, error):
        self.file_status_label.setText(f"❌ 处理失败：{error[:30]}")
        self.set_transparent_no_border(self.file_status_label, "#dc2626")
        QMessageBox.critical(self, "处理失败", f"错误信息：{error}")

    # ========== 过滤与分页（完整，无修改） ==========
    def _apply_filters(self, keep_page=False):
        if not keep_page:
            self.current_page = 1
        self.filtered_matches = []
        for url in self.all_matches:
            ext = self._get_extension(url)
            is_img = ext in IMAGE_EXTS
            is_video = ext in VIDEO_EXTS
            if is_img and self.img_check.isChecked():
                self.filtered_matches.append(url)
            elif is_video and self.video_check.isChecked():
                self.filtered_matches.append(url)
            elif not (is_img or is_video) and self.other_check.isChecked():
                self.filtered_matches.append(url)
        self.filtered_matches.sort(key=lambda x: (0 if self._get_extension(x) in IMAGE_EXTS else 1 if self._get_extension(x) in VIDEO_EXTS else 2))
        total_pages = self._get_total_pages()
        self.page_info_label.setText(f"第 {self.current_page} / {total_pages} 页 | 共 {len(self.filtered_matches)} 个链接")
        self.page_edit.setText(str(self.current_page))
        self._show_current_page()

    def _get_extension(self, url):
        try:
            parsed = urlparse(url)
            path = parsed.path
            ext = path.split(".")[-1].lower() if "." in path else ""
            return ext.split("?")[0].split("#")[0]
        except:
            ext = url.split(".")[-1].lower() if "." in url else ""
            return ext.split("?")[0].split("#")[0]

    def _show_current_page(self):
        self.result_tree.clear()
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.filtered_matches))
        current_items = self.filtered_matches[start_idx:end_idx]
        for url in current_items:
            ext = self._get_extension(url)
            if ext in IMAGE_EXTS:
                file_type = "图片"
                action_text = "双击预览 / 右键复制"
            elif ext in VIDEO_EXTS:
                file_type = "视频"
                action_text = "双击播放 / 右键复制"
            else:
                file_type = "其他"
                action_text = "无操作"
            item = QTreeWidgetItem([file_type, action_text, url])
            self.result_tree.addTopLevelItem(item)

    def _goto_page(self, page):
        total_pages = self._get_total_pages()
        if page < 1 and self.current_page == 1:
            QMessageBox.information(self, "提示", "当前已是【第一页】，无法向前翻页！")
            return
        if page > total_pages and self.current_page == total_pages:
            QMessageBox.information(self, "提示", "当前已是【最后一页】，无法向后翻页！")
            return
        if 1 <= page <= total_pages:
            self.current_page = page
            self._apply_filters(keep_page=True)

    def _jump_page_handler(self):
        input_text = self.page_edit.text().strip()
        total_pages = self._get_total_pages()
        if not input_text.isdigit():
            QMessageBox.warning(self, "输入错误", "请输入【正整数】页码进行跳转！")
            self.page_edit.setText(str(self.current_page))
            self.page_edit.selectAll()
            return
        target_page = int(input_text)
        if target_page < 1:
            QMessageBox.information(self, "跳转提示", f"页码不能小于1，已自动跳转到【第1页】！")
            self._goto_page(1)
        elif target_page > total_pages:
            QMessageBox.information(self, "跳转提示", f"页码超出范围（共{total_pages}页），已自动跳转到【最后一页】！")
            self._goto_page(total_pages)
        else:
            self._goto_page(target_page)
        self.page_edit.selectAll()

    # ========== 工具方法（完整，无修改） ==========
    def _clear_results(self):
        self.all_matches = []
        self.filtered_matches = []
        self.current_page = 1
        self.result_tree.clear()
        self.page_info_label.setText("第 1 / 1 页 | 共 0 个链接")
        self.page_edit.setText("1")
        self.file_status_label.setText(f"✅ 等待选择/拖拽文件 | 上次路径：{os.path.basename(self.last_path) if self.last_path else '无'}")
        self.set_transparent_no_border(self.file_status_label)

    def _export_links(self):
        if not self.filtered_matches:
            QMessageBox.information(self, "提示", "暂无可导出的链接！")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "导出链接", "米哈游媒体链接.txt", "文本文件 (*.txt);;所有文件 (*.*)")
        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(self.filtered_matches))
                QMessageBox.information(self, "成功", f"已导出 {len(self.filtered_matches)} 个链接到：{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "失败", f"导出失败：{str(e)}")

    def _copy_text(self, text):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "提示", "已复制到剪贴板！")

    def _copy_selected_link(self):
        selected_items = self.result_tree.selectedItems()
        if selected_items:
            self._copy_text(selected_items[0].text(2))

    def _open_selected_link(self):
        selected_items = self.result_tree.selectedItems()
        if selected_items:
            webbrowser.open(selected_items[0].text(2))

    def _show_right_menu(self, pos):
        if self.result_tree.selectedItems():
            self.right_menu.exec(self.result_tree.mapToGlobal(pos))

    def _on_item_double_click(self, item, column):
        self._open_selected_link()

    # ========== ✅ 智能兼容：关闭事件（无需修改，自动适配托盘开启/禁用） ==========
    def closeEvent(self, event):
        """智能判断：有托盘则隐藏窗口，无托盘则彻底关闭程序"""
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept() # 禁用托盘时，点击X直接彻底关闭

    # ========== ✅ 智能兼容：最小化事件（无需修改，自动适配托盘开启/禁用） ==========
    def changeEvent(self, event):
        """智能判断：有托盘则最小化隐藏，无托盘则正常最小化到任务栏"""
        if event.type() == event.Type.WindowStateChange:
            if self.windowState() == Qt.WindowState.WindowMinimized and self.tray_icon:
                self.hide()
                self.tray_icon.setVisible(True)
        super().changeEvent(event)

    # ========== ✅ 【核心封装】独立的托盘初始化方法（所有托盘逻辑全在这里） ==========
    def _init_system_tray(self, app_icon):
        """系统托盘核心逻辑，统一封装，外部仅需一行调用"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(app_icon)
        self.tray_icon.setToolTip(APP_TITLE)

        # 托盘右键菜单
        tray_menu = QMenu(self)
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(lambda: [self.show(), self.raise_(), self.activateWindow()])
        exit_action = QAction("彻底退出程序", self)
        exit_action.triggered.connect(lambda: [self.tray_icon.hide(), QApplication.quit()])
        tray_menu.addAction(show_action)
        tray_menu.addAction(exit_action)

        # 托盘左键单击 → 显示窗口
        self.tray_icon.activated.connect(lambda reason: [self.show(), self.raise_(), self.activateWindow()] if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    # ========== ✅ 唯一入口：图标设置 + 托盘开关 ==========
    def set_all_app_icons(self, icon_file):
        """
        窗口+任务栏图标：必显示（不受托盘影响）
        系统托盘图标：由下方【一行调用代码】控制开关
        """
        if not os.path.exists(icon_file):
            QMessageBox.warning(self, "提示", f"图标文件 {icon_file} 不存在，跳过图标设置")
            return
        
        try:
            app_icon = QIcon(icon_file)
            self.setWindowIcon(app_icon)  # 窗口+任务栏图标，永久生效
            # self._init_system_tray(app_icon) #系统托盘
            
        except Exception as e:
            QMessageBox.warning(self, "图标加载失败", f"图标设置出错：{str(e)}")

# ========== ✅ 程序入口（无任何修改，直接运行） ==========
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    
    window = MiHoYoMediaExtractor()
    # 图标路径正常写，无需改动
    window.set_all_app_icons(icon_file=r"D:\HP\Pictures\图标\神里凌华.ico")
    
    window.show()
    sys.exit(app.exec())
