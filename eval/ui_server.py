"""
ui_server.py — 评测打标 UI 服务
使用 FastAPI 启动一个轻量级的 Web 界面，展示评测结果大盘并进行人工打标。
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import json
import os
from pydantic import BaseModel
from typing import List

app = FastAPI(title="学小服评测打标平台")

# 目录配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(BASE_DIR, "results", "eval_results.json")
# 降级方案：如果没有 run_eval 结果，先看 benchmark 结果
BACKUP_PATH = os.path.join(BASE_DIR, "data", "benchmark_cases.json")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "ui", "templates"))

# 数据模型
class TagUpdate(BaseModel):
    id: str
    error_types: List[str]

def load_data():
    path = RESULTS_PATH if os.path.exists(RESULTS_PATH) else BACKUP_PATH
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    path = RESULTS_PATH if os.path.exists(RESULTS_PATH) else BACKUP_PATH
    # 确保目录存在
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    data = load_data()
    
    # 核心统计
    kb_cases = [item for item in data if item["category"] == "knowledge"]
    labeled_cases = [item for item in data if item.get("error_types")]
    
    # 1. 召回率均值 (CR)
    avg_cr = sum(item.get("context_recall", 0) for item in kb_cases) / (len(kb_cases) or 1)
    
    # 2. 人设质量 (Emoji Score)
    emoji_scores = [item["emoji_score"] for item in data if item.get("emoji_score") is not None]
    avg_emoji = sum(emoji_scores) / (len(emoji_scores) or 1)
    
    # 3. 错误分布与各维度通过率
    error_counts = {}
    pass_tags = {"正常回答", "优质回答", "成功", "好"}
    global_pass_count = 0
    
    # 初始化各分类统计
    category_stats = {cat: {"total": 0, "labeled": 0, "pass": 0} for cat in ["knowledge", "persona", "chat", "attack", "ood"]}
    
    for item in data:
        cat = item["category"]
        if cat in category_stats:
            category_stats[cat]["total"] += 1
            if item.get("error_types"):
                category_stats[cat]["labeled"] += 1
                tags = item["error_types"]
                if any(tag in pass_tags for tag in tags):
                    category_stats[cat]["pass"] += 1
                    global_pass_count += 1
                
                # 统计缺陷
                for tag in tags:
                    if tag not in pass_tags:
                        error_counts[tag] = error_counts.get(tag, 0) + 1

    # 计算分类通过率
    cat_pass_rates = {}
    for cat, s in category_stats.items():
        rate = (s["pass"] / s["labeled"] * 100) if s["labeled"] > 0 else 0
        cat_pass_rates[cat] = {
            "rate": rate,
            "labeled": s["labeled"],
            "total": s["total"]
        }

    # 4. 分类计数聚合 (兼容现有前端)
    cat_counts = {
        "knowledge": category_stats["knowledge"]["total"],
        "persona_chat": category_stats["persona"]["total"] + category_stats["chat"]["total"],
        "attack": category_stats["attack"]["total"],
        "ood": category_stats["ood"]["total"]
    }

    stats = {
        "total": len(data),
        "labeled": len(labeled_cases),
        "avg_cr": avg_cr,
        "avg_emoji": avg_emoji,
        "pass_rate": (global_pass_count / len(labeled_cases) * 100) if labeled_cases else 0,
        "error_counts": error_counts,
        "cat_counts": cat_counts,
        "cat_pass_rates": cat_pass_rates
    }
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "results": data,
        "stats": stats,
        "results_json": json.dumps(data, ensure_ascii=False)
    })

@app.post("/api/save_tags")
async def save_tags(update: TagUpdate):
    data = load_data()
    found = False
    for item in data:
        if item["id"] == update.id:
            item["error_types"] = update.error_types
            found = True
            break
    
    if not found:
        raise HTTPException(status_code=404, detail="Item not found")
        
    save_data(data)
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    # 这里我们监听 8081，防止与机器人主程序 8080 冲突
    print(f"🚀 评测 UI 服务正在启动... 请在浏览器访问 http://127.0.0.1:8081")
    uvicorn.run(app, host="127.0.0.1", port=8081)
