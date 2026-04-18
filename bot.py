import nonebot
import os
import sys

# 强制日志输出到文件
if not os.path.exists("logs"):
    os.makedirs("logs")

# 使用 loguru 输出文件
nonebot.logger.add("logs/bot.log", rotation="10 MB", level="DEBUG")

# 初始化 NoneBot
nonebot.init()
config = nonebot.get_driver().config
config.apscheduler_config = {
    "apscheduler.jobstores.default": {
        "type": "sqlalchemy",
        "url": "sqlite:///data/jobs.sqlite"
    }
}

# 注册 OneBot.V11 适配器
try:
    from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
    driver = nonebot.get_driver()
    driver.register_adapter(ONEBOT_V11Adapter)
except Exception as e:
    nonebot.logger.error(f"加载 Adapter 失败: {e}")

# 加载内置插件 echo，用于 ping-pong 测试连通性
nonebot.load_builtin_plugins("echo")

# 准备插件目录
if not os.path.exists("src/plugins"):
    os.makedirs("src/plugins")

# 加载自定义插件和第三方插件
nonebot.load_plugin("nonebot_plugin_apscheduler")
nonebot.load_plugins("src/plugins")

if __name__ == "__main__":
    nonebot.run()
