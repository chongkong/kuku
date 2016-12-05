import inspect
from uuid import uuid4

from .base import ActorLifeCycle, behavior, MSG_TYPE_KEY, UnknownMessageTypeError
from .context import ActorContext, MessageContext
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

    @property
    def sender(self):
        return self.context.sender

    def _find_behavior(self, msg_type):
        for type_ in msg_type.mro():
            if type_ in self.behaviors:
                return self.behaviors[type_]
        raise UnknownMessageTypeError('Unknown message type: {}'.format(msg_type))

    async def _main(self):
        while True:
            try:
                envelope = await self.mailbox.get()
                msg_ctx = MessageContext(envelope)
                if msg_ctx.resp_token:
                    if isinstance(envelope.message, Exception):
                        self.context.raise_reply_exc(
                            msg_ctx.resp_token, envelope.message, msg_ctx)
                    else:
                        self.context.resolve_reply(
                            msg_ctx.resp_token, envelope.message, msg_ctx)
                else:
                    behav = self._find_behavior(type(envelope.message))
                    if inspect.iscoroutinefunction(behav):
                        self.context.run_behavior(
                            self._monitor_coro_behav(behav, envelope.message), msg_ctx)
                    else:
                        self.context.set_msg_ctx(msg_ctx)
                        behav(self, envelope.message)
                        self.context.reset_msg_ctx()

                if self.life_cycle == ActorLifeCycle.stopped:
                    break
            except Exception as e:
                print('Error occurred: {}'.format(e))
                # TODO: supervised by parent

        self.before_die()
        self.life_cycle = ActorLifeCycle.dead

    async def _monitor_coro_behav(self, behav, message):
        try:
            await behav(self, message)
        except Exception as e:
            if self.context.req_token is not None:
                pass

    @behavior(object)
    def _unhandled(self, message):
        print('UnRegistered message type: {}'.format(type(message)))

    @behavior(SystemMessage)
    def _handle_system_message(self, message):
        if message.command == 'kill':
            self.life_cycle = ActorLifeCycle.stopped


base_actor = AsyncActor
