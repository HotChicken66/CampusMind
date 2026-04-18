import os
import sys
import docx
import shutil

# 添加根目录路径以便导入 src 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    假设原则：
    1. 识别包含 '问' 或 'Q' (不分大小写) 开头的段落为提问内容。
    2. 识别包含 '答' 或 'A' (不分大小写) 开头的段落为回答内容。
    3. 支持简单的交替段落逻辑。
    """
    doc = docx.Document(filepath)
    qa_pairs = []
    
    current_q = ""
    current_a = ""
    
    # 简单的状态机逻辑
    for paragraph in doc.paragraphs:
        p_text = paragraph.text.strip()
        if not p_text:
            continue
        
        # 兼容多种前缀：'问：' 'Q:' '1. 问：' 'Q： ' 等
        # 使用 search 配合 ^ 锚点，并允许冒号可选或有空格
        is_q = re.search(r'^(?:\d+[\.、\s]*)?[Qq问][：:\s]?', p_text)
        is_a = re.search(r'^(?:\d+[\.、\s]*)?[Aa答][：:\s]?', p_text)
        
        if is_q:
            # 如果已有完整的 QA，先存起来
            if current_q and current_a:
                qa_pairs.append(f"【{current_q}】\n{current_a}")
                current_a = ""
            current_q = p_text
        elif is_a:
            # 如果已有 Q 但 A 正在追加，说明这是新的 A 段落（较少见，通常是 A 紧跟 Q）
            current_a = p_text
        else:
            # 既不是 Q 也不是 A，如果是 A 后面的内容，追加到 A
            if current_a:
                current_a += "\n" + p_text
            elif current_q:
                # 还没有 A 的时候，可能直接接着 Q 后面就是答案片段
                current_a = p_text
            else:
                # 都没有，则作为通识片段保留
                qa_pairs.append(p_text)

    # 收尾
    if current_q and current_a:
        qa_pairs.append(f"【{current_q}】\n{current_a}")
    elif current_q:
        qa_pairs.append(current_q)
    elif current_a:
        qa_pairs.append(current_a)

    return qa_pairs

def clear_and_rebuild():
    store = VectorStore(collection_name="xuexiaofu_knowledge")
    print("🗑️ 正在清空并重置知识库（Collection 重建）...")
    store.reset_collection()
    
    files_to_import = [
        "学服实践部.docx",
        "宣传部资料.docx",
        "学服实践部QA.docx"
    ]
    
    for filename in files_to_import:
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filename)
        if not os.path.exists(filepath):
            print(f"❌ 找不到文件：{filepath}")
            continue
            
        print(f"📄 开始解析文档：[{filename}]，采用 QA 分块策略...")
        chunks = parse_qa_from_docx(filepath)
            
        if not chunks:
            print(f"⚠️ 文档 {filename} 解析后没有有效文本。")
            continue
            
        dept = get_department_from_filename(filename)
        metadatas = [{"source": filename, "department": dept} for _ in chunks]
        store.add_texts(texts=chunks, metadatas=metadatas)
        print(f"✅ {filename} 知识点已入库。部门：[{dept}]，共 {len(chunks)} 个片段。")

if __name__ == "__main__":
    import re
    clear_and_rebuild()
