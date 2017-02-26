import asyncio
import collections
import functools
import logging

from kuku import util
from kuku.actor import node
from kuku.actor import message as msg

__all__ = [
    'ActorContext'
]

logger = logging.getLogger(__name__)


WaitingItem = collections.namedtuple('WaitingItem', [
    'reply_fut',
    'timer_handle',
    'task'
])


class ActorContext(object):
    def __init__(self, actor, loop):
        self._actor = actor
        self._ref = node.get_actor_by_uuid(actor.uuid)
        self._loop = loop
        self._main_task = None
        self._waitings = {}
        self._children = set([])

    @property
    def loop(self):
        return self._loop

    @property
    def parent(self):
        return self._actor.parent

    @property
    def ref(self):
        return node.get_actor_by_uuid(self._actor.uuid)

    @property
    def _env(self):
        task = asyncio.Task.current_task(self._loop)
        return getattr(task, 'envelope', None)

    @property
    def actor_uuid(self):
        return self._actor.uuid

    @property
    def default_timeout(self):
        return self._actor.default_timeout

    @property
    def sender(self):
        if self._env:
            return self._env.sender

    @property
    def req_token(self):
        if self._env:
            return self._env.req_token

    @property
    def resp_token(self):
        if self._env:
            return self._env.resp_token

    def issue_req_token(self, reply_fut, timeout):
        token = util.random_alphanumeric(6)
        while token in self._waitings:
            token = util.random_alphanumeric(6)

        timer_handle = self._loop.call_later(
            timeout, functools.partial(self.timeout_reply, token))
        self._waitings[token] = WaitingItem(
            reply_fut, timer_handle, asyncio.Task.current_task(self._loop))
        return token

    def cancel_reply(self, token):
        if token in self._waitings:
            item = self._waitings.pop(token)
            item.reply_fut.cancel()
            item.timer_handle.cancel()

    def timeout_reply(self, token):
        if token in self._waitings:
            item = self._waitings.pop(token)
            item.reply_fut.set_exception(TimeoutError)
            item.timer_handle.cancel()

    def resolve_reply(self, envelope):
        token = envelope.resp_token
        if token in self._waitings:
            item = self._waitings.pop(token)
            if envelope.type == msg.MsgType.ERROR:
                item.reply_fut.set_exception(envelope.message)
                logger.debug(f'Error resolved {repr(envelope.resp_token)}')
            else:
                item.reply_fut.set_result(envelope.message)
                logger.debug(f'Resolved {repr(envelope.resp_token)}')
            item.timer_handle.cancel()
            item.task.envelope = envelope
        else:
            logger.warning(f'Cannot found {repr(envelope.resp_token)} in waitings')
            logger.debug(f'waitings: {list(self._waitings.keys())}')

    def run_main(self, coro):
        self._main_task = asyncio.Task(coro, loop=self._loop)

    def run_with_context(self, envelope, coro):
        task = asyncio.Task(coro, loop=self._loop)
        task.actor_ctx = self
        task.envelope = envelope
        return task

    async def _wrap_exception(self, action, args, kwargs):
        try:
            if asyncio.iscoroutinefunction(action):
                await action(self._actor, *args, **kwargs)
            else:
                action(self._actor, *args, **kwargs)
        except Exception as e:
            logger.exception("Error occurred while executing action")
            if self.req_token:
                self.sender.reply(e)

    def spawn(self, actor_type, *args, **kwargs):
        child = node.spawn(actor_type, *args, parent=self.ref, **kwargs)
        self._children.add(child)
        return child

    def remove_child(self, child):
        self._children.remove(child)
