import os
import sys
import docx

# 添加根目录路径以便导入 src 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.vector_store import VectorStore

def update_xuanchuan():
    store = VectorStore(collection_name="xuexiaofu_knowledge")
    
    filename = "宣传部资料.docx"
    
    print(f"🗑️ 正在删除旧版本内容：{filename}")
    try:
        # ChromaDB 删除符合 metadata filter 的文档
        store.collection.delete(where={"source": filename})
        print("✅ 旧版本删除成功。")
    except Exception as e:
        print(f"删除库时发生异常: {e}")
        
    filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filename)
    if not os.path.exists(filepath):
        print(f"❌ 找不到文件：{filepath}")
        return
        
    print(f"📄 开始解析文档：[{filename}]")
    doc = docx.Document(filepath)
    chunks = []
    current_chunk = ""
    for paragraph in doc.paragraphs:
        p_text = paragraph.text.strip()
        if not p_text:
            continue
            
        current_chunk += p_text + "\n"
        if len(current_chunk) > 50:
            chunks.append(current_chunk.strip())
            current_chunk = ""
            
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    if not chunks:
        print(f"⚠️ 文档 {filename} 解析后没有文本。")
        return
        
    metadatas = [{"source": filename} for _ in chunks]
    store.add_texts(texts=chunks, metadatas=metadatas)
    print(f"✅ {filename} 新版本知识点已入库。共 {len(chunks)} 个片段。")

if __name__ == "__main__":
    update_xuanchuan()
