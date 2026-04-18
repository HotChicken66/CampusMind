import os
import sys
import docx

# 添加根目录路径以便导入 src 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.vector_store import VectorStore

import re
from src.utils.vector_store import VectorStore

def get_department_from_filename(filename: str) -> str:
    if "实践部" in filename:
        return "实践部"
    elif "宣传部" in filename:
        return "宣传部"
    return "通用资料"

def parse_qa_from_docx(filepath: str) -> list[str]:
    """
    解析 Docx 中的 QA 对。
    """
    doc = docx.Document(filepath)
    qa_pairs = []
    
    current_q = ""
    current_a = ""
    
    for paragraph in doc.paragraphs:
        p_text = paragraph.text.strip()
        if not p_text:
            continue
        
        is_q = re.match(r'^(?:\d+[\.、])?[Qq问][:：]', p_text)
        is_a = re.match(r'^(?:\d+[\.、])?[Aa答][:：]', p_text)
        
        if is_q:
            if current_q and current_a:
                qa_pairs.append(f"【{current_q}】\n{current_a}")
                current_a = ""
            current_q = p_text
        elif is_a:
            current_a = p_text
        else:
            if current_a:
                current_a += "\n" + p_text
            elif current_q:
                current_a = p_text
            else:
                qa_pairs.append(p_text)

    if current_q and current_a:
        qa_pairs.append(f"【{current_q}】\n{current_a}")
    elif current_q:
        qa_pairs.append(current_q)
    elif current_a:
        qa_pairs.append(current_a)

    return qa_pairs

def load_docx_into_db(docx_path: str):
    """
    读取本地 Docx 并按照 QA 粒度切分后灌入知识库
    """
    if not os.path.exists(docx_path):
        print(f"❌ 找不到需要上传的知识文档：{docx_path}")
        return

    basename = os.path.basename(docx_path)
    print(f"📄 开始解析文档：[{basename}]，采用 QA 分块策略...")
    
    chunks = parse_qa_from_docx(docx_path)

    if not chunks:
        print("⚠️ 文档解析后没有提取到可用文本。")
        return

    print(f"🔪 文档成功切分为 {len(chunks)} 个 QA 片段。")
    print(f"🔄 正在向量化存储中...")
    
    store = VectorStore(collection_name="xuexiaofu_knowledge")
    dept = get_department_from_filename(basename)
    
    metadatas = [{"source": basename, "department": dept} for _ in chunks]
    
    store.add_texts(
        texts=chunks,
        metadatas=metadatas
    )
    
    print(f"\n✅ 知识库注入成功！已归类至 [{dept}] 部门。")

if __name__ == "__main__":
    file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "4月读书月.docx")
    load_docx_into_db(file_path)
