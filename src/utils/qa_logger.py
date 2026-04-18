import os
import datetime

# 统一日志存放路径
QA_LOG_PATH = os.path.join("logs", "qa_records.log")

def log_qa(question: str, answer: str, rag_context: str = None):
    """
    记录一次 Q&A 对话到 qa_records.log，并包含 RAG 参考内容
    """
    # 确保 logs 目录存在
    os.makedirs(os.path.dirname(QA_LOG_PATH), exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 清理回答中的分段符
    clean_answer = answer.replace("|||", "\n")
    
    # 构建日志条目
    log_entry = (
        f"[{timestamp}]\n"
        f"问：{question}\n"
        f"答：{clean_answer}\n"
    )
    
    # 如果有 RAG 背景资料，则追加资料区块
    if rag_context:
        log_entry += f"【RAG 参考资料】:\n{rag_context}\n"
    else:
        log_entry += "【RAG 参考资料】: 无 (纯闲聊/指令模式)\n"
        
    log_entry += f"{'-' * 50}\n"
    
    try:
        with open(QA_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"写入 QA 日志失败: {e}")
