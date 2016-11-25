from asyncio import Task, iscoroutine, get_event_loop
from inspect import ismethod

__all__ = [
    'StepAwareTask',
    'ActorContext',
    'get_current_context'
]


class StepAwareTask(Task):
    def __init__(self, coro, before_step, after_step, *, loop=None):
        super().__init__(coro, loop=loop)
        self._before_step = before_step
        self._after_step = after_step

    def _step(self, *args, **kwargs):
        self._before_step()
        super()._step(*args, **kwargs)
        self._after_step()


class ActorContext(object):
    def __init__(self, actor):
        self._contexts = []
        self._loop = actor.loop

        self.parent = actor.parent
        self.sender = None
        self.me = actor.ref
        self.default_timeout = actor.default_timeout
        self.children = []

    def push(self, ctx):
        backup = {}
        for key, val in ctx.items():
            if hasattr(self, key) and not ismethod(getattr(self, key)):
                backup[key] = getattr(self, key)
                setattr(self, key, val)
        self._contexts.append(backup)

    def pop(self):
        backup = self._contexts.pop()
        for key, val in backup.items():
            setattr(self, key, val)

    def run(self, coro):
        if not iscoroutine(coro):
            raise TypeError(
                'argument of run() should be a coroutine; '
                '{} found'.format(type(coro)))

        def before():
            setattr(self._loop, 'actor_context', self)

        def after():
            delattr(self._loop, 'actor_context')

        return StepAwareTask(coro, before, after, loop=self._loop)

    def run_with_context(self, coro, ctx):
        if not iscoroutine(coro):
            raise TypeError(
                'argument of run_with_context() should be a coroutine; '
                '{} found'.format(type(coro)))

        def before():
            setattr(self._loop, 'actor_context', self)
            self.push(ctx)

        def after():
            delattr(self._loop, 'actor_context')
            self.pop()

        return StepAwareTask(coro, before, after, loop=self._loop)

    def spawn(self, actor_type):
        pass


def get_current_context():
    return getattr(get_event_loop(), 'actor_context', None)
