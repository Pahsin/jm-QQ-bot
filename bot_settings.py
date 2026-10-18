"""机器人运行参数配置模块。

提供白名单、黑名单、回复冷却、是否响应 @ 等运行参数的读写，
以及统一的权限判断函数。供插件和 GUI 共同使用。
"""

import os
import json

# 配置文件的绝对路径（项目根目录）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_BASE_DIR, "bot_config.json")

# 默认配置
DEFAULT_CONFIG = {
    "cooldown_seconds": 30,          # 回复冷却时间（秒），0 表示不限制
    "require_at": True,              # 群聊是否需要 @ 机器人
    "whitelist": [],                 # 白名单 QQ 号列表，空 = 不限制
    "blacklist": [],                 # 黑名单 QQ 号列表
    "enable_whitelist": False,       # 是否启用白名单
    "enable_blacklist": True,        # 是否启用黑名单
}


def load_config() -> dict:
    """加载配置，不存在则用默认值并创建。"""
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
        except Exception:
            pass
    return cfg


def save_config(cfg: dict):
    """保存配置。"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def check_permission(user_id: str) -> tuple[bool, str]:
    """判断用户是否有权限触发机器人。

    返回 (是否允许, 拒绝原因)。拒绝原因为空字符串表示允许。
    判断顺序：黑名单 → 白名单。
    """
    cfg = load_config()
    uid = str(user_id)

    # 黑名单优先
    if cfg.get("enable_blacklist", True) and uid in cfg.get("blacklist", []):
        return False, "blacklist"

    # 白名单
    if cfg.get("enable_whitelist", False):
        wl = cfg.get("whitelist", [])
        if uid not in wl:
            return False, "whitelist"

    return True, ""
