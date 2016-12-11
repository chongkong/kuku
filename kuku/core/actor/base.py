from enum import Enum
import logging

__all__ = (
    'logger',
    'Error',
    'UnknownMessageTypeError',
    'ActorLifeCycle',
    'MSG_TYPE_KEY',
    'behavior'
)


logger = logging.getLogger('kuku.core.actor')


class Error(Exception):
    """Base Error class for all error in actor."""
    pass

class UnknownMessageTypeError(Error):
    pass


class ActorLifeCycle(Enum):
    born = 1
    running = 2
    stopped = 3
    dead = 4


MSG_TYPE_KEY = '__msg_type'


def behavior(msg_type):
    def decorator(f):
        setattr(f, MSG_TYPE_KEY, msg_type)
        return f
    return decorator
