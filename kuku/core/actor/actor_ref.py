import asyncio
import collections
import functools
import logging

from kuku import util
from kuku.core.actor import exception as exc
from kuku.core.actor import message as msg

__all__ = [
    'ActorRef'
]

logger = logging.getLogger(__name__)


def _get_context_or_error():
    current_task = asyncio.Task.current_task()
    if current_task is None or not hasattr(current_task, 'actor_ctx'):
        raise exc.OutOfContextError
    return current_task.actor_ctx


def _get_context_or_none():
    return getattr(asyncio.Task.current_task(), 'actor_ctx', None)


class ActorRef(object):
    nobody = util.create_named_singleton('Nobody')

    def __init__(self, mailbox, actor_type, uuid):
        self._mailbox = mailbox
        self.actor_type = actor_type
        self.uuid = uuid

    def tell(self, message, *, sender=None, msg_type=msg.MsgType.NORMAL):
        if sender is None:
            actor_ctx = _get_context_or_none()
            sender = actor_ctx.ref if actor_ctx is not None else self.nobody

        envelope = msg.Envelope(msg_type, message, sender)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'Tell {repr(sender)} -> {repr(self)}\n'
                         f'>\t[{msg_type.name}] {message}')
        self._mailbox.put(envelope)

    def ask(self, message, *, sender=None, timeout=None, msg_type=msg.MsgType.NORMAL):
        loop = asyncio.get_event_loop()
        fut = loop.create_future()

        actor_ctx = _get_context_or_error()
        sender = sender or actor_ctx.ref
        timeout = timeout or actor_ctx.default_timeout
        req_token = actor_ctx.issue_req_token(fut, timeout)

        envelope = msg.Envelope(msg_type, message, sender, req_token=req_token)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'Ask {repr(sender)} -> {repr(self)}\n'
                         f'>\t[{msg_type.name}] {message}\n'
                         f'>\treq_token: {repr(req_token)}')
        self._mailbox.put(envelope)
        return fut

    def reply(self, message, *, sender=None, msg_type=msg.MsgType.NORMAL):
        actor_ctx = _get_context_or_error()
        sender = sender or actor_ctx.ref
        resp_token = actor_ctx.req_token

        envelope = msg.Envelope(msg_type, message, sender, resp_token=resp_token)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'Reply {repr(sender)} -> {repr(self)}\n'
                         f'>\t[{msg_type.name}] {message}\n'
                         f'>\tresp_token: {repr(resp_token)}')
        self._mailbox.put(envelope)

    def reply_and_ask(self, message, *, sender=None, timeout=None, msg_type=msg.MsgType.NORMAL):
        loop = asyncio.get_event_loop()
        fut = loop.create_future()

        actor_ctx = _get_context_or_error()
        sender = sender or actor_ctx.ref
        req_token = actor_ctx.issue_req_token(fut, timeout)
        resp_token = actor_ctx.req_token

        envelope = msg.Envelope.normal(message, sender, req_token=req_token,
                                       resp_token=resp_token)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'Reply And Ask {repr(sender)} -> {repr(self)}\n'
                         f'>\t[{msg_type.name}] {message}\n'
                         f'>\treq_token: {repr(req_token)}\n'
                         f'>\tresp_token: {repr(resp_token)}')
        self._mailbox.put(envelope)

    def __getattr__(self, action_name):
        if action_name not in self.actor_type.rpc_actions:
            raise AttributeError(f'{repr(action_name)} is not registered as rpc')
        return functools.partial(self.rpc, action_name)

    def rpc(self, action_name, *args, timeout=None, sender=None, **kwargs):
        message = msg.RpcMessage(action_name, args, kwargs)
        action = self.actor_type.rpc_actions[action_name]

        if action.reply:
            return self.ask(message, sender=sender, timeout=timeout,
                            msg_type=msg.MsgType.RPC)
        else:
            self.tell(message, sender=sender, msg_type=msg.MsgType.RPC)

    def __repr__(self):
        return f'{self.actor_type.__name__}#{str(self.uuid)[:6]}'
