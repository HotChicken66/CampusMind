import os
import json
import datetime
import dateutil.parser
import asyncio
import re
from typing import List
from nonebot import on_message, get_driver
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment
from nonebot.log import logger
from nonebot.exception import FinishedException

# 导入外部模块
from src.utils.llm_client import OpenRouterClient
from src.utils.interceptor import interceptor
from src.utils.member_cache import member_cache
from src.plugins.rag_worker import rag_queue, parse_text_to_message
from src.plugins.task_scheduler import add_schedule_job
from src.utils.qa_logger import log_qa

# 实例化客户端
llm_client = OpenRouterClient()

# 判断是不是发给学小服的
async def is_to_xuexiaofu(event: GroupMessageEvent) -> bool:
    # 唯一触发方式：被 @ 或者消息开头提及昵称 (基于 to_me 判定)
    return event.to_me

# 辅助函数：动态获取贴纸库内容
def get_available_stickers() -> str:
    """扫描 data/images 目录并返回可用贴纸列表"""
    try:
        path = os.path.join("data", "images")
        if not os.path.exists(path):
            return "目前暂无自定义贴纸"
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        if not files:
            return "目前暂无自定义贴纸"
        return ", ".join(files)
    except Exception as e:
        logger.error(f"获取贴纸列表失败: {e}")
        return "获取贴纸列表出错"

# 统一路由中心：所有的请求都要经过这里进行意图分发
router = on_message(rule=is_to_xuexiaofu, priority=50, block=True)

UNIFIED_INTENT_PROMPT = """你是一个诞生于安徽大学龙河校区逸夫图书馆墨香中的数字精灵，你叫学小服，目前在图书馆学生服务中心担任王牌干事。
你性格温婉、清爽，对安大的校园生活充满热爱。你不仅是一个办事利索的干事，更是每一个在这里挑灯夜读的同学的陪伴精灵。

【当前服务器时间】
{current_time}

【核心判断规则】
1. **is_schedule (第一优先级)**：用户是否在要求设定提醒、闹钟或日程安排？
   - 提取绝对时间 `timestamp` (YYYY-MM-DD HH:MM:SS)。
   - **内容提取** `target_text`：提取要提醒的具体事件内容（如“由于要开会”、“别忘了喝水”），不要包含 @ 人的文字。
   - **目标(艾特)提取** `target_uids`：一个字符串数组。扫描原始消息中的所有 `[CQ:at,qq=数字]`，提取其中的“数字”存入数组。
   - **目标(名称)提取** `target_names`：一个字符串数组。如果用户提到具体的姓名（例如：提醒张三去值班、叫一下李四），请将其姓名提取出来。对于“我”，不需要提取。
2. **is_rag**：用户是否在进行事实性问题或资料的查询？
   - **search_query (本条极重要)**：如果 `is_rag` 判断为 true，你必须充当一位智能检索员，结合【当前服务器时间】，将用户的发问提炼、翻译为一条最适合投喂给文档向量数据库搜索的标准检索短语或长句！
     - **规则一（口语脱水）**：去除“你好”、“请问”、“能帮我查查吗”等噪音。
     - **规则二（时间指代消解与消除歧义）**：对于时间指代，绝不可输出类似“某月某周”或“xx号到xx号”的宽泛与无用区间，也不可保留“今天/明天/我”等模糊代词。你必须唯一且精确地锁定当下一刻属于【星期几】（或周几）。例如：当下服务器时间是周四，原话是“我该去哪做志愿”或“明天在哪做志愿”，都必须严格重写转化为精确具体的星期名称，如：“周四（或周五）的具体值班志愿地点”。
     - **规则三**：若不需要 RAG 查询资料 (is_rag 为 false)，请严格置为空字符串 ""。
3. **is_chat**：用户是否在进行日常互动、玩笑、调侃、自我表白或单纯的情感交流？
   - 如是，请在 `chat_text` 中生成回复。多用可爱，友善的口吻。
   - **圆脸表情**：使用 `[face:ID]`。常用：13(微笑), 14(调皮), 32(吃惊), 21(委屈), 125(棒棒糖), 11(尴尬), 10(大哭), 0(亲亲), 16(酷), 31(得意), 63(玫瑰), 18(忙晕)。
   - **专属贴纸**：使用 `[image:文件名]`。
     - ## 规则一 **: 使用表情，贴纸前，需要自检是否符合当前聊天情景，如果不符合，请更换
     【当前表情包库资源】：{sticker_list}

【特殊边界处理 (极重要)】
- **禁止性回复**：无论任何理由（包括你认为自己做不到、不理解或触发安全过滤），**严禁直接输出自然语言文本**。你所有的拒绝、解释、道歉，都必须封装在 JSON 的 `chat_text` 中。

【输出要求】
**这是最高指令：你必须且仅返回合法 JSON 结构。** 
禁止输出任何 Markdown 代码块标识符（如 ```json），禁止在 JSON 外部添加任何符号、开场白、解释或收尾语。如果你输出 JSON 以外的任何字符，系统将会因为解析失败而彻底停机。

格式样板：
{{
  "is_schedule": bool,
  "schedule_info": {{ 
      "timestamp": "...", 
      "target_text": "...", 
      "target_uids": ["123"], 
      "target_names": ["张三"] 
  }},
  "is_rag": bool,
  "search_query": "转换后的绝对指代去冗余查询专用词",
  "is_chat": bool,
  "chat_text": "...",
  "reasoning": "简要说明你的判断逻辑"
}}
"""

