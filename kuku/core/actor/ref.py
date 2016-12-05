from asyncio import get_event_loop, CancelledError, TimeoutError
from functools import partial

from .message import Envelope

__all__ = (
    'ActorRef',
    'FunctionRef',
)


def get_context(must=False):
    loop = get_event_loop()
    if must and not hasattr(loop, 'actor_context'):
        raise AssertionError('function is not called within actor context')
    return getattr(get_event_loop(), 'actor_context', None)


def get_sender(must=False):
    context = get_context(must)
    sender = context.sender if context else None
    if must and sender is None:
        raise AssertionError('sender should not be None')
    return sender


def get_default_timeout(must=False):
    context = get_context(must)
    timeout = context.default_timeout if context else None
    if must and timeout is None:
        raise AssertionError('timeout should not be None')
    return timeout


class ActorRef(object):
    nobody = object()

    def __init__(self, actor):
        self._mailbox = actor.mailbox
        self._msg_types = {behav.__name__: msg_type
                           for (msg_type, behav) in actor.behaviors.items()}
        self.actor_type = type(actor)
        self.actor_uuid = actor.uuid

    def tell(self, message, *, sender=None):
        sender = sender or get_sender() or self.nobody
        envelope = Envelope(message, sender)
        self._mailbox.put(envelope)

    def ask(self, message, *, sender=None, timeout=None):
        # We have to wait on caller's loop, which is the loop of current thread
        loop = get_event_loop()  
        fut = loop.create_future()

        context = get_context(True)
        sender = sender or context.sender
        timeout = timeout or context.default_timeout
        req_token = context.issue_req_token(fut, timeout)

        envelope = Envelope(message, sender, req_token=req_token)
        self._mailbox.put(envelope)
        return fut

    def reply(self, message, *, sender=None):
        context = get_context(True)
        sender = sender or context.sender
        resp_token = context.req_token

        envelope = Envelope(message, sender, resp_token=resp_token)
        self._mailbox.put(envelope)

    def reply_and_ask(self, message, *, sender=None, timeout=None):
        # We have to wait on caller's loop, which is the loop of current thread
        loop = get_event_loop()
        fut = loop.create_future()

        context = get_context(True)
        sender = sender or context.sender
        req_token = context.issue_req_token(fut, timeout)
        resp_token = context.req_token

        envelope = Envelope(message, sender, req_token=req_token, resp_token=resp_token)
        self._mailbox.put(envelope)

    def __getattr__(self, behav):
        if behav not in self._msg_types:
            raise AttributeError('{} is not registered as a behavior'.format(behav))
        msg_type = self._msg_types[behav]
        return partial(self._rpc, msg_type)

    def _rpc(self, msg_type, *args, sender=None, timeout=None, **kwargs):
        message = msg_type(*args, **kwargs)
        if sender:
            self.tell(message, sender)
        else:
            return self.ask(message, timeout=timeout)


class FunctionRef(object):
    def __init__(self, fn):
        self.fn = fn

    def tell(self, message, sender=None):
        sender = sender or get_sender() or ActorRef.nobody
        self.fn(Envelope(message, sender))

    async def ask(self, message):
        raise NotImplementedError('Cannot ask to FunctionRef')
