import collections

from kuku.actor import exception as exc

__all__ = [
    'rpc',
    'TriggerMapping',
    'MessageTypeTriggerMapping',
    'on_message_type',
    'ActionTree',
]


def _field_set_decorator(**fields):
    def decorator(f):
        for k, v in fields.items():
            setattr(f, k, v)
        return f
    return decorator


def _field_add_decorator(field_name, value):
    def decorator(f):
        if not hasattr(f, field_name) or getattr(f, field_name) is None:
            setattr(f, field_name, [])
        getattr(f, field_name).append(value)
        return f
    return decorator


def rpc(f=None, reply=False):
    deco = _field_set_decorator(rpc=True, reply=reply)
    if f is not None:
        return deco(f)
    else:
        return deco


Trigger = collections.namedtuple('Trigger', [
    'mapping_type',
    'args'
])


def create_trigger_decorator(mapping_type):
    def decorator_decl(*args):
        trigger = Trigger(mapping_type, args)
        return _field_add_decorator('triggers', trigger)
    return decorator_decl


def child_mapping(mapping_type, *args):
    trigger = Trigger(mapping_type, args)
    return _field_add_decorator('parent_triggers', trigger)


class TriggerMapping(object):
    parent_triggers = None

    def put(self, trigger_args, mapping_or_action):
        raise NotImplementedError

    def resolve(self, message):
        raise NotImplementedError


class MessageTypeTriggerMapping(TriggerMapping):
    def __init__(self):
        self.items = {}

    def put(self, trigger_args, item):
        msg_type = trigger_args[0]
        self.items[msg_type] = item

    def resolve(self, message):
        for msg_type in type(message).mro():
            if msg_type in self.items.keys():
                return self.items[msg_type]

    def __repr__(self):
        mappings = ', '.join(f'{repr(k)}->{repr(v)}'
                             for k, v in self.items.items())
        return f'{type(self).__name__}({mappings})'

on_message_type = create_trigger_decorator(MessageTypeTriggerMapping)


class ActionTree(object):
    def __init__(self, actions):
        self.root = None
        self.actions = {action.__name__: action for action in actions}
        self.mappings = {}

        for action in actions:
            for trigger in action.triggers:
                self._register(trigger, action)

    def _register(self, trigger, mapping_or_action):
        if trigger.mapping_type not in self.mappings:
            self.mappings[trigger.mapping_type] = trigger.mapping_type()
        mapping = self.mappings[trigger.mapping_type]
        mapping.put(trigger.args, mapping_or_action)
        if mapping.parent_triggers:
            for parent_trigger in mapping.parent_triggers:
                self._register(parent_trigger, mapping)
        elif self.root is None:
            self.root = mapping
        elif type(self.root) != type(mapping):
            raise exc.MultipleRootMappingsError(
                f'{type(self.root)}, {type(mapping)}')

    def resolve_action(self, message):
        mapping_or_action = self.root
        while isinstance(mapping_or_action, TriggerMapping):
            mapping_or_action = mapping_or_action.resolve(message)
        if mapping_or_action is not None:
            return mapping_or_action
        raise exc.MessageResolveError

    def __repr__(self):
        fields = ', '.join(f'{k}={v}' for k, v in self.__dict__.items())
        return f'ActionTree({fields})'
