"""QQ 漫画编号下载机器人 —— 启动入口。

运行方式（在项目根目录）：
    ./venv/Scripts/python.exe bot.py
"""

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

# 初始化 NoneBot，加载配置和插件
nonebot.init()

# 注册 OneBot V11 适配器
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

# 加载插件
nonebot.load_from_toml("pyproject.toml")

if __name__ == "__main__":
    nonebot.run()
