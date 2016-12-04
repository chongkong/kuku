from asyncio import Task, iscoroutine
from inspect import ismethod

from .cluster import get_actor_by_uuid, spawn

__all__ = (
    'ActorContext'
)


class LoopContext(object):
    def __init__(self, loop, actor_context, msg_ctx=None):
        self.loop = loop
        self.actor_context = actor_context
        self.msg_ctx = msg_ctx

    def __enter__(self):
        self.loop.actor_context = self.actor_context
        if self.msg_ctx:
            self.actor_context.set_msg_ctx(self.msg_ctx)

    def __exit__(self, exc_type, exc_val, exc_tb):
        del self.loop.actor_context
        self.actor_context.reset_msg_ctx()


class ContextAwareTask(Task):
    def __init__(self, coro, actor_context, msg_ctx=None, loop=None):
        super().__init__(coro, loop=loop)
        self._actor_context = actor_context
        self._msg_ctx = msg_ctx

    def _step(self, *args, **kwargs):
        with LoopContext(self._loop,
                         self._actor_context,
                         self._msg_ctx):
            super()._step(*args, **kwargs)


class ActorContext(object):
    def __init__(self, actor):
        self._backup = {}
        self._loop = actor.loop
        self._ref = None
        self._actor_uuid = actor.uuid

        self.parent = actor.parent
        self.sender = None
        self.default_timeout = actor.default_timeout
        self.children = set([])

    @property
    def ref(self):
        if self._ref is None:
            self._ref = get_actor_by_uuid(self._actor_uuid)
        return self._ref

    def set_msg_ctx(self, ctx):
        if len(self._backup) > 0:
            self.reset_msg_ctx()  # Only one message context can be set at the moment
        for key, val in ctx.items():
            if hasattr(self, key) and not ismethod(getattr(self, key)):
                self._backup[key] = getattr(self, key)
                setattr(self, key, val)

    def reset_msg_ctx(self):
        for key, val in self._backup.items():
            setattr(self, key, val)
        self._backup.clear()

    def run(self, coro):
        if not iscoroutine(coro):
            raise TypeError(
                'argument of run() should be a coroutine; '
                '{} found'.format(type(coro)))

        return ContextAwareTask(coro, self, loop=self._loop)

    def run_behavior(self, coro, msg_ctx):
        if not iscoroutine(coro):
            raise TypeError(
                'argument of run_behavior() should be a coroutine; '
                '{} found'.format(type(coro)))

        return ContextAwareTask(coro, self, msg_ctx, loop=self._loop)

    def spawn(self, actor_type, *args, **kwargs):
        child = spawn(actor_type, *args, parent=self.ref, **kwargs)
        self.children.add(child)
        return child
