import inspect
from enum import Enum
from uuid import uuid4

from .context import ActorContext
from .mailbox import Mailbox
from .message import Envelope, SystemMessage

__all__ = (
    'ActorLifeCycle',
    'behavior',
    'ActorMeta',
    'AsyncActor',
    'base_actor'
)


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

    def __init__(self, loop, parent, init_args, init_kwargs):
        self.loop = loop
        self.parent = parent
        self.uuid = uuid4()
        self.life_cycle = ActorLifeCycle.born
        self.mailbox = Mailbox(self.loop)
        self.context = ActorContext(self)

        self.before_start(*init_args, **init_kwargs)

        self.execution = self.context.run(self._main())

    def before_start(self, *args, **kwargs):
        pass

    def before_die(self):
        pass

    def message_context_factory(self, envelope):
        return {'sender': envelope.sender,
                'reply': ''}

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
                self._open_envelope(envelope)
                if self.life_cycle == ActorLifeCycle.stopped:
                    break
            except Exception as e:
                print('Error occurred: {}'.format(e))
                # TODO: supervised by parent

        self.before_die()
        self.life_cycle = ActorLifeCycle.dead

    def _open_envelope(self, envelope):
        ctx = self.message_context_factory(envelope)
        behav = self._find_behavior(type(envelope.message))
        if inspect.iscoroutinefunction(behav):
            self.context.run_behavior(behav(self, envelope.message), ctx)
        else:
            self.context.set_msg_ctx(ctx)
            behav(self, envelope.message)
            self.context.reset_msg_ctx()

    @behavior(object)
    def _unhandled(self, message):
        print('UnRegistered message type: {}'.format(type(message)))

    @behavior(SystemMessage)
    def _handle_system_message(self, message):
        if message.command == 'kill':
            self.life_cycle = ActorLifeCycle.stopped


base_actor = AsyncActor
