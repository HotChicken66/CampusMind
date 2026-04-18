import datetime
from typing import List
from nonebot.adapters.onebot.v11 import Message, Bot, MessageSegment
from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler
import nonebot

from src.utils.polisher import polisher

async def timer_callback(group_id: int, uids: List[int], content: str):
    """
    APScheduler 到点后触发的回调函数，执行真实 @ 提醒
    增加：异步文案润色环节
    """
    logger.info(f"触发定时提醒 -> 群 {group_id} | 目标 UID: {uids} | 原始内容: {content}")
    try:
        bot = nonebot.get_bot()
        
        # --- [新增] 异步文案润色环节 ---
        logger.info("🎨 正在调用 Polishing Agent 进行文案包装...")
        final_text = await polisher.polish(content)
        
        msg = Message()
        
        # 依次添加 @ 蓝字消息段
        if uids:
            for uid in uids:
                msg.append(MessageSegment.at(uid))
        
        # 使用润色后的文案替代原始内容
        msg.append(f" {final_text}")
        
        await bot.send_group_msg(group_id=group_id, message=msg)
    except Exception as e:
        logger.error(f"定时提醒触发失败: {e}")

def add_schedule_job(group_id: int, run_dt: datetime.datetime, creator_id: int, target_uids: List[int], content: str):
    """
    供外部插件调用的挂载函数
    """
    # 确定最终要 @ 的人选：优先使用明确提到的，如果没有则使用发起人
    final_uids = target_uids if target_uids else [creator_id]
    
    scheduler.add_job(
        timer_callback,
        "date",
        run_date=run_dt,
        args=[group_id, final_uids, content]
    )
    logger.info(f"成功添加定时任务，触发时间 {run_dt}。将 @ {final_uids}，内容: {content}")
