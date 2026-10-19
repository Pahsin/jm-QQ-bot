"""QQ 漫画机器人 - 整合 GUI 主程序

功能：
- 一键启动/停止 nonebot 机器人
- 一键启动/停止 NapCat（QQ 协议端）
- 实时显示两个组件的日志
- 清理代理环境变量（避免 jmcomic 走错代理）

依赖：仅 tkinter + subprocess（Python 标准库），
所以任何完整安装的 Python 都能运行本 GUI。
"""

import os
import json
import sys
import subprocess
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# 项目根目录
# 关键：打包成 exe 后，__file__ 指向 PyInstaller 临时解压目录，不是真实目录。
# 所以要用 sys.executable（exe 所在目录）作为 BASE_DIR，这样 config.json 和
# venv、bot.py 等都能在 exe 旁边正确找到。
if getattr(sys, "frozen", False):
    # 打包后：exe 所在目录
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # 开发模式：脚本所在目录
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# 默认配置
DEFAULT_CONFIG = {
    # nonebot 机器人
    "bot_python": os.path.join(BASE_DIR, "venv", "Scripts", "python.exe"),
    "bot_script": os.path.join(BASE_DIR, "bot.py"),
    # NapCat
    "napcat_dir": "E:\\NapCat.Shell",
    "napcat_launcher": "NapCatWinBootMain.exe",
    "napcat_hook": "NapCatWinBootHook.dll",
    "napcat_qq_path": "D:\\QQ\\QQ.exe",
    # 通用
    "qq_number": "3607932740",
}

# 需要清理的代理环境变量（避免 jmcomic 走错代理）
PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")


