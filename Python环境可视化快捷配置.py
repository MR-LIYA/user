import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, Label, Entry, Button, Scrollbar, Toplevel, ttk
import threading
import ctypes

# -------------------------- 底层修复：彻底消除tk空白窗口/闪烁 --------------------------
# 强制Windows DPI感知（解决高分屏适配）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# 全局单例根窗口（全程隐藏，仅作为主界面载体）
_root_instance = None

def get_singleton_root():
    """获取单例根窗口（初始化时完全隐藏，无任何显示/闪烁）"""
    global _root_instance
    if _root_instance is None:
        # 创建根窗口但完全隐藏，杜绝tk空白窗口
        _root_instance = tk.Tk()
        _root_instance.withdraw()  # 彻底隐藏根窗口
        _root_instance.attributes("-alpha", 0.0)  # 全透明
        _root_instance.update_idletasks()  # 冻结绘制
    return _root_instance

def fix_tkinter_visibility():
    """隐藏控制台（仅win32），不影响主界面"""
    if sys.platform.startswith('win32'):
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass

# -------------------------- 核心工具函数 --------------------------
def center_toplevel(window, parent):
    """将Toplevel窗口相对于父窗口居中"""
    window.update_idletasks()
    parent_x = parent.winfo_x()
    parent_y = parent.winfo_y()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()
    win_w = window.winfo_width()
    win_h = window.winfo_height()
    x = parent_x + (parent_w - win_w) // 2
    y = parent_y + (parent_h - win_h) // 2
    window.geometry(f"{win_w}x{win_h}+{x}+{y}")

def center_window(window, width, height):
    """窗口居中（仅计算位置，无多余绘制）"""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

def run_command(args, **kwargs):
    """执行命令并隐藏控制台窗口（仅Windows）"""
    if sys.platform.startswith('win32'):
        # 添加Windows特有的创建标志，隐藏子进程控制台
        kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
    return subprocess.run(args,** kwargs)

def check_module_installed(python_path, module_name):
    """检查指定Python环境是否安装了目标模块"""
    try:
        result = run_command(
            [python_path, "-c", f"import {module_name}"],
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="ignore"
        )
        return True
    except subprocess.CalledProcessError:
        return False

def find_and_move_pip_autoremove(python_path):
    """
    自动查找pip-autoremove.py并移动到正确路径：
    - 全局环境：Scripts → Lib\\site-packages
    - 虚拟环境：Scripts → Lib\\site-packages
    """
    python_dir = os.path.dirname(python_path)
    scripts_dir = os.path.join(python_dir, "Scripts")
    lib_dir = os.path.join(python_dir, "Lib")
    site_packages_dir = os.path.join(lib_dir, "site-packages")

    # 查找pip-autoremove.py
    source_file = None
    if os.path.exists(scripts_dir):
        for file in os.listdir(scripts_dir):
            if file.lower() == "pip-autoremove.py":
                source_file = os.path.join(scripts_dir, file)
                break
    if not source_file:
        return False, "未找到 pip-autoremove.py 文件（Scripts目录下）"

    # 判断环境类型
    is_venv = False
    if os.path.exists(site_packages_dir):
        if "Program Files" not in python_dir and "AppData" not in python_dir:
            is_venv = True

    # 目标路径
    target_dir = site_packages_dir if is_venv else lib_dir
    target_file = os.path.join(target_dir, "pip-autoremove.py")

    # 移动文件
    try:
        if os.path.exists(target_file):
            os.remove(target_file)
        shutil.move(source_file, target_dir)
        if os.path.exists(target_file):
            return True, f"成功移动到：{target_dir}"
        else:
            return False, "文件移动后未找到目标文件"
    except PermissionError:
        return False, "权限不足！请以管理员身份运行"
    except Exception as e:
        return False, f"移动失败：{str(e)}"

# -------------------------- 进度条窗口类 --------------------------
class ProgressWindow:
    def __init__(self, parent, total, title="操作中"):
        self.top = Toplevel(parent.root)
        self.top.title(title)
        self.top.geometry("400x100")
        self.top.resizable(False, False)
        center_toplevel(self.top, parent.root)
        self.top.transient(parent.root)
        self.top.grab_set()

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.top,
            variable=self.progress_var,
            maximum=total,
            mode="determinate"
        )
        self.progress_bar.pack(fill=tk.X, padx=20, pady=20)

        # 当前操作提示
        self.label = Label(self.top, text="准备中...", font=("微软雅黑", 10))
        self.label.pack(pady=5)

        self.current = 0
        self.total = total

    def update(self, text):
        """更新进度和提示"""
        self.current += 1
        self.progress_var.set(self.current)
        self.label.config(text=text)
        self.top.update_idletasks()

    def close(self):
        """关闭窗口"""
        self.top.destroy()

