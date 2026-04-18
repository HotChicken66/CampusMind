from nonebot import on_request, on_message
from nonebot.adapters.onebot.v11 import FriendRequestEvent, PrivateMessageEvent
from nonebot.rule import Rule
from nonebot.log import logger

# 1. 自动拒绝好友请求拦截器
friend_req = on_request(priority=1, block=True)

@friend_req.handle()
async def reject_friend(event: FriendRequestEvent):
    # 拒绝好友请求
    logger.info(f"拦截到来自 {event.user_id} 的加好友请求，已自动拒绝。")
    await event.reject()

# 2. 私聊消息拦截器
async def is_private(event: PrivateMessageEvent) -> bool:
    return True

# 针对私聊应用 Rule 拦截
private_msg_interceptor = on_message(rule=Rule(is_private), priority=1, block=True)

@private_msg_interceptor.handle()
async def ignore_private(event: PrivateMessageEvent):
    logger.info(f"拦截到来自 {event.user_id} 的私聊消息：{event.get_plaintext()}，静默丢弃。")
    # 不返回任何消息，直接结束/丢弃
