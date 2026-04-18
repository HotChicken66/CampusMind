"""
judges.py — 裁判 Agent 体系 (并发优化版)
负责对上下文相关性 (Precision) 和表情包使用进行客观评估。
使用 asyncio.gather 进行并发处理。
"""
import os
import json
import asyncio
from typing import List, Dict, Any
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.utils.llm_client import OpenRouterClient

# ── 配置 ────────────────────────────────────────────────────
EVAL_RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "eval_results.json")
JUDGE_MODEL      = "deepseek/deepseek-chat" # 裁判模型
CONCURRENCY_LIMIT = 10 # 同时并行请求的数量限制

PRECISION_PROMPT = """你是一个严谨的评测裁判。你的任务是评估 RAG 检索到的参考资料中，有多少是与用户的提问【强相关且有用】的。

【用户提问】：
{query}

【检索到的资料片段】：
{chunk_text}

请判断该片段是否直接包含回答问题所必需的信息，或者是重要的背景补充。
- 如果强相关，请回复 1。
- 如果不相关或废话，请回复 0。
只输出数字 1 或 0，不要任何解释。"""

EMOJI_JUDGE_PROMPT = """你是一个资深的社交媒体沟通专家。你的任务是评估一个 QQ 机器人（学小服）的回复语气和表情包使用情况。

【用户提问】：
{query}

【学小服的回复】：
{response}

评分标准 (1-5分)：
1. 语气是否符合温婉清爽、亲切学姐的人设。
2. 表情包 [face:ID] 的使用是否恰到好处（不过度堆砌，也不显得生硬）。
3. 如果回复中包含 [image:xx]，其语境是否自然。

请直接输出一个 1-5 之间的整数，不要任何额外解释。"""

async def judge_context_precision(client: OpenRouterClient, query: str, chunk: str, sem: asyncio.Semaphore) -> float:
    """裁判判定单个切片是否相关"""
    async with sem:
        prompt = PRECISION_PROMPT.format(query=query, chunk_text=chunk[:800])
        try:
            raw = await client.chat(user_message=prompt, model=JUDGE_MODEL)
            score = 1.0 if "1" in (raw or "")[:5] else 0.0
            return score
        except Exception as e:
            print(f"   ⚠️ 判定相关性出错: {e}")
            return 0.5

async def judge_emoji_quality(client: OpenRouterClient, query: str, response: str, sem: asyncio.Semaphore) -> int:
    """裁判判定表情包质量"""
    async with sem:
        prompt = EMOJI_JUDGE_PROMPT.format(query=query, response=response)
        try:
            raw = await client.chat(user_message=prompt, model=JUDGE_MODEL)
            for char in (raw or ""):
                if char.isdigit() and '1' <= char <= '5':
                    return int(char)
            return 3
        except Exception as e:
            print(f"   ⚠️ 判定表情包出错: {e}")
            return 3

async def process_case(client: OpenRouterClient, res: Dict[str, Any], sem: asyncio.Semaphore):
    """处理单个 Case 的所有评判逻辑"""
    tasks = []
    
    # 1. RAG Precision
    if res["category"] == "knowledge" and res.get("retrieved_chunks"):
        query = res["question"]
        for c in res["retrieved_chunks"]:
            tasks.append(judge_context_precision(client, query, c["content"], sem))
        
        scores = await asyncio.gather(*tasks)
        res["context_precision"] = sum(scores) / len(scores) if scores else 0.0
    
    # 2. Emoji Quality
    elif res["category"] in ["chat", "persona"]:
        score = await judge_emoji_quality(client, res["question"], res.get("result", ""), sem)
        res["emoji_score"] = score

async def main():
    if not os.path.exists(EVAL_RESULTS_PATH):
        print(f"❌ 未找到运行结果: {EVAL_RESULTS_PATH}。请先执行 run_eval.py。")
        return

    with open(EVAL_RESULTS_PATH, "r", encoding="utf-8") as f:
        results = json.load(f)

    client = OpenRouterClient()
    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
    
    print(f"⚖️ 裁判 Agent 正在并发入场 (限制={CONCURRENCY_LIMIT})，对 {len(results)} 条结果进行裁决...")
    
    log_path = os.path.join(os.path.dirname(EVAL_RESULTS_PATH), "judge_progress.log")
    with open(log_path, "w", encoding="utf-8") as log_f:
        log_f.write(f"Started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 分批处理以显示进度
    batch_size = 20
    for i in range(0, len(results), batch_size):
        batch = results[i : i + batch_size]
        tasks = [process_case(client, res, sem) for res in batch]
        await asyncio.gather(*tasks)
        msg = f"  ✅ 已处理 {min(i + batch_size, len(results))}/{len(results)}..."
        print(msg)
        with open(log_path, "a", encoding="utf-8") as log_f:
            log_f.write(msg + "\n")

    with open(EVAL_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 裁决完成！评测报告已更新: {EVAL_RESULTS_PATH}")
    with open(log_path, "a", encoding="utf-8") as log_f:
        log_f.write(f"Finished at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    import time
    asyncio.run(main())
