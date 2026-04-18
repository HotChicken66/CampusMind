import re
import os
import asyncio
from typing import Dict, Any
from nonebot import get_driver, get_bot
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment

from src.utils.vector_store import VectorStore
from src.utils.llm_client import OpenRouterClient
from src.utils.qa_logger import log_qa

# 全局的 RAG 任务队列
rag_queue = asyncio.Queue()

# 统一综合知识库 (采用延时初始化以规避启动时的网络波动影响)
_vs_unified = None

def get_vs_unified():
    global _vs_unified
    if _vs_unified is None:
        _vs_unified = VectorStore(collection_name="xuexiaofu_knowledge")
    return _vs_unified

llm_client = OpenRouterClient()

# 预设模型参数
DEEPSEEK_MODEL = "deepseek-chat"
# 距离阈值设定（1.0 ~ 1.2 左右通常拦截不相关的闲聊或无关检索，测试中真实命中一般会在 0.3 - 0.7）
DISTANCE_THRESHOLD = 1.0 

def parse_text_to_message(text: str) -> Message:
    """
    将包含 [face:ID] 、 [image:文件名] 以及 {知识库图片} 的字符串解析为 OneBot V11 Message 对象
    """
    # 匹配 [face:数字] 或 [image:文件名.扩展名] 或 {文件名}
    pattern = r'(\[face:\d+\]|\[image:[^\]]+\]|\{[^}]+\})'
    parts = re.split(pattern, text)
    msg = Message()
    for part in parts:
        if not part:
            continue
        if part.startswith("[face:"):
            # 获取 ID 数字
            face_id = re.search(r'\d+', part).group()
            msg.append(MessageSegment.face(int(face_id)))
        elif part.startswith("[image:") or (part.startswith("{") and part.endswith("}")):
            # 获取文件名
            if part.startswith("[image:"):
                img_name = re.search(r':([^\]]+)', part).group(1)
            else:
                img_name = part[1:-1]
            
            # 兼容性处理：如果没带后缀，尝试寻找
            possible_names = [img_name]
            if "." not in img_name:
                possible_names.extend([f"{img_name}.jpg", f"{img_name}.png", f"{img_name}.jpeg", f"{img_name}.gif"])
            
            found = False
            # 1. 优先尝试精确/带后缀匹配
            for name in possible_names:
                sticker_path = os.path.abspath(os.path.join("data", "images", name))
                knowledge_path = os.path.abspath(os.path.join("data", "knowledge_images", name))
                
                if os.path.exists(sticker_path):
                    msg.append(MessageSegment.image(f"file:///{sticker_path}"))
                    found = True; break
                elif os.path.exists(knowledge_path):
                    msg.append(MessageSegment.image(f"file:///{knowledge_path}"))
                    found = True; break
            
            # 2. 如果没找到，尝试“前缀模糊匹配”（处理像 {图1} 匹配 "图 1塔楼.png" 的情况）
            if not found:
                kn_img_dir = os.path.abspath(os.path.join("data", "knowledge_images"))
                if os.path.exists(kn_img_dir):
                    # 获取该目录下所有图片
                    all_files = os.listdir(kn_img_dir)
                    # 匹配规则：忽略大小写，且文件名以 img_name 开头（或去掉空格后开头）
                    clean_tag = img_name.replace(" ", "").lower()
                    for f in all_files:
                        clean_f = f.replace(" ", "").lower()
                        if clean_f.startswith(clean_tag):
                            full_path = os.path.join(kn_img_dir, f)
                            msg.append(MessageSegment.image(f"file:///{full_path}"))
                            found = True; break
            
            if not found:
                msg.append(MessageSegment.text(f"【图片丢失:{img_name}】"))
        else:
            msg.append(MessageSegment.text(part))
    return msg

