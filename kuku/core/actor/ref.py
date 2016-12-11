from asyncio import get_event_loop, Task
from functools import partial

from .message import Envelope

__all__ = (
    'ActorRef',
)


def get_context_or_error():
    return Task.current_task().actor_ctx


def get_context_or_none():
    return getattr(Task.current_task(), 'actor_ctx', None)


class ActorRef(object):
    nobody = object()

    def __init__(self, actor):
        self._mailbox = actor.mailbox
        self._msg_types = {behav.__name__: msg_type
                           for (msg_type, behav) in actor.behaviors.items()}
        self.actor_type = type(actor)
        self.actor_uuid = actor.uuid

    def tell(self, message, *, sender=None):
        if sender is None:
            ctx = get_context_or_none()
            sender = ctx.ref if ctx is not None else self.nobody

        envelope = Envelope(message, sender)
        self._mailbox.put(envelope)

    def ask(self, message, *, sender=None, timeout=None):
        loop = get_event_loop()  
        fut = loop.create_future()

        ctx = get_context_or_error()
        sender = sender or ctx.ref
        timeout = timeout or ctx.default_timeout
        req_token = ctx.issue_req_token(fut, timeout)

        envelope = Envelope(message, sender, req_token=req_token)
        self._mailbox.put(envelope)
        return fut

    def reply(self, message, *, sender=None):
        ctx = get_context_or_error()
        sender = sender or ctx.ref
        resp_token = ctx.req_token

        envelope = Envelope(message, sender, resp_token=resp_token)
        self._mailbox.put(envelope)

    def reply_and_ask(self, message, *, sender=None, timeout=None):
        loop = get_event_loop()
        fut = loop.create_future()

        ctx = get_context_or_error()
        sender = sender or ctx.ref
        req_token = ctx.issue_req_token(fut, timeout)
        resp_token = ctx.req_token

        envelope = Envelope(message, sender, req_token=req_token, resp_token=resp_token)
        self._mailbox.put(envelope)

    def __getattr__(self, behav):
        if behav not in self._msg_types:
            raise AttributeError('{} is not registered as a behavior'.format(behav))
        msg_type = self._msg_types[behav]
        return partial(self._rpc, msg_type)

    def _rpc(self, msg_type, *args, sender=None, timeout=None, wait=True, **kwargs):
        message = msg_type(*args, **kwargs)
        if wait:
            return self.ask(message, timeout=timeout)
        else:
            self.tell(message, sender=sender)
