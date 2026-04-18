from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent

# 使用 on_command 替代 on_message
# 只有精准匹配到 "ping" 指令时才会触发并拦截
ping = on_command("ping", priority=10, block=True)

@ping.handle()
async def handle_ping():
    await ping.finish("pong")
