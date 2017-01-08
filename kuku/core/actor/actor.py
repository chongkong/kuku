import inspect
from uuid import uuid4

from .action_tree import ActionTree
from .base import ActorLifeCycle, UnknownMessageTypeError
from .context import ActorContext
from .mailbox import Mailbox
from .message import SystemMessage

__all__ = (
    'ActorMeta',
    'Actor',
    'base_actor'
)


class ActorMeta(type):
    def __new__(mcs, name, bases, attrs):
        actor_class = super().__new__(mcs, name, bases, attrs)

        actor_actions = [
            attr for attr in attrs.values()
            if hasattr(attr, 'trigger_tags')
        ]
        base_actors_actions = [
            attr for base in bases
            for attr in base.__dict__.values()
            if hasattr(attr, 'trigger_tags')
        ]

        actor_class.action_tree = ActionTree(
            base_actors_actions + actor_actions)
        return actor_class


class Actor(object, metaclass=ActorMeta):
    default_timeout = 60
    action_tree = None

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

    async def _main(self):
        while True:
            try:
                envelope = await self.mailbox.get()
                self._handle_envelope(envelope)

                if self.life_cycle == ActorLifeCycle.stopped:
                    break
            except Exception as e:
                print('Error occurred: {}'.format(e))
                # TODO: supervised by parent

        self.before_die()
        self.life_cycle = ActorLifeCycle.dead

    async def _handle_envelope(self, envelope):
        if envelope.resp_token:
            self.context.resolve_reply(envelope)
            return

        if envelope.internal:
            self._handle_internal(envelope.message)
            return

        if envelope.rpc:
            action, message = self.action_tree.resolve_rpc(
                envelope.rpc.action_name, envelope.rpc.args,
                envelope.rpc.kwargs)
        elif envelope.message:
            action = self.action_tree.resolve_message_action(envelope.message)
            message = envelope.message
        else:
            return

        with self.context.msg_scope(envelope):
            if inspect.iscoroutinefunction(action):
                self.context.run_coroutine_behavior(action(self, message))
            else:
                action(self, message)

    def _handle_internal(self, message):
        if message.command == 'kill':
            self.life_cycle = ActorLifeCycle.stopped


base_actor = Actor
