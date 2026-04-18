import os
import httpx
from typing import Optional
from dotenv import load_dotenv

# 使用绝对路径以防路径漂移
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env.prod")
load_dotenv(ENV_PATH)

class DeepSeekClient:
    def __init__(self, api_key: Optional[str] = None):
        env_key = os.environ.get("DEEPSEEK_API_KEY")
        self.api_key = api_key or env_key or os.environ.get("OPENROUTER_API_KEY")
        
        if not self.api_key:
            print(f"[FATAL ERROR] API_KEY Not Found! CWD: {os.getcwd()}, ENV_PATH: {ENV_PATH}")
            # 尝试再读一次
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        self.api_key = line.strip().split("=", 1)[1]
                        print(f"Fallback Parse Success! Extracted Key: {self.api_key[:8]}...")
        
        self.base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/") + "/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def chat(self, user_message: str, model: str = "deepseek-chat", system_message: Optional[str] = None) -> str:
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }

        # trust_env=False 用以规避某些系统代理导致的 SSL 或 Connection Error 阻断
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            try:
                response = await client.post(self.base_url, json=payload, headers=self.headers)
                response.raise_for_status() 
                
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPError as e:
                error_msg = str(e)
                if hasattr(e, 'response') and e.response:
                    error_msg += f" | Status: {e.response.status_code} | Body: {e.response.text}"
                raise Exception(f"DeepSeek API 请求失败: {error_msg}")
            except Exception as e:
                raise Exception(f"DeepSeek API 发生未知错误: {e}")

# 别名映射，保持向后兼容性
OpenRouterClient = DeepSeekClient

