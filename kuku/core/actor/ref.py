from asyncio import Future, wait_for, ensure_future, get_event_loop
from functools import partial

from kuku.core.actor.context import get_current_context
from kuku.core.message import Envelope

__all__ = [
    'ActorRef',
    'RpcActorRef',
    'FunctionRef',
]


def get_current_context_sender():
    ctx = get_current_context()
    return ctx.sender if ctx is not None else None


def get_current_context_timeout():
    ctx = get_current_context()
    return ctx.default_timeout if ctx is not None else None


class ActorRef(object):
    nobody = object()

    def __init__(self, mailbox):
        self._mailbox = mailbox

    def tell(self, message, sender=None):
        sender = sender or get_current_context_sender() or self.nobody
        envelope = Envelope(message, sender=sender)
        self._mailbox.put(envelope)

    async def ask(self, message, timeout=None):
        fut = Future(loop=get_event_loop())

        def fn(envelope):
            if not fut.done():
                fut.set_result(envelope.message)

        self._mailbox.put(Envelope(message, sender=FunctionRef(fn)))
        return await wait_for(fut, timeout)


class RpcActorRef(ActorRef):
    def __init__(self, mailbox, behaviors):
        super().__init__(mailbox)
        self._msg_types = {behav.__name__: msg_type
                           for (msg_type, behav) in behaviors.items()}

    def __getattr__(self, behav):
        if behav not in self._msg_types:
            raise AttributeError('{} is not registered as a behavior'.format(behav))
        msg_type = self._msg_types[behav]
        return partial(self._rpc, msg_type)

    def _rpc(self, msg_type, *args, **kwargs):
        timeout = kwargs.pop('timeout', get_current_context_timeout())
        message = msg_type(*args, **kwargs)
        return ensure_future(self.ask(message, timeout=timeout), loop=get_event_loop())


class FunctionRef(object):
    def __init__(self, fn):
        self.fn = fn

    def tell(self, message, sender=None):
        sender = sender or get_current_context_sender() or ActorRef.nobody
        self.fn(Envelope(message, sender))

    async def ask(self, message):
        raise NotImplementedError('Cannot ask to FunctionRef')
