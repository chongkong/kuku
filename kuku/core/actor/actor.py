import inspect
from asyncio import get_event_loop
from enum import Enum
from uuid import uuid4

from kuku.core.actor.context import ActorContext
from kuku.core.actor.mailbox import Mailbox
from kuku.core.actor.ref import ActorRef, RpcActorRef
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

    def __init__(self,
                 parent=ActorRef.nobody,
                 loop=None,
                 args=None,
                 kwargs=None):
        self.parent = parent
        self.uuid = uuid4()
        self.life_cycle = ActorLifeCycle.born
        self.loop = loop or get_event_loop()
        self.mailbox = Mailbox(self.loop)
        self.context = ActorContext(self)

        self.before_start(*args, **kwargs)

        self.context.run(self._main())

    def before_start(self, *args, **kwargs):
        pass

    def before_die(self):
        pass

    def actor_ref_factory(self):
        return ActorRef(self.mailbox)

    def context_factory(self, envelope):
        return {'sender': envelope.sender}

    @property
    def ref(self):
        return self.actor_ref_factory()

    @property
    def sender(self):
        return self.context.sender

    def _find_behavior(self, msg_type):
        for type_ in msg_type.mro():
            if type_ in self.behaviors:
                return self.behaviors[type_]
        raise TypeError('Unknown message type: {}'.format(msg_type))

    async def _main(self):
        while True:
            try:
                envelope = await self.mailbox.get()
                assert isinstance(envelope, Envelope)
                await self._open_envelope(envelope)
                if self.life_cycle == ActorLifeCycle.stopped:
                    break
            except Exception as e:
                print('Error occurred: {}'.format(e))
                # TODO: supervised by parent

        self.before_die()
        self.life_cycle = ActorLifeCycle.dead

    async def _open_envelope(self, envelope):
        ctx = self.context_factory(envelope)
        behav = self._find_behavior(type(envelope.message))
        if inspect.iscoroutinefunction(behav):
            self.context.run_with_context(
                behav(self, envelope.message), ctx)
        else:
            self.context.push(ctx)
            behav(self, envelope.message)
            self.context.pop()

    @behavior(object)
    def unhandled(self, message):
        print('UnRegistered message type: {}'.format(type(message)))

    @behavior(SystemMessage)
    def handle_system_message(self, message):
        if message.command == 'kill':
            self.life_cycle = ActorLifeCycle.stopped


class RpcActor(AsyncActor):
    def actor_ref_factory(self):
        return RpcActorRef(self.mailbox, self.behaviors)


base_actor = RpcActor


class LoggingActor(base_actor):
    @behavior(str)
    def handle_message(self, message):
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

    from asyncio import ensure_future
    ensure_future(echo.ask('foo')).add_done_callback(lambda fut: print(fut.result()))
