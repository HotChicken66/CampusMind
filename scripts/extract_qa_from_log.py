import re
import os

BOT_LOG_PATH = os.path.join("logs", "bot.log")
QA_LOG_PATH = os.path.join("logs", "qa_records.log")

def extract_qa():
    if not os.path.exists(BOT_LOG_PATH):
        print("未找到 bot.log，跳过历史回溯。")
        return

    with open(BOT_LOG_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. 分割每次事务
    events = re.split(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \| SUCCESS  \| nonebot:handle_event:537)', content)
    
    qa_pairs = []
    
    for i in range(1, len(events), 2):
        event_header = events[i]
        event_body = events[i+1] if i+1 < len(events) else ""
        
        ts_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', event_header)
        ts = ts_match.group() if ts_match else "Unknown Time"
        
        q_match = re.search(r'统一中心拦截到消息：(.+)', event_body)
        if not q_match:
            continue
        question = q_match.group(1).strip()
        
        # 提取结果与 RAG 资料
        answer = "【历史回溯无法获取实时回复原文，请参考处理逻辑】"
        rag_context = None
        
        # 提取 RAG 资料块
        rag_match = re.search(r'检索成功，组装资料:\n(.+?)\n\d{4}-\d{2}-\d{2}', event_body, re.DOTALL)
        if rag_match:
            rag_context = rag_match.group(1).strip()

        # 尝试从报错中提取回复原文
        error_match = re.search(r'无法从响应中提取 JSON: (.+)', event_body)
        if error_match:
            answer = error_match.group(1).strip()
        else:
            reason_match = re.search(r'🧠 \[大脑决断结果\] (.+)', event_body)
            if reason_match:
                answer = f"处理逻辑：{reason_match.group(1).strip()}"

        qa_pairs.append({
            "ts": ts,
            "q": question,
            "a": answer,
            "ctx": rag_context
        })

    # 重写写入（覆盖旧的，因为格式变了）
    if qa_pairs:
        with open(QA_LOG_PATH, "w", encoding="utf-8") as f:
            f.write("="*20 + " 历史回溯记录 (V2 格式) " + "="*20 + "\n")
            for pair in qa_pairs:
                log_entry = (
                    f"[{pair['ts']}]\n"
                    f"问：{pair['q']}\n"
                    f"答：{pair['a']}\n"
                )
                if pair['ctx']:
                    log_entry += f"【RAG 参考资料】:\n{pair['ctx']}\n"
                else:
                    log_entry += "【RAG 参考资料】: 无\n"
                    
                log_entry += f"{'-' * 50}\n"
                f.write(log_entry)
        print(f"成功按新格式回溯提取了 {len(qa_pairs)} 条历史 QA。")
    else:
        print("未在 logs/bot.log 中发现符合格式的对话。")

if __name__ == "__main__":
    extract_qa()
