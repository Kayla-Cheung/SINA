import asyncio
from contextlib import asynccontextmanager

class ConcurrencyManager:
    def __init__(self):
        # 钥匙柜（实现高并发细粒度锁）
        self._locks = {} 
        # 元锁（保护“铸造钥匙”这个动作本身）
        self._global_lock = asyncio.Lock()
    
    async def get_lock(self, resource_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if resource_id not in self._locks:
                self._locks[resource_id] = asyncio.Lock()
            return self._locks[resource_id]
        
    @asynccontextmanager
    async def resource_lock(self, resource_id: str):
        lock = await self.get_lock(resource_id)
        await lock.acquire()
        try:
            yield
        finally:
            lock.release()

lock_manager = ConcurrencyManager()
