from .base import MultipleRootTriggersError


class TriggerTag(object):
    __slots__ = ['trigger_type', 'args']

    def __init__(self, trigger_type, args):
        self.trigger_type = trigger_type
        self.args = args


def create_trigger_decorator(trigger_type):
    def decorator_declaration(*args):
        def decorator(f):
            if hasattr(f, 'trigger_tags'):
                f.trigger_tags.append(TriggerTag(trigger_type, args))
            else:
                f.trigger_tags = [TriggerTag(trigger_type, args)]
        return decorator
    return decorator_declaration


def child_trigger(trigger_type, args):
    def class_decorator(cls):
        assert issubclass(cls, Trigger)
        if cls.parent_trigger_nodes is None:
            cls.parent_triggers = [TriggerTag(trigger_type, args)]
        else:
            cls.parent_triggers.append(TriggerTag(trigger_type, args))
    return class_decorator


class Trigger(object):
    parent_triggers = None

    def add_trigger(self, trigger_args, action):
        raise NotImplementedError

    def resolve(self, message):
        raise NotImplementedError

    def synthesize(self, trigger_args, msg_args, msg_kwargs):
        raise NotImplementedError


class MessageTypeTrigger(Trigger):
    def __init__(self):
        self.actions = {}

    def add_trigger(self, trigger_args, action):
        msg_type = trigger_args[0]
        self.actions[msg_type] = action

    def resolve(self, message):
        for msg_type in type(message).mro():
            if msg_type in self.actions.keys():
                return self.actions[msg_type]

    def synthesize(self, trigger_args, msg_args, msg_kwargs):
        msg_type = trigger_args[0]
        return msg_type(*msg_args, **msg_kwargs)

on_message_type = create_trigger_decorator(MessageTypeTrigger)


class ActionTree(object):
    def __init__(self, actions):
        self.root = None
        self.actions = {act.__name__: act for act in actions}
        self.triggers = {}
        triggers = {}

        for action in actions:
            if not hasattr(action, 'triggers'):
                continue
            for tag in action.trigger_tags:
                if tag.trigger_type in triggers:
                    trigger = triggers[tag.trigger_type]
                else:
                    trigger = tag.trigger_type()
                    triggers[tag.trigger_type] = trigger
                trigger.add_trigger(tag.args, action)
                if action.__name__ not in self.triggers:
                    self.triggers[action.__name__] = trigger

        for trigger_type in triggers.keys():
            trigger = triggers[trigger_type]
            if trigger_type.parent_triggers is not None:
                for item in trigger_type.parent_triggers:
                    if item.trigger_type in triggers:
                        parent_trigger = triggers[item.trigger_type]
                    else:
                        parent_trigger = item.trigger_type()
                        triggers[parent_trigger] = parent_trigger
                    parent_trigger.add_trigger(item.args, trigger)
            elif self.root is None:
                self.root = triggers[trigger_type]
            else:
                raise MultipleRootTriggersError

    def resolve_message_action(self, message):
        trigger_or_action = self.root
        while isinstance(trigger_or_action, Trigger):
            trigger_or_action = trigger_or_action.resolve(message)
        return trigger_or_action

    def resolve_rpc(self, action_name, msg_args, msg_kwargs):
        if action_name in self.triggers:
            action = self.actions[action_name]
            trigger = self.triggers[action_name]
            message = trigger.synthesize(
                action.triggers[0].args, msg_args, msg_kwargs)
            return action, message
