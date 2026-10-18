"""QQ 漫画编号下载机器人插件（个人学习用途）。

功能：
- 发 "jm 123" / "下载 123" / "本子 123" → 下载漫画到本地，并打包成 zip 发回
- 发 "jmv 123" → 查看本子详情（只查不下载）

依赖：jmcomic、nonebot2、nonebot-adapter-onebot
"""

import os
import re
import time
import shutil
import traceback
import logging

# 关键：在 import jmcomic 之前清除代理环境变量，强制直连
# （curl-cffi 会读取 HTTP_PROXY/HTTPS_PROXY，系统注入的内部代理会导致连接失败）
for _proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_proxy_key, None)

import jmcomic
from nonebot import on_regex, on_command
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent

# 基础目录（项目根目录）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OPTION_FILE = os.path.join(_BASE_DIR, "option.yml")
DOWNLOAD_DIR = os.path.join(_BASE_DIR, "downloads")

# 引入配置模块（bot_settings.py 在项目根目录）
sys_path_added = False
if _BASE_DIR not in __import__("sys").path:
    __import__("sys").path.insert(0, _BASE_DIR)
import bot_settings

# 日志
logger = logging.getLogger("jm_bot")
_handler = logging.FileHandler(os.path.join(_BASE_DIR, "jm_bot.log"), encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)
logger.setLevel(logging.DEBUG)


def extract_id(text: str) -> str | None:
    """从文本中提取数字编号。"""
    m = re.search(r"(\d+)", text)
    return m.group(1) if m else None


def is_mentioned(event: MessageEvent) -> bool:
    """判断消息是否 @ 了机器人。

    规则：
    - 私聊：直接放行（无需 @）
    - 群聊：若配置 require_at=True 则需 @；否则放行
    """
    # 私聊：直接放行
    if not isinstance(event, GroupMessageEvent):
        return True
    # 群聊：根据配置决定是否必须 @
    cfg = bot_settings.load_config()
    if not cfg.get("require_at", True):
        return True  # 不需要 @，直接放行
    return bool(getattr(event, "to_me", False))


# 回复冷却（CD）：从配置动态读取
_last_trigger_time: dict[str, float] = {}


def check_cooldown(user_id: str) -> tuple[bool, int]:
    """检查是否在冷却中。返回 (是否冷却中, 剩余秒数)。"""
    cooldown = bot_settings.load_config().get("cooldown_seconds", 30)
    if cooldown <= 0:
        return False, 0  # CD 关闭
    now = time.time()
    last = _last_trigger_time.get(user_id, 0)
    remain = cooldown - (now - last)
    if remain > 0:
        return True, int(remain) + 1
    return False, 0


def mark_trigger(user_id: str):
    """记录触发时间。"""
    _last_trigger_time[user_id] = time.time()


def check_user_permission(user_id: str) -> tuple[bool, str]:
    """检查用户权限（黑名单/白名单）。返回 (是否允许, 拒绝原因)。"""
    return bot_settings.check_permission(user_id)


def pack_album(album_id: str) -> str:
    """把下载好的本子图片按顺序合成一个 PDF，返回 PDF 路径。"""
    from PIL import Image

    album_dir = os.path.join(DOWNLOAD_DIR, album_id)
    if not os.path.isdir(album_dir):
        raise FileNotFoundError(f"下载目录不存在: {album_dir}")

    # 收集图片，按文件名排序
    exts = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
    images = sorted(
        [f for f in os.listdir(album_dir) if f.lower().endswith(exts)]
    )
    if not images:
        raise FileNotFoundError(f"目录里没有图片: {album_dir}")

    # 打开所有图片并转成 RGB（PDF 不支持 alpha 通道）
    pil_images = []
    for name in images:
        path = os.path.join(album_dir, name)
        img = Image.open(path)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        pil_images.append(img)

    # 第一张图保存，其余追加
    pdf_path = os.path.join(DOWNLOAD_DIR, f"{album_id}.pdf")
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    first, *rest = pil_images
    first.save(pdf_path, "PDF", save_all=True, append_images=rest, resolution=100.0)

    # 关闭所有图片释放内存
    for img in pil_images:
        img.close()

    return pdf_path


def cleanup_album(album_id: str):
    """发送成功后清理本地文件（图片目录 + PDF）。"""
    album_dir = os.path.join(DOWNLOAD_DIR, album_id)
    pdf_path = os.path.join(DOWNLOAD_DIR, f"{album_id}.pdf")
    # 删除图片目录
    if os.path.isdir(album_dir):
        shutil.rmtree(album_dir, ignore_errors=True)
        logger.info(f"已删除图片目录: {album_dir}")
    # 删除 PDF
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        logger.info(f"已删除 PDF: {pdf_path}")


# ---- 下载本子 ----
download = on_regex(
    r"(?:jm|下载|本子|下載)\s*(\d+)",
    priority=10,
    block=True,
)


