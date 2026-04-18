import os
import json
import datetime
import uvicorn
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import sys
import shutil
import time

# 确保能导入 src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.vector_store import VectorStore

app = FastAPI(title="学小服周更知识管理后台")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_PATH = os.path.join("data", "weekly_knowledge.json")
IMAGE_DIR = os.path.abspath(os.path.join("data", "knowledge_images"))

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# 挂载静态图片路径，供前端预览
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

class DayRow(BaseModel):
    label: str
    officer: str
    code: str
    time: str
    location: str

class WeeklyKnowledgePayload(BaseModel):
    rows: List[DayRow]

def sync_to_vector_store(rows: List[DayRow]):
    """将动态行数据同步到统一向量库"""
    vs = VectorStore(collection_name="xuexiaofu_knowledge")
    
    # 定点清除旧的周更知识，释放这些旧的数据位
    vs.delete_by_metadata({"source": "weekly"})
    
    texts = []
    fixed_ids = []
    
    for i, row in enumerate(rows):
        # 嗅探当前的行属于上午还是下午，以组成严密的问题
        period = "上午" if "上午" in row.time else "下午" if "下午" in row.time else ""
        
        # 组装硬编码写死的 Q 与 A
        q_text = f"【Q：{row.label}{period}的志愿值班信息是什么？】\n"
        a_text = f"A：【动态业务安排】：{row.label}的值班干事是{row.officer}，当天的志愿地点位于{row.location}，时间安排为{row.time}，此日期的志愿签到码/志愿码固定为：{row.code}。"
        
        texts.append(q_text + a_text)
        # 写死固定序列号，完全跳出原系统的自增统计缺陷
        fixed_ids.append(f"weekly_knowledge_chunk_{i+1}")
        
    if texts:
        # 显式传入 fixed_ids 进行插入，安全入库
        vs.add_texts(texts, metadatas=[{"source": "weekly"}] * len(texts), ids=fixed_ids)
        print(f"✅ 已同步 {len(rows)} 行数据（共 {len(texts)} 条知识点）到向量库。")

@app.get("/api/weekly")
async def get_weekly():
    if not os.path.exists(DATA_PATH):
        return {"rows": [], "updated_at": "从未更新"}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/weekly")
async def save_weekly(payload: WeeklyKnowledgePayload):
    data_dict = payload.dict()
    data_dict["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 保存到 JSON 文件保持持久化
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)
    
    # 同步到 ChromaDB
    try:
        sync_to_vector_store(payload.rows)
    except Exception as e:
        print(f"向量库同步发生错误: {e}")
        return {"status": "partial_success", "message": f"Saved locally but vector sync failed: {str(e)}"}
        
    return {"status": "success", "updated_at": data_dict["updated_at"]}

class ManualChunkPayload(BaseModel):
    question: str
    answer: str
    department: str

@app.get("/api/chunks")
async def get_chunks():
    """获取所有知识库分块展示"""
    vs = VectorStore(collection_name="xuexiaofu_knowledge")
    try:
        chunks = vs.get_all_chunks()
        return {"chunks": chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chunks")
async def add_chunk(payload: ManualChunkPayload):
    """手动添加一条知识记录"""
    vs = VectorStore(collection_name="xuexiaofu_knowledge")
    try:
        content = f"【问】：{payload.question}\n【答】：{payload.answer}"
        vs.add_texts(
            texts=[content],
            metadatas=[{"source": "manual_add", "department": payload.department}]
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/chunks/{chunk_id}")
async def delete_chunk(chunk_id: str):
    """删除指定的知识记录"""
    vs = VectorStore(collection_name="xuexiaofu_knowledge")
    try:
        vs.delete_texts(ids=[chunk_id])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """上传图片并分配唯一文件名"""
    try:
        # 生成唯一文件名：image_{timestamp}_{original}
        timestamp = int(time.time())
        origin_name = file.filename
        # 清理文件名中的空格或其他可能导致问题的字符
        safe_name = "".join([c if c.isalnum() or c in "._-" else "_" for c in origin_name])
        unique_name = f"manual_kn_{timestamp}_{safe_name}"
        
        save_path = os.path.join(IMAGE_DIR, unique_name)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"status": "success", "filename": unique_name, "url": f"/images/{unique_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

@app.get("/api/image-list")
async def get_image_list():
    """获取所有图片文件名，供前端进行前缀智能匹配"""
    try:
        files = os.listdir(IMAGE_DIR)
        # 过滤出常见的图片格式
        img_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
        return {"images": img_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def read_index():
    # 确保路径正确
    html_path = os.path.join("scripts", "weekly_manager.html")
    if not os.path.exists(html_path):
        return "Critical Error: scripts/weekly_manager.html not found."
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    print("🚀 学小服管理后台已启动（已开启热重载模式）！")
    print("请访问: http://127.0.0.1:8000")
    # 开启 reload=True 需要传入 import 字符串
    uvicorn.run("scripts.weekly_admin_service:app", host="127.0.0.1", port=8000, reload=True)