# -------------------------- 安装/升级窗口类 --------------------------
class InstallUpgradeWindow:
    def __init__(self, parent, python_path, run_pip_func, reset_batch_func, add_batch_func, show_batch_func):
        self.parent = parent
        self.python_path = python_path
        self.run_pip_func = run_pip_func
        self.reset_batch_func = reset_batch_func
        self.add_batch_func = add_batch_func
        self.show_batch_func = show_batch_func

        # 获取勾选的包（用于升级操作）
        self.selected_pkgs = self.get_selected_packages()

        self.top = Toplevel(parent.root)
        self.top.title("安装/升级Python包")
        self.top.geometry("520x220")
        self.top.resizable(False, False)
        center_toplevel(self.top, parent.root)
        self.top.transient(parent.root)
        self.top.grab_set()

        # 窗口布局
        self.setup_ui()

    def get_selected_packages(self):
        """获取勾选的包列表"""
        selected = []
        if hasattr(self.parent, 'tree') and self.parent.tree.get_children():
            for item in self.parent.tree.get_children():
                values = self.parent.tree.item(item, "values")
                if values[0] == "✅":
                    pkg_name = values[1].strip()
                    selected.append(pkg_name)
        return selected

    def setup_ui(self):
        # 1. 包名+版本输入区域
        if self.selected_pkgs:
            Label(self.top, text=f"已选择包: {', '.join(self.selected_pkgs)}，请输入版本号（格式：包名==版本号）：", 
                  font=("微软雅黑", 10)).pack(pady=8)
        else:
            Label(self.top, text="包名（单个/多个用逗号分隔）+ 版本号（格式：包名==版本号，如 requests==2.31.0）：", 
                  font=("微软雅黑", 10)).pack(pady=8)
            
        self.pkg_entry = Entry(self.top, font=("微软雅黑", 12), width=55)
        self.pkg_entry.pack(padx=20, pady=5)
        
        # 如果有选中的包，自动填充
        if self.selected_pkgs and len(self.selected_pkgs) == 1:
            self.pkg_entry.insert(0, self.selected_pkgs[0] + "==")
        
        self.pkg_entry.focus()

        # 2. 镜像源选择
        self.mirror_var = tk.BooleanVar(value=True)
        mirror_check = tk.Checkbutton(
            self.top, 
            text="使用清华镜像源", 
            variable=self.mirror_var,
            font=("微软雅黑", 10)
        )
        mirror_check.pack(pady=5)

        # 3. 操作按钮
        btn_frame = tk.Frame(self.top)
        btn_frame.pack(pady=15)
        
        execute_btn = Button(
            btn_frame, 
            text="执行安装/升级", 
            command=self.execute_operation,
            font=("微软雅黑", 10),
            width=15
        )
        execute_btn.pack(side=tk.LEFT, padx=10)
        
        cancel_btn = Button(
            btn_frame, 
            text="取消", 
            command=self.top.destroy,
            font=("微软雅黑", 10),
            width=10
        )
        cancel_btn.pack(side=tk.LEFT, padx=10)

    def execute_operation(self):
        """执行安装或升级操作"""
        # 获取输入内容
        pkg_input = self.pkg_entry.get().strip()
        if not pkg_input:
            messagebox.showwarning("警告", "请输入包名！")
            return
        
        # 拆分包名（兼容单个/多个，支持版本号）
        packages = [p.strip() for p in pkg_input.split(",") if p.strip()]
        if not packages:
            messagebox.showwarning("警告", "请输入有效的包名！")
            return
        
        # 获取镜像源选择
        use_mirror = self.mirror_var.get()
        
        # 关闭窗口
        self.top.destroy()

        # 单个包处理
        if len(packages) == 1:
            self.run_pip_func(
                "install",
                packages[0], 
                use_mirror=use_mirror
            )
        # 多个包处理（带进度条）
        else:
            self.reset_batch_func()
            progress_win = ProgressWindow(self.parent, len(packages), "批量处理中")
            # 批量执行
            for pkg in packages:
                self.run_pip_func(
                    "install", 
                    pkg, 
                    use_mirror=use_mirror,
                    auto_refresh=False,
                    is_batch=True,
                    progress_win=progress_win
                )
            # 最后刷新列表并显示结果
            self.parent.root.after(1000, self.parent.show_packages)
            self.parent.root.after(1000, self.show_batch_func, "安装/升级")

