from asyncio import wait_for, ensure_future, get_event_loop, Future
from enum import Enum
from uuid import uuid4

from kuku.core.actor.mailbox import Mailbox
from kuku.core.actor.ref import SenderWrappedActorRef, ActorRef
from kuku.core.message import Envelope, SystemMessage


__all__ = [
    'ActorLifeCycle',
    'behavior',
    'ActorMeta',
    'AsyncActor'
]


class ActorLifeCycle(Enum):
    born = 1
    running = 2
    stopped = 3
    dead = 4


def behavior(msg_type):
    def decorator(f):
        f.__msg_type = msg_type
        return f
    return decorator


class ActorMeta(type):
    def __new__(mcs, name, bases, attrs, **kwargs):
        actor = super().__new__(mcs, name, bases, attrs)

        class_behaviors = [
            attr for attr in attrs.values()
            if hasattr(attr, '__msg_type')]
        base_behaviors = [
            attr for base in bases
            for attr in base.__dict__.values()
            if hasattr(attr, '__msg_type')]

        for behav in class_behaviors + base_behaviors:
            msg_type = getattr(behav, '__msg_type')
            if msg_type not in actor.behaviors:
                actor.behaviors[msg_type] = behav

        return actor


class AsyncActor(metaclass=ActorMeta):
    default_timeout = 60
    behaviors = {}

    def __init__(self, parent=ActorRef.nobody, loop=None):
        self.parent = parent
        self.uuid = uuid4()
        self.life_cycle = ActorLifeCycle.born
        self._loop = loop or get_event_loop()
        self._mailbox = Mailbox(loop=self._loop)

        self.context = None

        self.run(self._main())

    @property
    def ref(self):
        return ActorRef(self._mailbox, self._loop)

    @property
    def sender(self):
        if self.context and 'sender' in self.context:
            return self.context['sender']

    def run(self, coroutine, timeout=None, callback=None):
        if timeout is None:
            fut = ensure_future(coroutine, loop=self._loop)
        else:
            fut = wait_for(coroutine, timeout=timeout, loop=self._loop)
        if callback is not None:
            fut.add_done_callback(callback)
        return fut

    def _find_behavior(self, msg_type):
        for type_ in msg_type.mro():
            if type_ in self.behaviors:
                return self.behaviors[type_]
        raise TypeError('Unknown message type: {}'.format(msg_type))

    async def _main(self):
        while True:
            try:
                envelope = await self._mailbox.get()
                if not isinstance(envelope, Envelope):
                    print('Message should be wrapped in an Envelope')
                    continue
                self.context = dict(sender=SenderWrappedActorRef(self.ref, envelope.sender_ref))
                behav = self._find_behavior(type(envelope.message))
                if behav is not None:
                    await behav(self, envelope.message)
                self.context = None

                if self.life_cycle == ActorLifeCycle.stopped:
                    self.life_cycle = ActorLifeCycle.dead
                    break

            except Exception as e:
                print('Error occurred: {}'.format(e))
                pass

    @behavior(object)
    async def handle_message(self, message):
        print('UnRegistered message type: {}'.format(type(message)))

    @behavior(SystemMessage)
    async def handle_system_message(self, message):
        if message.command == 'kill':
            self.life_cycle = ActorLifeCycle.stopped


class LoggingActor(AsyncActor):
    @behavior(str)
    async def handle_message(self, message):
        print(message)


class EchoActor(AsyncActor):
    @behavior(str)
    async def handle_message(self, message):
        self.sender.tell(message)


if __name__ == '__main__':
    log = LoggingActor().ref
    echo = EchoActor().ref
    echo.tell('yollo', sender=log)