@download.handle()
async def handle_download(event: MessageEvent):
    user_id = event.get_user_id()

    # 黑名单/白名单权限检查
    allowed, reason = check_user_permission(user_id)
    if not allowed:
        logger.info(f"拒绝下载请求: 来自 {user_id}（{reason}）")
        if reason == "blacklist":
            await download.finish("你已被拉黑，无法使用此功能。")
        else:
            await download.finish("你没有权限使用此功能。")
        return

    # 群聊需 @ 机器人
    if not is_mentioned(event):
        logger.info(f"群聊未 @ 机器人，忽略: 来自 {user_id}")
        return

    # CD 冷却检查
    in_cd, remain = check_cooldown(user_id)
    if in_cd:
        await download.finish(f"冷却中，请 {remain} 秒后再试~")

    album_id = extract_id(event.get_plaintext())
    logger.info(f"收到下载请求: album_id={album_id}, 来自 {user_id}")
    if not album_id:
        await download.finish("没识别到编号哦，试试：@我 jm 123")

    # 标记触发时间
    mark_trigger(user_id)

    await download.send(f"收到，开始下载本子 {album_id}，请稍候...")

    import asyncio

    def _sync_download():
        logger.info(f"开始下载 album_id={album_id}")
        option = jmcomic.create_option_by_file(OPTION_FILE)
        return jmcomic.download_album(album_id, option)

    def _sync_pack():
        return pack_album(album_id)

    try:
        loop = asyncio.get_running_loop()
        # 下载
        await loop.run_in_executor(None, _sync_download)
        logger.info(f"下载成功 album_id={album_id}")
        # 合成 PDF
        pdf_path = await loop.run_in_executor(None, _sync_pack)
        logger.info(f"PDF 合成成功: {pdf_path}")
    except Exception as e:
        logger.error(f"下载/合成PDF失败 album_id={album_id}: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        await download.finish(f"下载失败: {type(e).__name__}: {e}")
        return

    # 发送文件
    try:
        file_msg = MessageSegment(type="file", data={"file": pdf_path})
        await download.send(f"本子 {album_id} 下载完成，共 {_count_images(album_id)} 张图，已合成 PDF：")
        await download.send(file_msg)
        logger.info(f"文件已发送: {pdf_path}")
    except Exception as e:
        logger.error(f"发送文件失败: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        await download.send(f"PDF 合成完成，但发送失败（{type(e).__name__}: {e}）。文件在本地：{pdf_path}")
        await download.finish()
        return

    # 发送成功后清理本地文件
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, cleanup_album, album_id)
        logger.info(f"已清理本地文件 album_id={album_id}")
    except Exception as e:
        logger.error(f"清理失败 album_id={album_id}: {e}")

    await download.finish(f"本子 {album_id} 下载完成 ✅")


def _count_images(album_id: str) -> int:
    album_dir = os.path.join(DOWNLOAD_DIR, album_id)
    if not os.path.isdir(album_dir):
        return 0
    return len([f for f in os.listdir(album_dir) if f.lower().endswith((".jpg", ".png", ".webp", ".jpeg"))])


# ---- 查看详情：jmv 123 ----
query = on_command("jmv", priority=10, block=True)


@query.handle()
async def handle_query(event: MessageEvent):
    user_id = event.get_user_id()

    # 黑名单/白名单权限检查
    allowed, reason = check_user_permission(user_id)
    if not allowed:
        logger.info(f"拒绝查询请求: 来自 {user_id}（{reason}）")
        if reason == "blacklist":
            await query.finish("你已被拉黑，无法使用此功能。")
        else:
            await query.finish("你没有权限使用此功能。")
        return

    # 群聊需 @ 机器人
    if not is_mentioned(event):
        logger.info(f"群聊未 @ 机器人，忽略 jmv: 来自 {user_id}")
        return

    # CD 冷却检查
    in_cd, remain = check_cooldown(user_id)
    if in_cd:
        await query.finish(f"冷却中，请 {remain} 秒后再试~")

    arg = str(event.get_message()).strip()
    arg = re.sub(r"^jmv\s*", "", arg, flags=re.I)
    album_id = extract_id(arg)
    logger.info(f"收到查询请求: album_id={album_id}, 来自 {user_id}")

    if not album_id:
        await query.finish("用法：@我 jmv 123")

    # 标记触发时间
    mark_trigger(user_id)

    import asyncio

    def _sync_query():
        option = jmcomic.create_option_by_file(OPTION_FILE)
        client = option.new_jm_client()
        return client.get_album_detail(album_id)

    try:
        loop = asyncio.get_running_loop()
        album = await loop.run_in_executor(None, _sync_query)
        logger.info(f"查询成功 album_id={album_id}")
    except Exception as e:
        logger.error(f"查询失败 album_id={album_id}: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        await query.finish(f"查询失败: {type(e).__name__}: {e}")
        return

    lines = [
        f"标题: {album.title}",
        f"ID: {album.id}",
        f"作者: {', '.join(album.author)}",
        f"更新: {album.update_date}",
        f"总页数: {album.page_count}",
        f"点赞: {album.likes}",
        f"章节数: {len(album.episode_list)}",
    ]
    await query.finish("\n".join(lines))
