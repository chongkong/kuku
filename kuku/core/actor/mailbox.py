from asyncio import Queue

__all__ = (
    'Mailbox',
)


class Mailbox(object):
    """ Thread-safe asyncio queue """

    def __init__(self, loop):
        self._loop = loop
        self._queue = Queue(loop=loop)

    def put(self, item):
        self._loop.call_soon_threadsafe(self._queue.put_nowait, item)

    async def get(self):
        return await self._queue.get()
