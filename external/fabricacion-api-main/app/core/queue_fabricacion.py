import asyncio


class FabricacionQueue:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def add_job(self, job):
        await self.queue.put(job)

    async def get_job(self):
        return await self.queue.get()

# Cola global
fabricacion_queue = FabricacionQueue()

