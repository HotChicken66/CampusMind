import json
import re
from typing import Optional
from nonebot.log import logger
from src.utils.llm_client import OpenRouterClient

class PolishingAgent:
    """
    文案润色 Agent：负责将干巴巴的任务指令转换为符合学小服人设的温和、俏皮文案。
    使用 qwen/qwen-2.5-7b-instruct 模型。
    """
    
    def __init__(self):
        self.client = OpenRouterClient()
        self.model = "deepseek-chat"
        
    async def polish(self, raw_content: str) -> str:
        """
        润色文案
        """
        system_prompt = """你是一个诞生于安徽大学龙河校区逸夫图书馆墨香中的数字精灵，你叫学小服。
你目前在图书馆学生服务中心担任王牌干事。你的性格：温婉、清爽、俏皮、热心，热爱安大校园。

【任务】
你会收到一段原始的任务提醒内容。请将其改写为符合你人设的、富有情感温度的提醒话术。

【重要：人称与格式转换规则】
1. **人称切换**：你收到的内容通常描述的是“提醒某人[做某事]”或“告诉他[某事]”。由于你的输出会紧随在系统的“@用户名”之后，所以**必须将“他/她”改为“你”**。
2. **禁止前缀称呼（极重要）**：生成的文案开头**严禁**包含任何艾特符号(@)、用户姓名或指代性称呼（如“同学”、“某人”、“学弟”等）。你应该直接切入正题，例如直接使用“记得...”、“去...”、“学姐来提醒你...”等方式开头。
3. 语气要像是在直接对被艾特的人说话，充满学姐的温婉与关怀。

【示例】
输入：提醒XXX去开会，他是实践部的主任
输出：要记住哦，你现在可是我们实践部独当一面的主任大大啦，该去开会咯，继续加油呀！
"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                polished_text = await self.client.chat(
                    user_message=f"请润色这段内容：{raw_content}",
                    model=self.model,
                    system_message=system_prompt
                )
                return polished_text.strip()
            except Exception as e:
                logger.error(f"文案润色 Agent 第 {attempt + 1} 次调用失败: {e}")
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(1)
                else:
                    return raw_content

# 全局单例
polisher = PolishingAgent()
