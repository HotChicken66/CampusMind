import os
import chromadb
from chromadb.utils import embedding_functions

# 强制禁用 HuggingFace 联网寻找更新和遥测，彻底采用本地缓存以防 Proxy SSL 阻断和客户端崩溃
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
# 强制禁用 ChromaDB 的后门遥测
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# 本地数据库存放目录
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "chroma_db")

# 使用专门针对中文优化的轻量级模型构建 Embeddings
# 采用延时加载策略，防止在 NoneBot 启动阶段因网络问题导致初始化失败崩溃
_emb_fn = None

def get_embedding_function():
    global _emb_fn
    if _emb_fn is None:
        _emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="shibing624/text2vec-base-chinese")
    return _emb_fn


class VectorStore:
    def __init__(self, collection_name: str = "xuexiaofu_knowledge"):
        # 确保目录存在
        os.makedirs(DB_PATH, exist_ok=True)
        # 初始化持久化配置
        self.client = chromadb.PersistentClient(path=DB_PATH)
        # 存储当前使用的集合名称
        self.collection_name = collection_name
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=get_embedding_function()
        )

    def reset_collection(self):
        """物理删除并重新创建集合，用于清空旧数据"""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=emb_fn
            )
            print(f"🗑️ 集合 {self.collection_name} 已清空并重置。")
        except Exception as e:
            print(f"⚠️ 重置集合失败: {e}")

    def delete_by_metadata(self, metadata_filter: dict):
        """根据元数据条件静默删除相关词条，不影响同一集合下的其他资料"""
        try:
            # collection.delete takes a `where` param which maps closely to chromadb's metadata filtering
            self.collection.delete(where=metadata_filter)
            print(f"🗑️ 已根据元数据条件 {metadata_filter} 清除集合 {self.collection_name} 中的相关语料。")
        except Exception as e:
            print(f"⚠️ 清除集合特定数据失败: {e}")

    def add_texts(self, texts: list[str], metadatas: list[dict] = None, ids: list[str] = None):
        """导入文本文本段到向量库"""
        if not texts:
            return
        
        # 自动生成递增 ID 或填充空 metadatas
        if ids is None:
            # 获取目前已有数量，防止冲毁
            start_idx = self.collection.count()
            ids = [f"doc_{start_idx + i}" for i in range(len(texts))]
            
        if metadatas is None:
            metadatas = [{"source": "unknown"}] * len(texts)

        self.collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        print(f"✅ 成功插入 {len(texts)} 条文本块。")

    def search(self, query: str, n_results: int = 5, distance_threshold: float = 1.0) -> list[dict]:
        """
        检索最相似的文本段落
        注意：ChromaDB 默认使用 L2 欧几里得距离，距离越小越相关。
        所以这里如果 distance_threshold 太大，说明不相关。
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # 解析返回结果
        ret = []
        if not results['documents'] or not results['documents'][0]:
            return ret
            
        docs = results['documents'][0]
        distances = results['distances'][0]
        metas = results['metadatas'][0]
        ids = results['ids'][0]
        
        for doc, dist, meta, idx in zip(docs, distances, metas, ids):
            # 过滤掉距离太远（语义不相关）的垃圾信息防幻觉 (PRD中提到的阈值拦截机制)
            if dist <= distance_threshold:
                ret.append({
                    "id": idx,
                    "content": doc,
                    "distance": dist,
                    "metadata": meta
                })
        return ret

    def delete_texts(self, ids: list[str]):
        """根据 ID 列表物理删除向量库中的记录"""
        try:
            self.collection.delete(ids=ids)
            print(f"🗑️ 已成功从集合 {self.collection_name} 中删除 {len(ids)} 条记录。")
        except Exception as e:
            print(f"⚠️ 删除记录失败: {e}")

    def get_all_chunks(self):
        """获取集合中所有的文档片段记录"""
        results = self.collection.get()
        ret = []
        if not results['documents']:
            return ret
            
        for doc, meta, idx in zip(results['documents'], results['metadatas'], results['ids']):
            ret.append({
                "id": idx,
                "content": doc,
                "metadata": meta
            })
        return ret
