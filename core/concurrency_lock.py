import asyncio
from contextlib import asynccontextmanager

class ConcurrencyManager:
    def __init__(self):
        # 钥匙柜（实现高并发细粒度锁）
        self._locks = {} 
        # 引用计数（解决内存泄漏）
        self._ref_counts = {}
        # 元锁（保护“铸造/销毁钥匙”这个动作本身）
        self._global_lock = asyncio.Lock()
    
    @asynccontextmanager
    async def resource_lock(self, resource_id: str):
        async with self._global_lock:
            if resource_id not in self._locks:
                self._locks[resource_id] = asyncio.Lock()
                self._ref_counts[resource_id] = 0
            self._ref_counts[resource_id] += 1
            lock = self._locks[resource_id]
            
        await lock.acquire()
        try:
            yield
        finally:
            lock.release()
            async with self._global_lock:
                self._ref_counts[resource_id] -= 1
                if self._ref_counts[resource_id] == 0:
                    del self._locks[resource_id]
                    del self._ref_counts[resource_id]

lock_manager = ConcurrencyManager()
