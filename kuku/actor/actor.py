import asyncio
import enum
import logging
import uuid

from kuku.actor import action as tree
from kuku.actor import context as ctx
from kuku.actor import exception as exc
from kuku.actor import message as msg

from kuku.actor import mailbox

__all__ = [
    'ActorState',
    'ActorMeta',
    'Actor'
]

logger = logging.getLogger(__name__)


class ActorState(enum.Enum):
    BORN = 1
    RUNNING = 2
    STOPPED = 3
    DEAD = 4


class ActorMeta(type):
    def __new__(mcs, name, bases, attrs):
        actor_class = super().__new__(mcs, name, bases, attrs)

        trigger_actions = []
        rpc_actions = {}

        def pick_trigger_or_rpc(meth):
            if hasattr(meth, 'triggers'):
                trigger_actions.append(meth)
            if hasattr(meth, 'rpc'):
                rpc_actions[meth.__name__] = meth

        for method in attrs.values():
            pick_trigger_or_rpc(method)
        for base_class in bases:
            for method in base_class.__dict__.values():
                pick_trigger_or_rpc(method)

        actor_class.action_tree = tree.ActionTree(trigger_actions)
        actor_class.rpc_actions = rpc_actions
        return actor_class


class Actor(object, metaclass=ActorMeta):
    default_timeout = 60
    action_tree = None  # filled by ActorMeta
    rpc_actions = None  # filled by ActorMeta

    def __init__(self, loop, parent, init_args, init_kwargs):
        self.parent = parent
        self.uuid = uuid.uuid4()
        self.life_state = ActorState.BORN
        self.mailbox = mailbox.Mailbox(loop)
        self.context = ctx.ActorContext(self, loop)
        self.logger = logging.getLogger(f'{self}')

        self.before_start(*init_args, **init_kwargs)
        self.context.run_main(self._main())

    def before_start(self, *args, **kwargs):
        pass

    def before_die(self):
        pass

    @property
    def sender(self):
        return self.context.sender

    async def _main(self):
        while True:
            try:
                envelope = await self.mailbox.get()
                if envelope.type == msg.MsgType.INTERNAL:
                    self._handle_internal(envelope.message)
                    if self.life_state == ActorState.STOPPED:
                        break
                self.context.run_with_context(envelope, self._handle_envelope(envelope))
            except exc.Error:
                self.logger.exception(f'Error occurred in {self}')
                # TODO: supervised by parent

        self.before_die()
        self.life_state = ActorState.DEAD

    async def _handle_envelope(self, envelope):
        try:
            if envelope.resp_token:
                self.logger.debug(f'Received reply for {repr(envelope.resp_token)}')
                self.context.resolve_reply(envelope)
                return

            message = envelope.message
            if envelope.type == msg.MsgType.RPC:
                action = self.rpc_actions.get(message.action_name)
                self.logger.debug(f'Received rpc {message}')
                if action is None:
                    raise exc.BadMessageError(f'No RPC found for {repr(message.action_name)}')
                if asyncio.iscoroutinefunction(action):
                    await action(self, *message.args, **message.kwargs)
                else:
                    action(self, *message.args, **message.kwargs)
            elif envelope.type == msg.MsgType.NORMAL:
                action = self.action_tree.resolve_action(message)
                self.logger.debug(f'Received message {repr(message)}')
                if action is None:
                    raise exc.BadMessageError(f'No handler found for {repr(message)}')
                if asyncio.iscoroutinefunction(action):
                    await action(self, message)
                else:
                    action(self, message)
            else:
                raise exc.BadEnvelopeError(f'Invalid envelope type {envelope.type.name}')
        except Exception as e:
            logger.exception("Error occurred while executing action")
            if self.context.req_token:
                self.sender.reply(e, msg_type=msg.MsgType.ERROR)

    def _handle_internal(self, message):
        logger.debug(f'Received internal message {repr(message)}')
        if message == 'die':
            self.life_state = ActorState.STOPPED

    def __repr__(self):
        return f'{type(self).__name__}#{str(self.uuid)[:6]}'
