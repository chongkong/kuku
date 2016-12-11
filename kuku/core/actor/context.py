from asyncio import Task, iscoroutine, TimeoutError
from collections import namedtuple
from functools import partial

from pip.utils import cached_property

from kuku.util import random_alphanumeric
from .message import ErrorForward
from .cluster import get_actor_by_uuid, spawn

__all__ = (
    'ActorContext'
)


class ContextAwareTask(Task):
    def __init__(self, coro, actor_ctx):
        super().__init__(coro, loop=actor_ctx.loop)
        self.actor_ctx = actor_ctx
        self.envelope = actor_ctx.envelope

    def _step(self, *args, **kwargs):
        with self.actor_ctx.msg_scope(self.envelope):
            super()._step(*args, **kwargs)


class MessageScope(object):
    __slots__ = ('actor_ctx', 'envelope')

    def __init__(self, actor_ctx, envelope):
        self.actor_ctx = actor_ctx
        self.envelope = envelope

    def __enter__(self):
        self.actor_ctx.envelope = self.envelope

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.actor_ctx.envelope = None


ReplyInboxItem = namedtuple('ReplyInboxItem', ['reply_fut', 'timer_handle', 'task'])


class ActorContext(object):
    def __init__(self, actor, loop):
        self._actor = actor
        self._loop = loop

        self.envelope = None
        self.reply_inbox = {}
        self.children = set([])

    @property
    def loop(self):
        return self._loop

    @property
    def parent(self):
        return self._actor.parent

    @cached_property
    def ref(self):
        return get_actor_by_uuid(self._actor.uuid)

    @property
    def actor_uuid(self):
        return self._actor.uuid

    @property
    def default_timeout(self):
        return type(self._actor).default_timeout

    @property
    def sender(self):
        return self.envelope.sender if self.envelope else None

    @property
    def req_token(self):
        return self.envelope.req_token if self.envelope else None

    @property
    def resp_token(self):
        return self.envelope.resp_token if self.envelope else None

    def issue_req_token(self, reply_fut, timeout):
        token = random_alphanumeric(6)
        while token in self.reply_inbox:
            token = random_alphanumeric(6)

        timer_handle = self._loop.call_later(
            timeout, partial(self.timeout_reply, token))
        self.reply_inbox[token] = ReplyInboxItem(
            reply_fut, timer_handle, Task.current_task(self._loop))
        return token

    def cancel_reply(self, token):
        if token in self.reply_inbox:
            item = self.reply_inbox.pop(token)
            item.reply_fut.cancel()
            item.timer_handle.cancel()

    def timeout_reply(self, token):
        if token in self.reply_inbox:
            item = self.reply_inbox.pop(token)
            item.reply_fut.set_exception(TimeoutError)
            item.timer_handle.cancel()

    def resolve_reply(self, envelope):
        token = envelope.resp_token
        if token in self.reply_inbox:
            item = self.reply_inbox.pop(token)
            if isinstance(envelope.message, ErrorForward):
                item.reply_fut.set_exception(envelope.message.error)
            else:
                item.reply_fut.set_result(envelope.message)
            item.timer_handle.cancel()
            item.task.envelope = envelope

    def msg_scope(self, envelope):
        return MessageScope(self, envelope)

    def run_main(self, coro):
        return ContextAwareTask(coro, self)

    def run_coroutine_behavior(self, behav):
        if not iscoroutine(behav):
            raise TypeError(
                'argument of run_behavior() should be a coroutine; '
                '{} found'.format(type(behav)))

        return ContextAwareTask(
            self._wrap_exc(behav), self)

    async def _wrap_exc(self, coro):
        try:
            await coro
        except Exception as e:
            if self.envelope.req_token:
                self.sender.reply(e)

    def spawn(self, actor_type, *args, **kwargs):
        child = spawn(actor_type, *args, parent=self.ref, **kwargs)
        self.children.add(child)
        return child

    def remove_child(self, child):
        self.children.remove(child)
