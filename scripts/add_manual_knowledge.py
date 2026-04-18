import os
import sys

# 添加根目录路径以便导入 src 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.vector_store import VectorStore

def add_specific_knowledge():
    store = VectorStore(collection_name="xuexiaofu_knowledge")
    
    # 用户要求的条目
    # 注意：用户写的是 [image:2025年古籍进校园]，我们保持原样存入，worker 会解析它
    text = "2025年古籍进校园的活动通知参考图片：[image:2025年古籍进校园.jpg]"
    metadata = {"source": "manual_entry", "type": "activity_notice"}
    
    store.add_texts(texts=[text], metadatas=[metadata])
    print(f"✅ 成功添加知识条目: {text}")

if __name__ == "__main__":
    add_specific_knowledge()
