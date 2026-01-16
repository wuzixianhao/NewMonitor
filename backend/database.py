import redis
import json
from models import ServerSchema
from typing import Dict, List

# --- Redis 配置 ---
# 如果你的 Redis 有密码，加 password='xxx'
# decode_responses=True 让我们取出来的是字符串而不是字节
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class Database:
    def __init__(self):
        self.prefix = "server:"  # Redis key 前缀，方便管理

    def get_all_servers(self) -> Dict[str, ServerSchema]:
        """获取所有服务器数据，返回字典 {id: ServerSchema}"""
        servers = {}
        # 1. 扫描所有以 server: 开头的 key
        keys = r.keys(f"{self.prefix}*")
        if not keys:
            return {}
        
        # 2. 批量获取数据
        values = r.mget(keys)
        
        # 3. 反序列化
        for val in values:
            if val:
                try:
                    # 将 JSON 字符串转为 Pydantic 对象
                    server_obj = ServerSchema.model_validate_json(val)
                    servers[server_obj.server_id] = server_obj
                except Exception as e:
                    print(f"Redis 数据解析失败: {e}")
        return servers

    def get_server(self, server_id: str) -> ServerSchema | None:
        """获取单个服务器"""
        val = r.get(f"{self.prefix}{server_id}")
        if val:
            return ServerSchema.model_validate_json(val)
        return None

    def upsert_server(self, server: ServerSchema):
        """新增或更新服务器 (自动保存)"""
        key = f"{self.prefix}{server.server_id}"
        # model_dump_json() 直接把对象转成 JSON 字符串
        r.set(key, server.model_dump_json())

    def delete_server(self, server_id: str):
        """删除服务器"""
        r.delete(f"{self.prefix}{server_id}")

# 初始化一个全局 DB 对象供外部调用
db = Database()