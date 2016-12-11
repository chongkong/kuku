import inspect
from uuid import uuid4

from .base import ActorLifeCycle, behavior, MSG_TYPE_KEY, UnknownMessageTypeError
from .context import ActorContext
from .mailbox import Mailbox
from .message import SystemMessage

__all__ = (
    'ActorMeta',
    'AsyncActor',
    'base_actor'
)


class ActorMeta(type):
    @classmethod
    def __prepare__(mcs, name, bases):
        return {'behaviors': {}}

    def __new__(mcs, name, bases, attrs, **kwargs):
        actor = super().__new__(mcs, name, bases, attrs)

        class_behaviors = [
            attr for attr in attrs.values()
            if hasattr(attr, MSG_TYPE_KEY)]
        base_behaviors = [
            attr for base in bases
            for attr in base.__dict__.values()
            if hasattr(attr, MSG_TYPE_KEY)]

        for behav in class_behaviors + base_behaviors:
            msg_type = getattr(behav, MSG_TYPE_KEY)
            if msg_type not in actor.behaviors:
                actor.behaviors[msg_type] = behav

        return actor


class AsyncActor(metaclass=ActorMeta):
    default_timeout = 60
    behaviors = {}

    def __init__(self, loop, parent, init_args, init_kwargs):
        self.parent = parent
        self.uuid = uuid4()
        self.life_cycle = ActorLifeCycle.born
        self.mailbox = Mailbox(loop)
        self.context = ActorContext(self, loop)

        self.before_start(*init_args, **init_kwargs)

        self.execution = self.context.run_main(self._main())

    def before_start(self, *args, **kwargs):
        pass

    def before_die(self):
        pass

    @property
    def sender(self):
        return self.context.sender

    def _find_behavior(self, msg):
        for type_ in type(msg).mro():
            if type_ in self.behaviors:
                return self.behaviors[type_]
        raise UnknownMessageTypeError('Unknown message type: {}'.format(type(msg)))

    async def _main(self):
        while True:
            try:
                envelope = await self.mailbox.get()
                if envelope.resp_token:
                    self.context.resolve_reply(envelope)
                else:
                    behav = self._find_behavior(envelope.message)
                    with self.context.msg_scope(envelope):
                        if inspect.iscoroutinefunction(behav):
                            self.context.run_coroutine_behavior(
                                behav(self, envelope.message))
                        else:
                            behav(self, envelope.message)

                if self.life_cycle == ActorLifeCycle.stopped:
                    break
            except Exception as e:
                print('Error occurred: {}'.format(e))
                # TODO: supervised by parent

        self.before_die()
        self.life_cycle = ActorLifeCycle.dead

    @behavior(object)
    def _unhandled(self, message):
        print('UnRegistered message type: {}'.format(type(message)))

    @behavior(SystemMessage)
    def _handle_system_message(self, message):
        if message.command == 'kill':
            self.life_cycle = ActorLifeCycle.stopped


base_actor = AsyncActor
