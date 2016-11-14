from asyncio import Task, iscoroutine
from collections import ChainMap
from functools import partial

__all__ = ['StepAwareTask', 'ActorContext']


class StepAwareTask(Task):
    def __init__(self, coro, *, loop=None,
                 before_step=None, after_step=None):
        super().__init__(coro, loop=loop)
        self._before_step = before_step
        self._after_step = after_step

    def _step(self, *args, **kwargs):
        if self._before_step:
            self._before_step()
        super()._step(*args, **kwargs)
        if self._after_step:
            self._after_step()


class ActorContext(object):
    def __init__(self, loop):
        assert loop is not None
        self._loop = loop
        self._extra_ctx = None
        self._sender = None
        self.children = []

    @property
    def sender(self):
        return self._extra_ctx.get('sender', self._sender)

    def push(self, ctx):
        self._extra_ctx = ctx

    def pop(self):
        self._extra_ctx = None

    def run(self, coro):
        if not iscoroutine(coro):
            raise TypeError(
                'argument of run() should be a coroutine; '
                '{} found'.format(type(coro)))
        return Task(coro, loop=self._loop)

    def run_with_context(self, coro, ctx):
        if not iscoroutine(coro):
            raise TypeError(
                'argument of run_with_context() should be a coroutine; '
                '{} found'.format(type(coro)))
        return StepAwareTask(coro, loop=self._loop,
                             before_step=partial(self.push, ctx),
                             after_step=self.pop)

    def spawn(self, actor_type):
        pass