# -------------------------- 主程序类 --------------------------
class PipManagerApp:
    def __init__(self, root):
        self.root = root
        # 1. 根窗口作为主界面，先完全冻结
        self.root.title("Python 环境管理工具")
        self.root.resizable(False, False)
        self.root.attributes("-alpha", 0.0)  # 全透明（无闪烁）
        self.root.attributes("-disabled", True)  # 禁用交互
        
        # 2. 一次性初始化所有UI（无多次重绘）
        self.python_path = None
        self.packages = []
        self.batch_results = {"success": [], "failed": []}
        self.batch_lock = threading.Lock()
        # 核心包列表（禁止卸载）
        self.core_packages = ["pip", "setuptools"]

        self.setup_ui()
        
        # 3. 窗口居中（仅计算位置，无绘制）
        center_window(self.root, 700, 500)
        
        # 4. 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 5. 分步显示主界面（零闪烁）
        # 先启用交互，再恢复透明度，无任何中间态
        self.root.after(100, lambda: self.root.attributes("-disabled", False))
        self.root.after(150, lambda: self.root.attributes("-alpha", 1.0))
        self.root.deiconify()  # 显示根窗口（此时已完成所有绘制）

    def setup_ui(self):
        # 路径选择行
        path_frame = tk.Frame(self.root)
        path_frame.pack(pady=10, fill=tk.X)
        path_frame.grid_columnconfigure(0, weight=0)
        path_frame.grid_columnconfigure(1, weight=1)
        path_frame.grid_columnconfigure(2, weight=0)
        
        tk.Label(path_frame, text="python解释器路径：", font=("微软雅黑", 12)).grid(row=0, column=0, padx=(20, 5), sticky="e")
        self.path_entry = tk.Entry(path_frame, font=("微软雅黑", 12))
        self.path_entry.grid(row=0, column=1, padx=5, sticky="ew")
        select_btn = tk.Button(path_frame, text="选择", command=self.select_python, font=("微软雅黑", 12))
        select_btn.grid(row=0, column=2, padx=(5, 20))

        # 操作按钮行
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10, fill=tk.X)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(3, weight=1)
        
        self.install_upgrade_btn = tk.Button(btn_frame, text="安装/升级", command=self.open_install_upgrade_window, font=("微软雅黑", 12))
        self.install_upgrade_btn.grid(row=0, column=1, padx=5)
        self.uninstall_btn = tk.Button(btn_frame, text="卸载", command=self.choose_uninstall_method, font=("微软雅黑", 12))
        self.uninstall_btn.grid(row=0, column=2, padx=5)

        # 包列表区域
        list_frame = tk.Frame(self.root)
        list_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        
        # 垂直滚动条
        v_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview样式
        style = ttk.Style()
        style.configure("Treeview", rowheight=25, font=("微软雅黑", 10))
        style.configure("Treeview.Heading", font=("微软雅黑", 10, "bold"))
        
        # 创建Treeview（带复选框）
        self.tree = ttk.Treeview(
            list_frame, 
            columns=["Select", "Package", "Version"],
            show="headings",
            yscrollcommand=v_scroll.set,
            selectmode="extended"
        )
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.config(command=self.tree.yview)
        
        # 设置列属性
        self.tree.column("Select", width=50, anchor="center")
        self.tree.column("Package", width=300, anchor="w")
        self.tree.column("Version", width=200, anchor="w")
        self.tree.heading("Select", text="选择")
        self.tree.heading("Package", text="包名")
        self.tree.heading("Version", text="版本")
        
        # 绑定勾选事件
        self.tree.bind("<Button-1>", self.toggle_checkbox)

    def select_python(self):
        """选择Python解释器并自动显示包列表"""
        python_path = filedialog.askopenfilename(
            title="选择Python解释器",
            filetypes=[("Python Executable", "python.exe"), ("All Files", "*.*")]
        )
        if python_path and os.path.exists(python_path):
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, python_path)
            self.python_path = python_path
            self.show_packages()

    def toggle_checkbox(self, event):
        """切换复选框状态"""
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            row = self.tree.identify_row(event.y)
            column = self.tree.identify_column(event.x)
            if column == "#1":
                current_value = self.tree.item(row, "values")[0]
                new_value = "✅" if current_value != "✅" else ""
                self.tree.item(row, values=(new_value, self.tree.item(row, "values")[1], self.tree.item(row, "values")[2]))

    def show_packages(self):
        """显示已安装的包列表"""
        if not self.python_path:
            messagebox.showwarning("警告", "请先选择Python解释器！")
            return

        # 清空现有列表
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 异步获取包列表
        def get_packages():
            try:
                result = run_command(
                    [self.python_path, "-m", "pip", "list", "--format=freeze"],
                    capture_output=True,
                    encoding="utf-8",
                    errors="ignore"
                )
                packages = []
                for line in result.stdout.splitlines():
                    if "==" in line:
                        name, version = line.split("==", 1)
                        packages.append((name.strip(), version.strip()))
                self.packages = packages
                self.root.after(0, self.update_package_tree)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"获取包列表失败：{str(e)}"))

        threading.Thread(target=get_packages, daemon=True).start()

    def update_package_tree(self):
        """更新包列表UI"""
        for name, version in self.packages:
            self.tree.insert("", tk.END, values=("", name, version))

    def open_install_upgrade_window(self):
        """打开安装/升级窗口"""
        if not self.python_path:
            messagebox.showwarning("警告", "请先选择Python解释器！")
            return
        
        InstallUpgradeWindow(
            self,
            self.python_path,
            self.run_pip_command,
            self.reset_batch_results,
            self.add_batch_result,
            self.show_batch_results
        )

    def choose_uninstall_method(self):
        """选择卸载方式"""
        if not self.python_path:
            messagebox.showwarning("警告", "请先选择Python解释器！")
            return
            
        # 获取勾选的包
        selected_pkgs = []
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if values[0] == "✅":
                pkg_name = values[1].strip()
                selected_pkgs.append(pkg_name)
        
        if not selected_pkgs:
            messagebox.showwarning("警告", "请先勾选要卸载的包！")
            return
            
        # 检查核心包
        core_in_selected = [pkg for pkg in selected_pkgs if pkg in self.core_packages]
        if core_in_selected:
            messagebox.showwarning("警告", f"核心包 {', '.join(core_in_selected)} 不支持卸载！")
            return
        
        # 创建卸载方式选择窗口
        method_window = Toplevel(self.root)
        method_window.title("选择卸载方式")
        method_window.geometry("300x170")
        center_toplevel(method_window, self.root)
        method_window.transient(self.root)
        method_window.grab_set()

        Label(method_window, text="请选择卸载方式：", font=("微软雅黑", 10)).pack(pady=15)
        uninstall_method = tk.StringVar(value="pip")
        
        tk.Radiobutton(
            method_window, 
            text="pip uninstall（仅卸载包本身）", 
            variable=uninstall_method, 
            value="pip",
            font=("微软雅黑", 10)
        ).pack(anchor=tk.W, padx=20)
        
        tk.Radiobutton(
            method_window, 
            text="pip-autoremove（卸载包及无用依赖）", 
            variable=uninstall_method, 
            value="autoremove",
            font=("微软雅黑", 10)
        ).pack(anchor=tk.W, padx=20, pady=5)
        
        # 确认按钮
        btn_frame = tk.Frame(method_window)
        btn_frame.pack(pady=10)
        
        def confirm_method():
            method = uninstall_method.get()
            method_window.destroy()
            self.execute_uninstall(selected_pkgs, method)
        
        Button(btn_frame, text="确认", command=confirm_method, font=("微软雅黑", 10), width=10).pack(side=tk.LEFT, padx=10)
        Button(btn_frame, text="取消", command=method_window.destroy, font=("微软雅黑", 10), width=10).pack(side=tk.LEFT)

    def execute_uninstall(self, selected_pkgs, method):
        """执行卸载操作"""
        confirm = messagebox.askyesno(
            "确认卸载", 
            f"确定要使用{'pip uninstall' if method == 'pip' else 'pip-autoremove'}卸载以下包吗？\n{', '.join(selected_pkgs)}"
        )
        if not confirm:
            return

        self.reset_batch_results()
        progress_win = ProgressWindow(self, len(selected_pkgs), "卸载中")
        
        for pkg in selected_pkgs:
            try:
                if method == "pip":
                    cmd = [self.python_path, "-m", "pip", "uninstall", "-y", pkg]
                else:
                    # 检查并修复pip-autoremove
                    if not check_module_installed(self.python_path, "pip_autoremove"):
                        success, msg = find_and_move_pip_autoremove(self.python_path)
                        if not success:
                            self.add_batch_result(pkg, False, msg)
                            progress_win.update(f"卸载失败: {pkg} (缺少pip-autoremove)")
                            continue
                    cmd = [self.python_path, "-m", "pip_autoremove", pkg, "-y"]
                
                # 执行卸载命令
                result = run_command(
                    cmd,
                    capture_output=True,
                    encoding="utf-8",
                    errors="ignore"
                )
                
                if result.returncode == 0:
                    self.add_batch_result(pkg, True)
                    progress_win.update(f"已卸载: {pkg}")
                else:
                    error_msg = result.stderr[:50] if result.stderr else "未知错误"
                    self.add_batch_result(pkg, False, error_msg)
                    progress_win.update(f"卸载失败: {pkg}")
            except Exception as e:
                self.add_batch_result(pkg, False, str(e))
                progress_win.update(f"卸载异常: {pkg}")
        
        progress_win.close()
        self.show_packages()
        self.show_batch_results("卸载")

    def run_pip_command(self, operation, package, use_mirror=True, auto_refresh=True, is_batch=False, progress_win=None):
        """执行pip安装/升级命令"""
        try:
            cmd = [self.python_path, "-m", "pip", operation, package]
            # 添加清华镜像源
            if use_mirror:
                cmd.extend(["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"])
            
            # 执行命令
            result = run_command(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="ignore"
            )
            
            pkg_name = package.split("==")[0]
            if result.returncode == 0:
                if is_batch:
                    self.add_batch_result(package, True)
                    if progress_win:
                        progress_win.update(f"成功: {pkg_name}")
                else:
                    messagebox.showinfo("成功", f"{pkg_name} 安装/升级成功！")
                    if auto_refresh:
                        self.show_packages()
            else:
                error_msg = result.stderr[:100] if result.stderr else "未知错误"
                if is_batch:
                    self.add_batch_result(package, False, error_msg)
                    if progress_win:
                        progress_win.update(f"失败: {pkg_name}")
                else:
                    messagebox.showerror("失败", f"{pkg_name} 操作失败:\n{error_msg}")
        except Exception as e:
            error_msg = str(e)
            if is_batch:
                self.add_batch_result(package, False, error_msg)
                if progress_win:
                    progress_win.update(f"异常: {package}")
            else:
                messagebox.showerror("异常", f"{package} 操作异常:\n{error_msg}")

    def reset_batch_results(self):
        """重置批量操作结果"""
        with self.batch_lock:
            self.batch_results = {"success": [], "failed": []}

    def add_batch_result(self, package, success, message=""):
        """添加批量操作结果"""
        with self.batch_lock:
            if success:
                self.batch_results["success"].append(package)
            else:
                self.batch_results["failed"].append(f"{package} ({message})")

    def show_batch_results(self, operation):
        """显示批量操作结果"""
        success_list = self.batch_results["success"]
        failed_list = self.batch_results["failed"]
        
        msg = f"{operation}结果：\n"
        msg += f"成功: {len(success_list)} 个\n"
        msg += f"失败: {len(failed_list)} 个\n\n"
        
        if success_list:
            msg += "成功列表：\n" + "\n".join(success_list) + "\n\n"
        if failed_list:
            msg += "失败列表：\n" + "\n".join(failed_list)
        
        result_window = Toplevel(self.root)
        result_window.title(f"{operation}结果")
        result_window.geometry("500x400")
        center_toplevel(result_window, self.root)
        result_window.transient(self.root)
        result_window.grab_set()

        # 结果文本框
        text_widget = tk.Text(result_window, font=("微软雅黑", 10), wrap=tk.WORD)
        text_widget.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, msg)
        text_widget.config(state=tk.DISABLED)

        # 关闭按钮
        Button(result_window, text="关闭", command=result_window.destroy, font=("微软雅黑", 10), width=10).pack(pady=10)

    def on_close(self):
        """平滑关闭主界面"""
        self.root.attributes("-alpha", 0.0)
        self.root.after(50, self.root.destroy)

if __name__ == "__main__":
    # 隐藏控制台，修复tk显示
    fix_tkinter_visibility()
    
    # 获取完全隐藏的根窗口
    root = get_singleton_root()
    
    # 创建并显示主界面
    app = PipManagerApp(root)
    
    # 进入主循环
    root.mainloop()
