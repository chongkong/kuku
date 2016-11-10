from asyncio import Future, wait_for

from kuku.core.message import Envelope

__all__ = [
    'ActorRef',
    'SenderWrappedActorRef',
    'FunctionRef'
]


class ActorRef(object):
    nobody = object()

    def __init__(self, mailbox, loop):
        self._mailbox = mailbox
        self._loop = loop

    def tell(self, message, sender=nobody):
        envelope = Envelope(sender, message)
        self._mailbox.put(envelope)

    async def ask(self, message, timeout=None):
        fut = wait_for(Future(loop=self._loop), timeout=timeout)

        def fn(msg):
            if not fut.done():
                fut.set_result(msg)

        self._mailbox.put(Envelope(FunctionRef(fn), message))


class SenderWrappedActorRef(object):
    def __init__(self, actor_ref, sender_ref):
        self._receiver = actor_ref
        self._sender = sender_ref

    def tell(self, message, sender=None):
        return self._receiver.tell(message, sender or self._sender)

    async def ask(self, message, timeout=None):
        return await self._receiver.ask(message, timeout)


class FunctionRef(object):
    def __init__(self, fn):
        self.fn = fn

    def tell(self, message):
        self.fn(message)

    async def ask(self, message):
        raise NotImplementedError('Cannot ask to FunctionRef')