async def rag_consumer():
    logger.info("RAG 消费者 Worker 已启动，正潜伏在后台等待队列任务...")
    while True:
        task: Dict[str, Any] = await rag_queue.get()
        group_id = task["group_id"]
        user_text = task["text"]
        search_query = task.get("search_query", user_text)
        if not search_query.strip():
            search_query = user_text
            
        bot_id = task["bot_id"]
        
        try:
            bot: Bot = get_bot(str(bot_id))
        except Exception:
            bot = get_bot()
            
        try:
            # Step 1: 检索资料
            store_name = "统一知识库"
            
            logger.info(f"[RAG 调度] 正在访问 [{store_name}] 检索关于优化搜索词 '{search_query}' (原始问话: '{user_text}') 的资料...")
            results = get_vs_unified().search(search_query, n_results=5, distance_threshold=DISTANCE_THRESHOLD)
            
            # 防幻觉兜底：如果没搜到（或者最高相关度都低于红线设定）
            if not results:
                logger.info(f"[RAG 调度] 未检索到相关资料，触发防幻觉兜底（阈值拦截）。")
                fallback_msg = "唔…学小服翻遍了知识库（不管是排班表还是规章制度）都没找到相关的答案呢，可能是没更新？建议你去群里骚扰一下值班干事或者对应的负责人哦！₍^ >ヮ<^₎"
                await bot.send_group_msg(group_id=group_id, message=fallback_msg)
                continue
                
            # 提取找到的高价值文本
            context_text = "\n---\n".join([r["content"] for r in results])
            logger.info(f"[RAG 调度] 检索成功，组装资料:\n{context_text}")
            
            # Step 2: 组装 Prompt
            knowledge_type_desc = "【知识库参考资料】"
            
            system_prompt = (
                "你是一个诞生于安徽大学逸夫图书馆墨香中的数字精灵“学小服”。\n"
                "你性格温婉热诚，作为图书馆学姐，你会基于提供的资料为干事和同学解答业务问题。\n\n"
                "### 核心规则 (CRITICAL RULES):\n"
                "1. **保持图片标签**：资料库中被 `{}` 包裹的内容（如 `{图16}`）是配套图片。如果资料包含图片且对回答有用，**你必须原样输出这些标签**。不要删掉它们！它们是我解析图片的“咒语”。\n"
                "2. **严禁幻觉**：不要说‘私聊发给你’或‘线下发给你’。你没有私聊功能。\n"
                "3. **回复风格**：语气亲切、自然。问什么答什么，不要罗列无关信息。\n\n"
                "4. **绝对不产生任何促进多轮对话的表达**：禁止出现：帮你搜、帮你整理、帮你细化、需要补充吗、还有疑问吗、要不要进一步解答等所有主动协助 / 引导话术。\n\n"
                "5. **如果你发现资料里没有对应的 {图X} 内容**：禁止生成任何参考资料中不存在的图片标签。\n\n"
                "### 样板案例 (EXAMPLE):\n"
                "用户：新闻稿怎么写？\n"
                "资料：包含七要素：时间地点...参考示例：{图16}\n"
                "你的回复：同学你好呀~ 新闻稿核心要求是真实准确哦，一定要包含时间、地点等七要素。 ||| 这里有一份优秀范文可以参考：{图16} 记得看完要认真模仿哦！\n\n"
                f"### 参考资料\n{context_text}"
            )
            
            logger.info("[RAG 调度] 正在调用 DeepSeek 进行深度总结与润色...")
            response = await llm_client.chat(
                user_message=user_text,
                model=DEEPSEEK_MODEL,
                system_message=system_prompt
            )
            
            # Step 3: 发送最终解答 (处理分段 |||)
            messages = [msg.strip() for msg in response.split("|||") if msg.strip()]
            for i, msg_text in enumerate(messages):
                # 模拟真人打字延迟
                typing_delay = min(4.0, max(1.0, len(msg_text) / 15.0))
                if i > 0:
                    await asyncio.sleep(typing_delay)
                
                # 解析并发送
                final_msg = parse_text_to_message(msg_text)
                await bot.send_group_msg(group_id=group_id, message=final_msg)
            
            # 手动记录到 QA 日志 (使用替换 ||| 为换行后的原文，并附带 RAG 背景资料)
            log_qa(user_text, response, rag_context=context_text)
            
        except Exception as e:
            logger.error(f"RAG 消费者执行任务期间发生意外崩溃: {e}")
            try:
                await bot.send_group_msg(group_id=group_id, message="学小服在翻找资料的时候突然头晕眼花了，请稍后再试QAQ")
            except:
                pass
        finally:
            rag_queue.task_done()

# 挂载到 NoneBot 的启动生命周期中，一并开启
driver = get_driver()

@driver.on_startup
async def start_worker():
    asyncio.create_task(rag_consumer())
