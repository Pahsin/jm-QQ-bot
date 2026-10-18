# QQ 漫画下载机器人（个人学习用途）

> 在 QQ 里发送漫画编号 → 机器人自动下载 → 合成 PDF 发回给你。
> **用途声明**：仅个人学习 Python 爬虫、机器人框架技术，不传播、不商业、不下载违规内容。

---

## ⚠️ 重要风险声明（务必先读）

1. **封号风险**：使用 NapCat 挂机器人登录 QQ 号，违反腾讯协议，可能导致账号被限制或封禁。请使用**小号**测试，自行承担风险。
2. **内容合规**：本项目基于 jmcomic（禁漫天堂漫画爬虫）。请勿下载、存储、传播任何侵权或违法违规内容。
3. **不要对外服务**：仅限个人本地使用，不要部署成公开/多用户服务。

---

## 一、整体架构

```
你的 QQ 号
   │  (登录)
   ▼
NapCat (OneBot 协议端)       ← 把你的 QQ 接入标准协议
   │  (反向 WebSocket)
   ▼
nonebot2 (机器人框架)        ← 监听消息、解析编号
   │
   ▼
jmcomic (下载库)             ← 下载漫画
   │
   ▼
合成 PDF → 发回 QQ
```

---

## 二、功能特性

- **QQ 命令触发**：发 `jm 123` 或 `@机器人 jm 123` 下载漫画
- **自动合成 PDF**：下载的图片按顺序合成为一个 PDF
- **自动发回**：PDF 通过 QQ 消息发回
- **自动清理**：发送成功后自动删除本地文件
- **回复冷却**：每用户 30 秒冷却，防止刷屏
- **群聊 @ 触发**：群里需 @ 机器人才响应（私聊直接触发）
- **GUI 控制台**：一键启动/停止，实时日志显示

---

## 三、环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.10+（完整安装版，需含 tkinter）|
| QQ | QQNT 新版（≥ 9.9.27）|
| NapCat | 独立 Shell 版（见下文）|
| 操作系统 | Windows（当前仅支持 Windows）|

---

## 四、安装部署

### 方式 A：一键安装器（推荐）

直接下载 `QQ-Manga-Bot-Installer.exe`（或运行 `python installer.py`），按向导操作：

1. **选择安装目录**
2. **NapCat**：二选一
   - 自动下载（国内镜像，自动切换 `gh-proxy.com` 等）
   - 我已下载好，选择路径（自动检索 `NapCatWinBootMain.exe`）
3. **QQNT**：二选一
   - 自动下载官方安装包
   - 我已安装 QQ，检索路径（自动检索 `QQ.exe`）
4. 点「开始安装」，完成后自动生成配置

### 方式 B：手动部署

### 1. 克隆项目

```bash
git clone <你的仓库地址>
cd jm-qq-bot
```

### 2. 安装 Python 依赖

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# 安装依赖
pip install -r requirements.txt
```

### 3. 安装 NapCat

1. 前往 [NapCatQQ Releases](https://github.com/NapNeko/NapCatQQ/releases) 下载 `NapCat.Shell.zip`（独立版）
   - 国内加速：`https://gh-proxy.com/https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip`
2. 解压到任意目录（如 `E:\NapCat.Shell`）
3. 确认本机已安装 **QQNT**（新版 QQ，≥ 9.9.27）

### 4. 配置

编辑 `config.json`，设置你的本机路径：

```json
{
  "bot_python": "你的项目目录\\venv\\Scripts\\python.exe",
  "napcat_dir": "你的 NapCat 目录",
  "napcat_qq_path": "你的 QQNT 安装路径\\QQ.exe",
  "qq_number": "你的机器人 QQ 号"
}
```

### 5. 启动

双击运行 GUI：

```bash
python main.py
```

在 GUI 里：
1. 点「启动 Bot」
2. 点「启动 NapCat」（会弹 UAC，点「是」）
3. 用手机 QQ 扫小号登录

---

## 五、使用说明

| 命令 | 功能 |
|------|------|
| `jm 123` | 下载本子 123，合成 PDF 发回 |
| `下载 456` | 同上 |
| `jmv 789` | 查看本子详情（标题/作者/页数），不下载 |

**私聊**：直接发命令即可。
**群聊**：需要 `@机器人 jm 123`。

---

## 六、项目结构

```
jm-qq-bot/
├── installer.py               # 一键安装向导（Tkinter）
├── main.py                    # GUI 主程序（Tkinter）
├── bot.py                     # nonebot 机器人入口
├── bot_settings.py            # 运行参数配置（白名单/黑名单/CD/@）
├── option.yml                 # jmcomic 下载配置
├── config.json                # GUI 配置（本机路径）
├── requirements.txt           # 依赖清单
├── pyproject.toml             # nonebot 项目配置
├── .env                       # nonebot 环境配置
├── src/plugins/jm_download.py # 核心插件（下载/合成PDF/发送）
├── build_exe.bat              # 打包脚本
└── README.md
```

---

## 七、打包成 exe（可选）

```bash
build_exe.bat
```

生成 `dist\QQ漫画机器人.exe`，双击即可运行（无需 Python 环境）。
注意：exe 只是 GUI 本体，NapCat 和 QQNT 仍需用户自行安装。

---

## 八、常见问题

**Q1：下载失败，报 "over proxy 127.0.0.1"？**
系统环境变量里的代理导致。程序已自动清理代理环境变量，如果仍失败，检查系统代理设置。

**Q2：群里 @ 机器人没反应？**
必须从 @ 列表里选中机器人（蓝色高亮），手打 @昵称 不算。

**Q3：NapCat 启动后 QQ 闪退？**
NapCat 需要管理员权限。点 UAC 弹窗的「是」，否则 DLL 注入失败。

**Q4：怎么换 QQ 号？**
重新运行 NapCat 扫码登录即可，配置文件里的 `qq_number` 也需更新。

---

## 免责声明

本项目仅供技术学习交流，请勿用于任何违法违规用途。使用者需自行承担因使用本项目产生的一切后果。
