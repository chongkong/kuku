from asyncio import wait_for, ensure_future, get_event_loop
from enum import Enum
from uuid import uuid4

from kuku.core.actor.mailbox import Mailbox
from kuku.core.actor.ref import ActorRef, RpcActorRef, patch_sender
from kuku.core.message import Envelope, SystemMessage


__all__ = [
    'ActorLifeCycle',
    'behavior',
    'ActorMeta',
    'AsyncActor',
    'base_actor'
]


class ActorLifeCycle(Enum):
    born = 1
    running = 2
    stopped = 3
    dead = 4


def behavior(msg_type):
    def decorator(f):
        f.msg_type = msg_type
        return f
    return decorator


class ActorMeta(type):
    @classmethod
    def __prepare__(metacls, name, bases):
        return {'behaviors': {}}

    def __new__(mcs, name, bases, attrs, **kwargs):
        actor = super().__new__(mcs, name, bases, attrs)

        class_behaviors = [
            attr for attr in attrs.values()
            if hasattr(attr, 'msg_type')]
        base_behaviors = [
            attr for base in bases
            for attr in base.__dict__.values()
            if hasattr(attr, 'msg_type')]

        for behav in class_behaviors + base_behaviors:
            msg_type = getattr(behav, 'msg_type')
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
        self.on_start()

        self.fire(self._main())

    def on_start(self):
        pass

    def actor_ref_factory(self):
        return ActorRef(self._mailbox, self._loop)

    @property
    def ref(self):
        return self.actor_ref_factory()

    @property
    def sender(self):
        if self.context and 'sender' in self.context:
            return self.context['sender']

    def fire(self, coroutine):
        return ensure_future(coroutine, loop=self._loop)

    def until(self, coroutine, timeout=None):
        return wait_for(coroutine, timeout, loop=self._loop)

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
                self.context = {
                    'sender': patch_sender(
                        envelope.sender_ref, self.ref, self.default_timeout)}
                behav = self._find_behavior(type(envelope.message))
                if behav is not None:
                    await behav(self, envelope.message)
                self.context = None

                if self.life_cycle == ActorLifeCycle.stopped:
                    self.life_cycle = ActorLifeCycle.dead
                    break

            except Exception as e:
                print('Error occurred: {}'.format(e))

    @behavior(object)
    async def handle_default(self, message):
        print('UnRegistered message type: {}'.format(type(message)))

    @behavior(SystemMessage)
    async def handle_system_message(self, message):
        if message.command == 'kill':
            self.life_cycle = ActorLifeCycle.stopped


class RpcActor(AsyncActor):
    def actor_ref_factory(self):
        return RpcActorRef(self._mailbox, self._loop,
                           self.behaviors, self.default_timeout)


base_actor = RpcActor


class LoggingActor(base_actor):
    @behavior(str)
    async def handle_message(self, message):
        print(message)


class EchoActor(base_actor):
    @behavior(str)
    async def handle_message(self, message):
        self.sender.tell(message)


if __name__ == '__main__':
    log = LoggingActor().ref
    log.tell('hello')
    log.handle_message('world')

    echo = EchoActor().ref
    echo.tell('yollo', sender=log)
