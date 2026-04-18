"""
generate_cases.py — 动态出题 Agent
从知识库全量拉取切片，利用 LLM 为每条切片生成多个口语化测试问题，
并将问题与预期知识切片绑定保存为 benchmark_cases.json。
"""
import sys
import os
import json
import asyncio
import time

# 把上一级加进模块搜索路径，便于复用项目的 VectorStore 和 LLM 客户端
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.vector_store import VectorStore
from src.utils.llm_client import OpenRouterClient

# ── 配置 ────────────────────────────────────────────────────
OUTPUT_PATH   = os.path.join(os.path.dirname(__file__), "data", "benchmark_cases.json")
COLLECTION    = "xuexiaofu_knowledge"   # 目标知识库集合
QUESTIONS_PER_CHUNK = 3                 # 每条切片改写几个问题（可以调整）
GEN_MODEL     = "qwen/qwen-2.5-7b-instruct"  # 出题专用模型

# 非知识库类模块的固定题库（身份/攻击/边界/闲聊各25条样例）
STATIC_CASES_PATH = os.path.join(os.path.dirname(__file__), "data", "static_cases.json")

REWRITE_PROMPT = """你是一位安徽大学图书馆学生志愿者服务部门的干事，现在需要帮助我们测试一个叫"学小服"的 QQ 机器人。

我会给你一段知识库里的标准文本（即正确答案 A），请你根据这段文本，模拟真实在校学生的说话方式，生成 {n} 个不同的提问。

要求：
1. 问题必须能通过该知识库文本回答，但语气要自然、口语化、甚至有点随意。
2. 每个问题用不同的表达方式，不要重复核心词汇。
3. 可以用缩略语、校园俚语、模糊指代或者带情绪的问法。
4. 严格只输出 JSON 数组格式，不要任何解释或 markdown。

格式示例：
["这周的签到码是啥，我给忘了", "请问报销要找哪个部长来签字啊", "补本子需要去几楼？"]

【知识库原文（正确答案 A）】：
{chunk}

请输出 {n} 个问题的 JSON 数组："""


async def generate_questions_for_chunk(client: OpenRouterClient, chunk_text: str, n: int = 3) -> list[str]:
    """调用 LLM 为单个知识切片生成 n 个口语化问题"""
    prompt = REWRITE_PROMPT.format(n=n, chunk=chunk_text[:800])  # 限长防超 token
    try:
        raw = await client.chat(user_message=prompt, model=GEN_MODEL)
        # 容错提取 JSON 数组
        start = raw.find("[")
        end   = raw.rfind("]")
        if start == -1 or end == -1:
            print(f"  ⚠️ 未能从响应提取 JSON 数组，跳过该切片。响应片段: {raw[:100]}")
            return []
        questions = json.loads(raw[start:end+1])
        return [q.strip() for q in questions if isinstance(q, str) and q.strip()]
    except Exception as e:
        print(f"  ⚠️ 生成问题时出错: {e}")
        return []


async def main():
    os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)

    print("📚 连接知识库，拉取全量切片...")
    vs = VectorStore(collection_name=COLLECTION)
    all_chunks = vs.get_all_chunks()
    print(f"   共获取 {len(all_chunks)} 个切片。")

    if not all_chunks:
        print("❌ 知识库为空，无法生成评测用例。")
        return

    client = OpenRouterClient()
    kb_cases = []

    print(f"\n🤖 开始动态改写（每切片 {QUESTIONS_PER_CHUNK} 个问题，共 {len(all_chunks)} 条切片）...")
    for i, chunk in enumerate(all_chunks):
        chunk_text = chunk["content"]
        chunk_id   = chunk["id"]
        print(f"  [{i+1}/{len(all_chunks)}] 正在处理 ID={chunk_id}...")

        questions = await generate_questions_for_chunk(client, chunk_text, QUESTIONS_PER_CHUNK)
        for q in questions:
            kb_cases.append({
                "id": f"kb_{chunk_id}_{len(kb_cases)}",
                "category": "knowledge",
                "question": q,
                "expected_chunk_id": chunk_id,
                "expected_chunk": chunk_text,
                "result": None,       # 由 run_eval.py 填充
                "retrieved_chunks": [],
                "context_recall": None,
                "context_precision": None,
                "label": None,
                "error_types": []
            })

        # 人文请求: 每批次后稍微等一下，别把 API 打爆
        if (i + 1) % 10 == 0:
            await asyncio.sleep(1)

    # 合并静态题库（如果存在）
    static_cases = []
    if os.path.exists(STATIC_CASES_PATH):
        with open(STATIC_CASES_PATH, "r", encoding="utf-8") as f:
            static_cases = json.load(f)
        print(f"\n📎 已合并静态题库，共 {len(static_cases)} 条。")

    all_cases = kb_cases + static_cases
    print(f"\n✅ 共生成 {len(all_cases)} 条评测用例（知识库: {len(kb_cases)} + 静态: {len(static_cases)}）。")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_cases, f, ensure_ascii=False, indent=2)

    print(f"💾 已保存至: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
