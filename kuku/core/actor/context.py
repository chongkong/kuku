from asyncio import Task, iscoroutine, TimeoutError
from collections import namedtuple
from functools import partial

from pip.utils import cached_property

from kuku.util import random_alphanumeric
from .message import Envelope
from .cluster import get_actor_by_uuid, spawn

__all__ = (
    'ActorContext'
)


class ContextAwareTask(Task):
    def __init__(self, coro, actor_ctx, msg_ctx=None, loop=None):
        super().__init__(coro, loop=loop)
        self.actor_ctx = actor_ctx
        self.msg_ctx = msg_ctx

    def _step(self, *args, **kwargs):
        self.actor_ctx.set_msg_ctx(self.msg_ctx)
        try:
            super()._step(*args, **kwargs)
        finally:
            self.actor_ctx.reset_msg_ctx()


class MessageContext(object):
    __slots__ = ('sender', 'req_token', 'resp_token')

    def __init__(self, envelope):
        assert isinstance(envelope, Envelope)
        self.sender = envelope.sender
        self.req_token = envelope.req_token
        self.resp_token = envelope.resp_token


ReplyInboxItem = namedtuple('ReplyInboxItem', ['reply_fut', 'timer_handle', 'task'])


class ActorContext(object):
    def __init__(self, actor):
        self._msg_ctx = None
        self._loop = actor.loop

        self.reply_inbox = {}
        self.actor_uuid = actor.uuid
        self.parent = actor.parent
        self.default_timeout = actor.default_timeout
        self.children = set([])

    @cached_property
    def ref(self):
        return get_actor_by_uuid(self.actor_uuid)

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

    def raise_reply_exc(self, token, exc, msg_ctx):
        if token in self.reply_inbox:
            item = self.reply_inbox.pop(token)
            item.reply_fut.set_exception(exc)
            item.timer_handle.cancel()
            item.task.msg_ctx = msg_ctx

    def resolve_reply(self, token, reply, msg_ctx):
        if token in self.reply_inbox:
            item = self.reply_inbox.pop(token)
            item.reply_fut.set_result(reply)
            item.timer_handle.cancel()
            item.task.msg_ctx = msg_ctx

    def set_msg_ctx(self, msg_ctx):
        self._msg_ctx = msg_ctx

    def reset_msg_ctx(self):
        self._msg_ctx = None

    @property
    def sender(self):
        return self._msg_ctx.sender if self._msg_ctx else None

    @property
    def req_token(self):
        return self._msg_ctx.req_token if self._msg_ctx else None

    @property
    def resp_token(self):
        return self._msg_ctx.resp_token if self._msg_ctx else None

    def run(self, coro):
        if not iscoroutine(coro):
            raise TypeError(
                'argument of run() should be a coroutine; '
                '{} found'.format(type(coro)))

        return ContextAwareTask(coro, self, loop=self._loop)

    def run_behavior(self, behav, msg_ctx):
        if not iscoroutine(behav):
            raise TypeError(
                'argument of run_behavior() should be a coroutine; '
                '{} found'.format(type(behav)))

        return ContextAwareTask(
            self._wrap_exc(behav), self, msg_ctx, loop=self._loop)

    async def _wrap_exc(self, behav):
        try:
            await behav
        except Exception as e:
            if self._msg_ctx.req_token:
                self.sender.reply(e)

    def spawn(self, actor_type, *args, **kwargs):
        child = spawn(actor_type, *args, parent=self.ref, **kwargs)
        self.children.add(child)
        return child

    def remove_child(self, child):
        self.children.remove(child)