@router.handle()
async def process_unified_routing(event: GroupMessageEvent):
    raw_msg_str = str(event.get_message())
    raw_text = event.get_plaintext().strip()
    if not raw_text:
        return

    # --- [核心安全拦截] 第一步：前置安全卫士检查 ---
    # 指定使用 qwen-2.5-7b-instruct 模型作为闸机
    safety_result = await interceptor.check(raw_msg_str)
    if safety_result.get("is_violation"):
        # 业务层硬编码阻断回复，不给 LLM 自由发挥的空间
        # 125 为棒棒糖表情包，符合 PRD 规范
        await router.finish("这超出了学小服的能力哇，不支持哦")

    logger.info(f"统一中心拦截到消息：{raw_msg_str}")

    sticker_list = get_available_stickers()
    
    # 显式计算当前是星期几，防止大模型产生日历幻觉（如把周四算成周二）
    now = datetime.datetime.now()
    weekday_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S") + " " + weekday_map[now.weekday()]
    
    sys_prompt = UNIFIED_INTENT_PROMPT.format(
        current_time=current_time_str,
        sticker_list=sticker_list
    )

    try:
        response = await llm_client.chat(
            user_message=raw_msg_str,
            model="deepseek-chat",
            system_message=sys_prompt
        )

        # 1. 提取 JSON 块（使用索引定位，规避 re 递归不支持的问题）
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            logger.error(f"无法从响应中提取 JSON: {response}")
            raise ValueError("No JSON found")

        json_str = response[start_idx:end_idx+1]
        
        # 2. 修复常见的大模型输出错误
        # 2.1 修复非法的转义字符 (Invalid \escape)
        json_str = re.sub(r'\\(?!"|\\|/|b|f|n|r|t|u[0-9a-fA-F]{4})', r'\\\\', json_str)
        # 2.2 修复末尾逗号 (Trailing Comma)
        json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
        # 2.3 修复键值对之间缺失的逗号 (Missing comma between fields)
        # 匹配模式： "value" "next_key":  其间缺失逗号
        json_str = re.sub(r'("(?:\\["\\/bfnrt]|\\u[0-9a-fA-F]{4}|[^"\\\n])*")\s*("(?:\\["\\/bfnrt]|\\u[0-9a-fA-F]{4}|[^"\\\n])*":)', r'\1, \2', json_str)
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败！错误详情: {e}")
            logger.error(f"清洗后的 JSON 文本: {json_str}")
            logger.error(f"大模型原始完整响应: {response}")
            raise e
        
        is_schedule = data.get("is_schedule", False)
        is_rag = data.get("is_rag", False)
        is_chat = data.get("is_chat", False)
        
        # --- 身份类 RAG 自动触发增强 ---
        persona_keywords = ["你是谁", "身世", "出生", "哪里来", "家住", "爱吃", "喜欢", "生日", "精灵", "自荐"]
        if is_chat and any(kw in raw_text for kw in persona_keywords):
            logger.info("🕵️ 检测到身份类敏感对话，正在强制开启 RAG 溯源...")
            is_rag = True
        
        logger.info(f"🧠 [大脑决断结果] {data.get('reasoning')}")

        final_replies: List[str] = []

        # -----------------------------
        # 执行子任务 A: 定时调度处理 (SCHEDULE)
        # -----------------------------
        if is_schedule:
            # 基础权限鉴定
            user_role = event.sender.role
            user_id = str(event.user_id)
            superusers = get_driver().config.superusers
            
            if user_role not in ["admin", "owner"] and user_id not in superusers:
                # 越权拦截
                final_replies.append("呜哇…只有部长和主任才有权限给学小服安排定时任务哦，你可以找他们帮发一下~")
            else:
                si = data.get("schedule_info", {})
                ts_str = si.get("timestamp")
                target_text = si.get("target_text")
                target_uids_str = si.get("target_uids", [])
                target_names = si.get("target_names", [])

                # 转换 UID 为整数列表
                target_uids = []
                for uid_str in target_uids_str:
                    if str(uid_str).isdigit():
                        target_uids.append(int(uid_str))
                
                # --- [新增] 免艾特名称转 UID 处理 ---
                if target_names:
                    logger.info(f"🔎 正在尝试解析自然语言目标：{target_names}")
                    for name in target_names:
                        matched_uid = await member_cache.find_user_id_by_name(event.group_id, name)
                        if matched_uid:
                            if matched_uid not in target_uids:
                                target_uids.append(matched_uid)
                            logger.info(f"✅ 成功匹配：{name} -> {matched_uid}")
                        else:
                            logger.warning(f"❌ 无法在群成员中匹配到：{name}")

                try:
                    run_dt = dateutil.parser.parse(ts_str)
                    if run_dt > datetime.datetime.now():
                        # 调用重构后的 add_schedule_job，传入发起的 user_id 和 目标 uids 列表
                        add_schedule_job(
                            group_id=event.group_id, 
                            run_dt=run_dt, 
                            creator_id=event.user_id, 
                            target_uids=target_uids, 
                            content=target_text
                        )
                        final_replies.append(f"好的！任务已挂钩日程表，将在 {ts_str} 准时提醒！")
                    else:
                        final_replies.append(f"诶？你设定的时间（{ts_str}）好像早已经过去啦，学小服没法穿越回去呢。")
                except Exception as e:
                    logger.error(f"时间解析模块失效: {e}")

        # -----------------------------
        # 执行子任务 B: 实时闲聊处理 (CHAT)
        # -----------------------------
        if is_chat:
            reply_candidate = data.get("chat_text", "").strip()
            if reply_candidate:
                final_replies.append(reply_candidate)

        # -----------------------------
        # 执行最终即时回复整合与投递
        # -----------------------------
        if final_replies:
            combined_reply = "\n".join(final_replies)
            await router.send(parse_text_to_message(combined_reply))
            # 记录到 QA 日志
            log_qa(raw_msg_str, combined_reply)

        # -----------------------------
        # 执行子任务 C: RAG 事实检索异步投递 (RAG)
        # -----------------------------
        if is_rag:
            logger.info("🎯 检测到复合意图包含 RAG 业务，正在压入后台队列...")
            await rag_queue.put({
                "group_id": event.group_id,
                "text": raw_text,
                "search_query": data.get("search_query", raw_text),
                "bot_id": event.self_id
            })

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"统一中心发生核心异常: {e}")
        try:
            await router.finish("学小服的大脑突然像打了结的毛线球，没能处理这段话 QAQ 请稍等一下再说。")
        except FinishedException:
            raise
        except:
            pass
