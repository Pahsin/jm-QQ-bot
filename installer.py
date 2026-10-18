"""QQ 漫画机器人 - 一键安装器

功能：
1. 选择安装目录
2. NapCat：自动下载（国内镜像）或选择已有路径
3. QQNT：自动下载或选择已有路径
4. 自动生成配置，完成后一键启动

依赖：仅 tkinter + urllib + zipfile（Python 标准库）
"""

import os
import sys
import json
import shutil
import zipfile
import threading
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ============ 常量 ============
# NapCat 国内镜像（按优先级排序，自动切换）
NAPCAT_MIRRORS = [
    "https://gh-proxy.com/",
    "https://ghfast.top/",
    "https://mirror.ghproxy.com/",
    "",  # 空 = 直连 GitHub
]
NAPCAT_URL = "https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip"
NAPCAT_ZIP_NAME = "NapCat.Shell.zip"

# QQNT 无稳定直链（官方下载链接为 JS 动态生成），需用户自行安装后检索路径
QQNT_OFFICIAL_URL = "https://im.qq.com/pcqq"

# 应用配置文件名
APP_CONFIG = "config.json"
BOT_CONFIG = "bot_config.json"

# 需要复制到安装目录的项目文件（打包时用 --add-data 嵌入）
PROJECT_FILES = [
    "bot.py",
    "main.py",
    "bot_settings.py",
    "option.yml",
    "requirements.txt",
    "pyproject.toml",
    ".env",
]

# 主程序 exe（打包时嵌入，安装时复制到安装目录并创建桌面快捷方式）
MAIN_EXE_NAME = "QQ-Manga-Bot.exe"


