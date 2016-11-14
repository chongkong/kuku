import types
from asyncio import Future, wait_for, ensure_future
from functools import wraps

from kuku.core.message import Envelope

__all__ = [
    'ActorRef',
    'RpcActorRef',
    'FunctionRef',
    'patch_sender'
]


class ActorRef(object):
    nobody = object()

    def __init__(self, mailbox, loop):
        self._mailbox = mailbox
        self._loop = loop

    def tell(self, message, sender=nobody):
        envelope = Envelope(message, sender=sender)
        self._mailbox.put(envelope)

    async def ask(self, message, timeout=None):
        fut = Future(loop=self._loop)

        def fn(envelope):
            if not fut.done():
                fut.set_result(envelope.message)

        self._mailbox.put(Envelope(message, sender=FunctionRef(fn)))
        return await wait_for(fut, timeout)


def patch_sender(actor_ref, default_sender, default_timeout):
    if actor_ref is ActorRef.nobody:
        return actor_ref

    original_tell = actor_ref.tell
    original_ask = actor_ref.ask

    @wraps(original_tell)
    def patched_tell(self, message, sender=None):
        original_tell(message, sender or default_sender)

    @wraps(original_ask)
    async def patched_ask(self, message, timeout=None):
        return await original_ask(message, timeout or default_timeout)

    actor_ref.tell = types.MethodType(patched_tell, actor_ref)
    actor_ref.ask = types.MethodType(patched_ask, actor_ref)

    return actor_ref


class RpcActorRef(ActorRef):
    def __init__(self, mailbox, loop, behaviors):
        super().__init__(mailbox, loop)

        for msg_type, behav in behaviors.items():
            def rpc(slf, *args, **kwargs):
                timeout = kwargs.pop('timeout', None)
                msg = msg_type(*args, **kwargs)
                return ensure_future(slf.ask(msg, timeout=timeout), loop=loop)
            setattr(self, behav.__name__, types.MethodType(rpc, self))


class FunctionRef(object):
    def __init__(self, fn):
        self.fn = fn

    def tell(self, message, sender=ActorRef.nobody):
        self.fn(Envelope(message, sender))

    async def ask(self, message):
        raise NotImplementedError('Cannot ask to FunctionRef')
