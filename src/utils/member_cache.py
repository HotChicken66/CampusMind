import os
import json
import time
from typing import List, Dict, Optional
from nonebot import get_bot
from nonebot.log import logger

CACHE_DIR = os.path.join("data", "member_cache")

class MemberCache:
    """
    群成员信息本地缓存中心
    防止频繁调用 bot.get_group_member_list 导致被封禁或延迟
    """
    def __init__(self, expire_seconds: int = 3600 * 24): # 默认缓存 24 小时
        self.expire_seconds = expire_seconds
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)

    def _get_cache_path(self, group_id: int) -> str:
        return os.path.join(CACHE_DIR, f"{group_id}.json")

    async def get_member_list(self, group_id: int) -> List[Dict]:
        """
        获取群成员列表，优先使用本地缓存
        """
        cache_path = self._get_cache_path(group_id)
        
        # 1. 尝试读取缓存
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 检查是否过期
                    if time.time() - data.get("updated_at", 0) < self.expire_seconds:
                        return data.get("members", [])
            except Exception as e:
                logger.error(f"读取群成员缓存失败: {e}")

        # 2. 调用 API 获取最新列表
        try:
            bot = get_bot()
            members = await bot.get_group_member_list(group_id=group_id)
            
            # 3. 写入缓存
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "updated_at": time.time(),
                    "members": members
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 已更新群 {group_id} 的成员名单缓存（共 {len(members)} 人）")
            return members
        except Exception as e:
            logger.error(f"获取群成员列表失败: {e}")
            return []

    async def find_user_id_by_name(self, group_id: int, name: str) -> Optional[int]:
        """
        在特定群中通过昵称/群名片查找 UID
        匹配优先级：全字匹配群名片 > 全字匹配昵称 > 包含匹配群名片 > 包含匹配昵称
        """
        members = await self.get_member_list(group_id)
        if not members:
            return None

        # 1. 全字匹配
        for m in members:
            if m.get("card") == name or m.get("nickname") == name:
                return m.get("user_id")

        # 2. 包含匹配 (模糊匹配)
        for m in members:
            card = m.get("card", "")
            nickname = m.get("nickname", "")
            if name in card or name in nickname:
                return m.get("user_id")

        return None

# 全局单例
member_cache = MemberCache()