def get_resource_dir() -> str:
    """返回项目文件所在目录（打包后为 _MEIPASS，开发时为脚本目录）。"""
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# ============ 下载工具 ============
def download_file(url: str, dest: str, progress_cb=None, cancel_flag=None) -> bool:
    """下载文件，支持进度回调和取消。返回是否成功。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                while True:
                    if cancel_flag and cancel_flag[0]:
                        return False
                    chunk = resp.read(1024 * 64)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total > 0:
                        progress_cb(downloaded, total)
        return True
    except Exception as e:
        return False


def download_napcat(dest_dir: str, progress_cb=None, cancel_flag=None) -> bool:
    """下载 NapCat（多镜像自动切换）。返回是否成功。"""
    zip_path = os.path.join(dest_dir, NAPCAT_ZIP_NAME)
    for mirror in NAPCAT_MIRRORS:
        url = mirror + NAPCAT_URL
        if progress_cb:
            progress_cb(0, 1, f"尝试镜像: {mirror or '直连'}")
        if download_file(url, zip_path, progress_cb, cancel_flag):
            # 验证 zip 有效
            if os.path.getsize(zip_path) > 100_000:  # NapCat.Shell.zip 约 33MB
                return True
        # 删除无效文件，尝试下一个镜像
        if os.path.exists(zip_path):
            os.remove(zip_path)
    return False


def unzip(zip_path: str, dest_dir: str) -> bool:
    """解压 zip。返回是否成功。"""
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest_dir)
        return True
    except Exception:
        return False


def find_napcat_launcher(directory: str) -> str | None:
    """在目录里检索 NapCat 启动器，返回路径或 None。"""
    target = "NapCatWinBootMain.exe"
    for root, dirs, files in os.walk(directory):
        # 跳过过深的目录
        depth = root[len(directory):].count(os.sep)
        if depth > 4:
            dirs[:] = []
            continue
        if target in files:
            return os.path.join(root, target)
    return None


def find_qq_exe(directory: str) -> str | None:
    """在目录里检索 QQ.exe（QQNT 启动器），返回路径或 None。"""
    for root, dirs, files in os.walk(directory):
        depth = root[len(directory):].count(os.sep)
        if depth > 4:
            dirs[:] = []
            continue
        # 找 QQ.exe，但要排除 versions 里的（那是子进程）
        if "QQ.exe" in files:
            path = os.path.join(root, "QQ.exe")
            # 判断是否是启动器（同级有 QQEX.exe 或 msvcp140.dll）
            parent = os.path.dirname(path)
            if os.path.exists(os.path.join(parent, "QQEX.exe")) or \
               os.path.exists(os.path.join(parent, "msvcp140.dll")):
                return path
    return None


def copy_project_files(dest_dir: str) -> bool:
    """复制项目文件到安装目录。返回是否成功。"""
    src_dir = get_resource_dir()
    try:
        # 复制单个文件
        for f in PROJECT_FILES:
            src = os.path.join(src_dir, f)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(dest_dir, f))
        # 复制 src 目录（含 plugins）
        src_src = os.path.join(src_dir, "src")
        if os.path.isdir(src_src):
            shutil.copytree(src_src, os.path.join(dest_dir, "src"), dirs_exist_ok=True)
        return True
    except Exception:
        return False


def copy_main_exe(dest_dir: str) -> bool:
    """复制主程序 exe 到安装目录。返回是否成功（不存在则返回 False，但不视为致命错误）。"""
    src_dir = get_resource_dir()
    src = os.path.join(src_dir, MAIN_EXE_NAME)
    if not os.path.exists(src):
        return False
    try:
        shutil.copy2(src, os.path.join(dest_dir, MAIN_EXE_NAME))
        return True
    except Exception:
        return False


def create_desktop_shortcut(target_exe: str, shortcut_name: str) -> bool:
    """在桌面创建快捷方式。返回是否成功。"""
    try:
        import subprocess
        desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
        if not os.path.isdir(desktop):
            # 尝试用注册表获取桌面路径
            desktop = os.path.join(os.environ.get("USERPROFILE", ""), "OneDrive", "Desktop")
        if not os.path.isdir(desktop):
            return False

        # 用 PowerShell 创建 .lnk（WScript.Shell）
        ps_script = (
            f"$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{os.path.join(desktop, shortcut_name)}.lnk'); "
            f"$s.TargetPath = '{target_exe}'; "
            f"$s.WorkingDirectory = '{os.path.dirname(target_exe)}'; "
            f"$s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return os.path.exists(os.path.join(desktop, shortcut_name + ".lnk"))
    except Exception:
        return False


def find_system_python() -> str | None:
    """查找系统里可用的 python.exe（打包成 exe 后 sys.executable 是 exe 本身，不能用）。"""
    candidates = []

    # 1. 环境变量里的 python
    if getattr(sys, "frozen", False):
        # 打包后，从 PATH 找
        import subprocess
        try:
            r = subprocess.run(["where", "python"], capture_output=True, text=True, timeout=10)
            for line in r.stdout.splitlines():
                line = line.strip()
                if line and line.lower().endswith("python.exe"):
                    candidates.append(line)
        except Exception:
            pass
    else:
        # 开发模式，直接用当前 python
        candidates.append(sys.executable)

    # 2. 常见安装路径
    for base in [os.environ.get("LOCALAPPDATA", ""), "C:\\Python", "C:\\Program Files\\Python"]:
        if not base or not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            depth = root[len(base):].count(os.sep)
            if depth > 3:
                dirs[:] = []
                continue
            if "python.exe" in files:
                candidates.append(os.path.join(root, "python.exe"))

    # 去重，返回第一个存在的
    seen = set()
    for c in candidates:
        c = c.strip().strip('"')
        if c and c not in seen and os.path.exists(c):
            return c
        seen.add(c)
    return None


def create_venv_and_install(install_dir: str, progress_cb=None, cancel_flag=None) -> tuple[bool, str]:
    """创建 venv 并安装依赖。返回 (是否成功, 说明)。"""
    import subprocess

    # 找到系统 python（打包后 sys.executable 不可用）
    python_exe = find_system_python()
    if not python_exe:
        return False, "未找到系统 Python，请先安装 Python 3.10+ 并加入 PATH"

    venv_dir = os.path.join(install_dir, "venv")

    # 1. 创建 venv
    if progress_cb:
        progress_cb(0, 1, f"正在用 {python_exe} 创建虚拟环境...")
    try:
        subprocess.run(
            [python_exe, "-m", "venv", venv_dir],
            check=True, capture_output=True, timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        return False, f"创建虚拟环境失败：{e}"

    # venv 里的 python
    venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        return False, "虚拟环境创建异常（未找到 python.exe）"

    # 2. pip install
    if progress_cb:
        progress_cb(0, 1, "正在安装依赖（可能需要几分钟）...")
    req_file = os.path.join(install_dir, "requirements.txt")
    try:
        proc = subprocess.Popen(
            [venv_python, "-m", "pip", "install", "-r", req_file,
             "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],  # 国内镜像
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in proc.stdout:
            if cancel_flag and cancel_flag[0]:
                proc.terminate()
                return False, "已取消"
            if "Successfully installed" in line:
                if progress_cb:
                    progress_cb(1, 1, "依赖安装完成")
        proc.wait(timeout=1800)
        if proc.returncode != 0:
            return False, "依赖安装失败（详见日志）"
    except Exception as e:
        return False, f"依赖安装出错：{e}"

    return True, "依赖安装完成"


# ============ 安装向导 ============
class InstallerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("QQ 漫画机器人 - 安装向导")
        self.root.geometry("680x640")
        self.root.minsize(680, 640)

        # 状态
        self.install_dir = ""
        self.napcat_source = ""  # "download" 或 "path"
        self.napcat_path = ""    # NapCat 目录（含 NapCatWinBootMain.exe 的父目录）
        self.qqnt_source = ""    # "download" 或 "path"
        self.qqnt_path = ""      # QQ.exe 路径
        self.cancel_flag = [False]

        self._build_ui()

    def _build_ui(self):
        # 顶部标题
        tk.Label(self.root, text="QQ 漫画机器人安装向导", font=("微软雅黑", 16, "bold")).pack(pady=(12, 2))
        tk.Label(self.root, text="个人学习用途 · 请勿传播违规内容", fg="#888").pack()

        # 可滚动内容区（Canvas + Scrollbar）
        canvas = tk.Canvas(self.root, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 主容器（放进滚动区）
        self.main = ttk.Frame(self.scroll_frame, padding=16)
        self.main.pack(fill="x")

        # ---- 第1步：安装目录 ----
        self.step1 = ttk.LabelFrame(self.main, text="第 1 步：选择安装目录", padding=10)
        self.step1.pack(fill="x", pady=6)

        row = ttk.Frame(self.step1)
        row.pack(fill="x")
        self.dir_var = tk.StringVar(value=os.path.join("D:\\", "QQ-Manga-Bot"))
        ttk.Entry(row, textvariable=self.dir_var, width=50).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="浏览", command=self._pick_dir).pack(side="left")

        # ---- 第2步：NapCat ----
        self.step2 = ttk.LabelFrame(self.main, text="第 2 步：NapCat（QQ 协议端）", padding=10)
        self.step2.pack(fill="x", pady=6)

        self.napcat_mode = tk.StringVar(value="download")
        ttk.Radiobutton(self.step2, text="自动下载（国内镜像）", variable=self.napcat_mode, value="download",
                        command=self._toggle_napcat).pack(anchor="w")
        ttk.Radiobutton(self.step2, text="我已下载好，选择路径", variable=self.napcat_mode, value="path",
                        command=self._toggle_napcat).pack(anchor="w")

        self.napcat_path_row = ttk.Frame(self.step2)
        self.napcat_path_row.pack(fill="x", pady=(4, 0))
        self.napcat_path_var = tk.StringVar()
        self.napcat_path_entry = ttk.Entry(self.napcat_path_row, textvariable=self.napcat_path_var, width=42)
        self.napcat_path_entry.pack(side="left", padx=(20, 6))
        self.napcat_path_btn = ttk.Button(self.napcat_path_row, text="浏览", command=self._pick_napcat)
        self.napcat_path_btn.pack(side="left")

        # ---- 第3步：QQNT ----
        self.step3 = ttk.LabelFrame(self.main, text="第 3 步：QQNT（新版 QQ）", padding=10)
        self.step3.pack(fill="x", pady=6)

        # 醒目的引导卡片（高亮背景）
        qqnt_guide = tk.Frame(self.step3, bg="#fff3cd", padx=10, pady=8, relief="solid", bd=1)
        qqnt_guide.pack(fill="x", pady=(0, 6))

        tk.Label(
            qqnt_guide,
            text="⚠ 请先安装新版 QQ（QQNT）",
            bg="#fff3cd", fg="#8a6d00",
            font=("微软雅黑", 11, "bold"),
        ).pack(anchor="w")

        tk.Label(
            qqnt_guide,
            text="QQNT 需要手动安装一次，无法自动下载（腾讯官方无稳定下载链接）。\n"
                 "请点击下方「打开官网」下载并安装新版 QQ（≥ 9.9.27），装好后再回来检索。",
            bg="#fff3cd", fg="#66512c", justify="left",
            font=("微软雅黑", 9),
        ).pack(anchor="w", pady=(4, 6))

        qqnt_btn_row = tk.Frame(qqnt_guide, bg="#fff3cd")
        qqnt_btn_row.pack(fill="x")
        self.btn_open_qq_site = tk.Button(
            qqnt_btn_row, text="① 打开官网下载 QQ", font=("微软雅黑", 10, "bold"),
            bg="#d9534f", fg="white", activebackground="#c9302c", activeforeground="white",
            relief="flat", padx=12, pady=4, cursor="hand2",
            command=self._open_qq_site,
        )
        self.btn_open_qq_site.pack(side="left")

        # 已装 QQ 的检索区
        tk.Label(
            self.step3,
            text="已安装 QQ？点下面检索：",
            font=("微软雅黑", 9), fg="#333",
        ).pack(anchor="w", pady=(0, 2))

        self.qqnt_path_row = ttk.Frame(self.step3)
        self.qqnt_path_row.pack(fill="x", pady=(2, 0))
        self.qqnt_path_var = tk.StringVar()
        self.qqnt_path_entry = ttk.Entry(self.qqnt_path_row, textvariable=self.qqnt_path_var, width=36)
        self.qqnt_path_entry.pack(side="left", padx=(0, 6))
        self.btn_auto_find = tk.Button(
            self.qqnt_path_row, text="② 自动检索", font=("微软雅黑", 10, "bold"),
            bg="#5cb85c", fg="white", activebackground="#4cae4c", activeforeground="white",
            relief="flat", padx=10, pady=2, cursor="hand2",
            command=self._auto_find_qqnt,
        )
        self.btn_auto_find.pack(side="left", padx=(0, 6))
        self.btn_manual_find = tk.Button(
            self.qqnt_path_row, text="③ 手动选择", font=("微软雅黑", 10),
            relief="flat", padx=10, pady=2, cursor="hand2",
            command=self._pick_qqnt,
        )
        self.btn_manual_find.pack(side="left")

        # ---- 底部固定区（不随内容滚动）----
        self.bottom_fixed = ttk.Frame(self.root, padding=(16, 8))
        self.bottom_fixed.pack(side="bottom", fill="x")

        self.progress = ttk.Progressbar(self.bottom_fixed, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 4))
        self.status_label = tk.Label(self.bottom_fixed, text="就绪", fg="#666", anchor="w")
        self.status_label.pack(fill="x")

        btn_row = ttk.Frame(self.bottom_fixed)
        btn_row.pack(fill="x", pady=(8, 0))
        self.btn_install = ttk.Button(btn_row, text="开始安装", command=self._start_install)
        self.btn_install.pack(side="right", ipadx=20, ipady=4)

        # 初始状态
        self._toggle_napcat()
        self._toggle_qqnt()

    # ---- UI 回调 ----
    def _pick_dir(self):
        d = filedialog.askdirectory(title="选择安装目录")
        if d:
            self.dir_var.set(d)

    def _toggle_napcat(self):
        if self.napcat_mode.get() == "path":
            self.napcat_path_entry.config(state="normal")
            self.napcat_path_btn.config(state="normal")
        else:
            self.napcat_path_entry.config(state="disabled")
            self.napcat_path_btn.config(state="disabled")

    def _toggle_qqnt(self):
        # QQNT 检索区始终可用
        self.qqnt_path_entry.config(state="normal")

    def _open_qq_site(self):
        """打开 QQ 官网下载页。"""
        import webbrowser
        webbrowser.open(QQNT_OFFICIAL_URL)

    def _auto_find_qqnt(self):
        """自动在常见路径检索 QQ.exe。"""
        candidates = [
            "D:\\QQ", "C:\\Program Files\\Tencent\\QQ", "C:\\Program Files (x86)\\Tencent\\QQ",
            "D:\\Program Files\\Tencent\\QQ", "C:\\Program Files\\QQ",
            "D:\\Program Files (x86)\\Tencent\\QQ",
        ]
        for c in candidates:
            if os.path.isdir(c):
                qq = find_qq_exe(c)
                if qq:
                    self.qqnt_path_var.set(qq)
                    messagebox.showinfo("检索成功", f"已自动找到 QQ.exe：\n{qq}")
                    return
        # 没找到，引导去官网
        messagebox.showwarning(
            "未找到 QQ",
            "未在常见路径找到 QQ。\n\n请先点击「① 打开官网下载 QQ」安装新版 QQ，\n装好后再点「② 自动检索」。",
        )

    def _pick_napcat(self):
        d = filedialog.askdirectory(title="选择 NapCat 目录")
        if not d:
            return
        launcher = find_napcat_launcher(d)
        if launcher:
            self.napcat_path_var.set(os.path.dirname(launcher))
            messagebox.showinfo("检索成功", f"已找到 NapCat 启动器：\n{launcher}")
        else:
            messagebox.showerror("未找到", "该目录下没有找到 NapCatWinBootMain.exe，请选择正确的 NapCat 解压目录。")

    def _pick_qqnt(self):
        d = filedialog.askdirectory(title="选择 QQ 安装目录")
        if not d:
            return
        qq = find_qq_exe(d)
        if qq:
            self.qqnt_path_var.set(qq)
            messagebox.showinfo("检索成功", f"已找到 QQ.exe：\n{qq}")
        else:
            # 允许直接选文件
            f = filedialog.askopenfilename(title="选择 QQ.exe", filetypes=[("QQ.exe", "QQ.exe")])
            if f and f.lower().endswith("qq.exe"):
                self.qqnt_path_var.set(f)
            else:
                messagebox.showerror("未找到", "未找到 QQ.exe。请选择 QQNT 安装目录（含 QQ.exe）。")

    # ---- 安装流程 ----
    def _start_install(self):
        self.install_dir = self.dir_var.get().strip()
        if not self.install_dir:
            messagebox.showerror("错误", "请选择安装目录。")
            return

        # 校验 NapCat
        if self.napcat_mode.get() == "path":
            self.napcat_path = self.napcat_path_var.get().strip()
            if not self.napcat_path:
                messagebox.showerror("错误", "请选择 NapCat 目录。")
                return
        # 校验 QQNT（只有检索路径模式）
        self.qqnt_path = self.qqnt_path_var.get().strip()
        if not self.qqnt_path:
            messagebox.showerror("错误", "请先检索或选择 QQ.exe 路径（需先安装新版 QQ）。")
            return

        self.btn_install.config(state="disabled")
        self.cancel_flag = [False]
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        """后台执行安装。"""
        try:
            os.makedirs(self.install_dir, exist_ok=True)

            # 第2步：NapCat
            if self.napcat_mode.get() == "download":
                self._set_status("正在下载 NapCat（国内镜像）...")
                if not download_napcat(self.install_dir, self._progress, self.cancel_flag):
                    self._install_failed("NapCat 下载失败，请改用「我已下载好」方式，手动下载后选择路径。")
                    return
                # 解压
                self._set_status("正在解压 NapCat...")
                napcat_dir = os.path.join(self.install_dir, "NapCat")
                if not unzip(os.path.join(self.install_dir, NAPCAT_ZIP_NAME), napcat_dir):
                    self._install_failed("NapCat 解压失败。")
                    return
                # 找到启动器所在目录
                launcher = find_napcat_launcher(napcat_dir)
                if not launcher:
                    self._install_failed("解压后未找到 NapCat 启动器。")
                    return
                self.napcat_path = os.path.dirname(launcher)
            else:
                self.napcat_path = self.napcat_path_var.get().strip()

            # 第3步：QQNT（用户已检索到路径）
            self.qqnt_path = self.qqnt_path_var.get().strip()

            # 第4步：复制项目文件
            self._set_status("正在复制项目文件...")
            if not copy_project_files(self.install_dir):
                self._install_failed("项目文件复制失败。")
                return

            # 第5步：创建 venv 并安装依赖
            self._set_status("正在创建虚拟环境并安装依赖（可能需要几分钟）...")
            ok, msg = create_venv_and_install(self.install_dir, self._progress, self.cancel_flag)
            if not ok:
                self._install_failed(f"依赖安装失败：{msg}")
                return
            self._set_status(msg)

            # 生成配置
            self._set_status("正在生成配置...")
            self._write_configs()

            # 复制主程序 exe + 创建桌面快捷方式
            self._set_status("正在复制主程序并创建桌面快捷方式...")
            self.main_exe_installed = copy_main_exe(self.install_dir)
            self.shortcut_created = False
            if self.main_exe_installed:
                main_exe_path = os.path.join(self.install_dir, MAIN_EXE_NAME)
                self.shortcut_created = create_desktop_shortcut(main_exe_path, "QQ漫画机器人")

            self._install_done()
        except Exception as e:
            self._install_failed(f"安装出错：{e}")

    def _write_configs(self):
        """生成 config.json 和 bot_config.json。"""
        # 主配置
        config = {
            "bot_python": os.path.join(self.install_dir, "venv", "Scripts", "python.exe"),
            "bot_script": os.path.join(self.install_dir, "bot.py"),
            "napcat_dir": self.napcat_path,
            "napcat_launcher": "NapCatWinBootMain.exe",
            "napcat_hook": "NapCatWinBootHook.dll",
            "napcat_qq_path": self.qqnt_path,
            "qq_number": "",
        }
        with open(os.path.join(self.install_dir, APP_CONFIG), "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        # 机器人运行配置（默认）
        bot_config = {
            "cooldown_seconds": 30,
            "require_at": True,
            "whitelist": [],
            "blacklist": [],
            "enable_whitelist": False,
            "enable_blacklist": True,
        }
        with open(os.path.join(self.install_dir, BOT_CONFIG), "w", encoding="utf-8") as f:
            json.dump(bot_config, f, ensure_ascii=False, indent=2)

    def _progress(self, done: int, total: int, extra: str = ""):
        """进度回调（在工作线程调用）。"""
        if total > 0:
            pct = min(100, int(done / total * 100))
            self.root.after(0, lambda: self.progress.config(value=pct))
        if extra:
            self.root.after(0, lambda: self.status_label.config(text=extra))

    def _set_status(self, text: str):
        self.root.after(0, lambda: self.status_label.config(text=text))

    def _install_failed(self, msg: str):
        self.root.after(0, lambda: self._show_failed(msg))

    def _show_failed(self, msg: str):
        self.btn_install.config(state="normal")
        self.status_label.config(text="安装失败", fg="red")
        messagebox.showerror("安装失败", msg)

    def _install_done(self):
        self.root.after(0, self._show_done)

    def _show_done(self):
        self.progress.config(value=100)
        self.status_label.config(text="安装完成", fg="green")
        self.btn_install.config(state="normal")

        msg = (
            f"安装完成！\n\n"
            f"安装目录：{self.install_dir}\n"
            f"NapCat：{self.napcat_path}\n"
            f"QQNT：{self.qqnt_path}\n\n"
        )
        if getattr(self, "main_exe_installed", False):
            msg += "✅ 主程序已复制到安装目录\n"
        if getattr(self, "shortcut_created", False):
            msg += "✅ 桌面快捷方式已创建\n"
        msg += "\n后续：\n1. 双击桌面「QQ漫画机器人」快捷方式启动\n2. 首次启动 NapCat 扫码登录小号"
        messagebox.showinfo("完成", msg)


def main():
    root = tk.Tk()
    InstallerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
