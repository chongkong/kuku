from asyncio import get_event_loop, set_event_loop, wait_for, run_coroutine_threadsafe, Queue
from threading import Thread

__all__ = [
    'run_coroutine',
    'new_queue'
]


def _run_event_loop_forever(loop):
    set_event_loop(loop)
    loop.run_forever()


_main_loop = get_event_loop()
_main_loop_thread = Thread(target=_run_event_loop_forever, args=[_main_loop])
_main_loop_thread.start()


def run_coroutine(coroutine, timeout=60):
    global _main_loop
    return run_coroutine_threadsafe(wait_for(coroutine, timeout, loop=_main_loop), _main_loop)


def new_queue():
    global _main_loop

    queue = Queue(loop=_main_loop)

    def putter(item):
        _main_loop.call_soon_threadsafe(queue.put_nowait, item)

    queue.put = putter
    return queue