def load_config() -> dict:
    """加载配置，不存在则用默认值。"""
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg: dict):
    """保存配置。"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def clean_env() -> dict:
    """返回清理代理后的环境变量 dict。"""
    env = os.environ.copy()
    for k in PROXY_KEYS:
        env.pop(k, None)
    return env


class ProcessManager:
    """管理一个子进程，捕获 stdout/stderr 到队列。"""

    def __init__(self, log_queue: queue.Queue, name: str):
        self.log_queue = log_queue
        self.name = name
        self.proc: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, cmd: list[str], cwd: str | None = None):
        if self.running:
            return
        env = clean_env()
        self.proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.log_queue.put((self.name, f"[启动] {' '.join(cmd)}\n"))
        self.thread = threading.Thread(target=self._read_output, daemon=True)
        self.thread.start()

    def _read_output(self):
        """持续读取子进程输出。"""
        assert self.proc is not None
        for line in self.proc.stdout:
            self.log_queue.put((self.name, line))
        self.log_queue.put((self.name, f"[进程退出] code={self.proc.returncode}\n"))

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.log_queue.put((self.name, "[已停止]\n"))


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.cfg = load_config()
        self.log_queue = queue.Queue()

        self.bot_mgr = ProcessManager(self.log_queue, "Bot")
        self.napcat_mgr = ProcessManager(self.log_queue, "NapCat")

        self._build_ui()
        self.root.after(100, self._poll_logs)

    def _build_ui(self):
        self.root.title("QQ 漫画机器人 - 控制台")
        self.root.geometry("820x620")

        # 顶部：标题
        title = tk.Label(self.root, text="QQ 漫画下载机器人", font=("微软雅黑", 16, "bold"))
        title.pack(pady=(12, 4))
        subtitle = tk.Label(self.root, text="个人学习用途 · 请勿用于传播违规内容", fg="#888")
        subtitle.pack()

        # 组件控制区
        ctrl = ttk.LabelFrame(self.root, text="组件控制", padding=10)
        ctrl.pack(fill="x", padx=12, pady=8)

        # Bot 行
        bot_row = ttk.Frame(ctrl)
        bot_row.pack(fill="x", pady=4)
        ttk.Label(bot_row, text="机器人 (nonebot)", width=18).pack(side="left")
        self.bot_status = ttk.Label(bot_row, text="● 未运行", foreground="#888")
        self.bot_status.pack(side="left", padx=6)
        self.btn_bot = ttk.Button(bot_row, text="启动 Bot", command=self.toggle_bot)
        self.btn_bot.pack(side="right")

        # NapCat 行
        nap_row = ttk.Frame(ctrl)
        nap_row.pack(fill="x", pady=4)
        ttk.Label(nap_row, text="NapCat (QQ协议端)", width=18).pack(side="left")
        self.nap_status = ttk.Label(nap_row, text="● 未运行", foreground="#888")
        self.nap_status.pack(side="left", padx=6)
        self.btn_nap = ttk.Button(nap_row, text="启动 NapCat", command=self.toggle_napcat)
        self.btn_nap.pack(side="right")

        # 提示
        tip = tk.Label(
            ctrl,
            text="提示：先启动 Bot，再启动 NapCat。NapCat 首次启动需扫码登录小号。",
            fg="#666", font=("微软雅黑", 9),
        )
        tip.pack(anchor="w", pady=(6, 0))

        # 日志区
        log_frame = ttk.LabelFrame(self.root, text="运行日志", padding=6)
        log_frame.pack(fill="both", expand=True, padx=12, pady=8)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=18, font=("Consolas", 9), state="disabled", wrap="word"
        )
        self.log_text.pack(fill="both", expand=True)

        # 底部：清空日志 + 配置按钮
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(bottom, text="清空日志", command=self.clear_log).pack(side="left")
        ttk.Button(bottom, text="机器人设置", command=self.open_bot_settings).pack(side="right", padx=6)
        ttk.Button(bottom, text="路径配置", command=self.open_config_dialog).pack(side="right")

    # ---- 日志 ----
    def _poll_logs(self):
        try:
            while True:
                name, line = self.log_queue.get_nowait()
                self._append_log(name, line)
        except queue.Empty:
            pass
        self._refresh_status()
        self.root.after(100, self._poll_logs)

    def _append_log(self, name: str, line: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _refresh_status(self):
        # Bot 状态
        if self.bot_mgr.running:
            self.bot_status.config(text="● 运行中", foreground="green")
            self.btn_bot.config(text="停止 Bot")
        else:
            self.bot_status.config(text="● 未运行", foreground="#888")
            self.btn_bot.config(text="启动 Bot")
        # NapCat 状态
        if self.napcat_mgr.running:
            self.nap_status.config(text="● 运行中", foreground="green")
            self.btn_nap.config(text="停止 NapCat")
        else:
            self.nap_status.config(text="● 未运行", foreground="#888")
            self.btn_nap.config(text="启动 NapCat")

    # ---- Bot 启停 ----
    def toggle_bot(self):
        if self.bot_mgr.running:
            self.bot_mgr.stop()
        else:
            py = self.cfg["bot_python"]
            script = self.cfg["bot_script"]
            if not os.path.exists(py):
                messagebox.showerror("错误", f"找不到 Python: {py}\n请先安装依赖或修改配置。")
                return
            if not os.path.exists(script):
                messagebox.showerror("错误", f"找不到 bot.py: {script}")
                return
            self.bot_mgr.start([py, script], cwd=BASE_DIR)

    # ---- NapCat 启停 ----
    def toggle_napcat(self):
        if self.napcat_mgr.running:
            self.napcat_mgr.stop()
            # NapCat 需要额外清理 QQ 进程
            self._kill_qq()
        else:
            nap_dir = self.cfg["napcat_dir"]
            launcher = os.path.join(nap_dir, self.cfg["napcat_launcher"])
            hook = os.path.join(nap_dir, self.cfg["napcat_hook"])
            qq_path = self.cfg["napcat_qq_path"]

            if not os.path.exists(launcher):
                messagebox.showerror("错误", f"找不到 NapCat 启动器: {launcher}\n请在配置里设置正确的 NapCat 目录。")
                return
            if not os.path.exists(qq_path):
                messagebox.showerror("错误", f"找不到 QQ: {qq_path}\n请确认 QQNT 已安装，或在配置里修改路径。")
                return

            # NapCat 需要管理员权限，通过 powershell 提权启动
            cmd = [
                "powershell", "-NoProfile", "-Command",
                f"Start-Process -FilePath '{launcher}' -ArgumentList '{qq_path}','{hook}' -Verb RunAs"
            ]
            self.napcat_mgr.start(cmd, cwd=nap_dir)
            self.log_queue.put(("NapCat", "[提示] 已请求提权启动，请在弹出的 UAC 窗口点击「是」，然后用手机 QQ 扫码登录。\n"))

    def _kill_qq(self):
        """停止 NapCat 时清理 QQ 进程。"""
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "QQ.exe"],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass

    # ---- 配置对话框 ----
    def open_config_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("配置")
        dlg.geometry("600x320")
        dlg.transient(self.root)
        dlg.grab_set()

        fields = {}
        labels = [
            ("bot_python", "Bot Python 路径"),
            ("napcat_dir", "NapCat 目录"),
            ("napcat_qq_path", "QQNT 路径 (QQ.exe)"),
            ("qq_number", "机器人 QQ 号"),
        ]
        for i, (key, label) in enumerate(labels):
            ttk.Label(dlg, text=label).grid(row=i, column=0, sticky="e", padx=8, pady=6)
            var = tk.StringVar(value=str(self.cfg.get(key, "")))
            ttk.Entry(dlg, textvariable=var, width=60).grid(row=i, column=1, sticky="w", padx=8, pady=6)
            fields[key] = var

        def save():
            for key, var in fields.items():
                self.cfg[key] = var.get().strip()
            save_config(self.cfg)
            dlg.destroy()
            messagebox.showinfo("提示", "配置已保存")

        ttk.Button(dlg, text="保存", command=save).grid(row=len(labels), column=1, sticky="e", pady=12)

    # ---- 机器人设置对话框 ----
    def open_bot_settings(self):
        """打开机器人运行参数设置对话框（白名单/黑名单/CD/@开关）。"""
        import bot_settings

        dlg = tk.Toplevel(self.root)
        dlg.title("机器人设置")
        dlg.geometry("560x480")
        dlg.transient(self.root)
        dlg.grab_set()

        cfg = bot_settings.load_config()

        # 第一行：CD + @ 开关
        row1 = ttk.Frame(dlg)
        row1.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Label(row1, text="回复冷却(秒)").pack(side="left")
        cd_var = tk.StringVar(value=str(cfg.get("cooldown_seconds", 30)))
        ttk.Entry(row1, textvariable=cd_var, width=8).pack(side="left", padx=6)

        at_var = tk.BooleanVar(value=bool(cfg.get("require_at", True)))
        ttk.Checkbutton(row1, text="群聊需 @ 机器人", variable=at_var).pack(side="left", padx=12)

        # 白名单区
        wl_frame = ttk.LabelFrame(dlg, text="白名单", padding=8)
        wl_frame.pack(fill="both", expand=True, padx=12, pady=6)

        wl_enable = tk.BooleanVar(value=bool(cfg.get("enable_whitelist", False)))
        ttk.Checkbutton(wl_frame, text="启用白名单（只允许下列 QQ 号使用）", variable=wl_enable).pack(anchor="w")

        wl_text = tk.Text(wl_frame, height=5, font=("Consolas", 10))
        wl_text.pack(fill="both", expand=True, pady=4)
        wl_text.insert("1.0", "\n".join(str(x) for x in cfg.get("whitelist", [])))
        ttk.Label(wl_frame, text="每行一个 QQ 号", foreground="#888").pack(anchor="w")

        # 黑名单区
        bl_frame = ttk.LabelFrame(dlg, text="黑名单", padding=8)
        bl_frame.pack(fill="both", expand=True, padx=12, pady=6)

        bl_enable = tk.BooleanVar(value=bool(cfg.get("enable_blacklist", True)))
        ttk.Checkbutton(bl_frame, text="启用黑名单（下列 QQ 号禁止使用）", variable=bl_enable).pack(anchor="w")

        bl_text = tk.Text(bl_frame, height=5, font=("Consolas", 10))
        bl_text.pack(fill="both", expand=True, pady=4)
        bl_text.insert("1.0", "\n".join(str(x) for x in cfg.get("blacklist", [])))
        ttk.Label(bl_frame, text="每行一个 QQ 号", foreground="#888").pack(anchor="w")

        def save():
            # 解析 CD
            try:
                cd = int(cd_var.get().strip())
                if cd < 0:
                    cd = 0
            except ValueError:
                messagebox.showerror("错误", "冷却时间必须是数字（秒）")
                return

            # 解析白名单/黑名单
            def parse_ids(text_widget):
                raw = text_widget.get("1.0", "end").strip()
                ids = [line.strip() for line in raw.splitlines() if line.strip()]
                return ids

            new_cfg = {
                "cooldown_seconds": cd,
                "require_at": at_var.get(),
                "enable_whitelist": wl_enable.get(),
                "whitelist": parse_ids(wl_text),
                "enable_blacklist": bl_enable.get(),
                "blacklist": parse_ids(bl_text),
            }
            bot_settings.save_config(new_cfg)
            dlg.destroy()
            messagebox.showinfo("提示", "机器人设置已保存。\n若机器人正在运行，需重启 Bot 生效。")

        ttk.Button(dlg, text="保存设置", command=save).pack(pady=12)

    def on_close(self):
        """关闭窗口时清理子进程。"""
        self.bot_mgr.stop()
        self.napcat_mgr.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
