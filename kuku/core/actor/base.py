from enum import Enum
import logging

__all__ = (
    'logger',
    'Error',
    'UnknownMessageTypeError',
    'ActorLifeCycle',
)


logger = logging.getLogger('kuku.core.actor')


class Error(Exception):
    """Base Error class for all error in actor."""
    pass


class UnknownMessageTypeError(Error):
    pass


class MultipleRootTriggersError(Error):
    pass


class ActorLifeCycle(Enum):
    born = 1
    running = 2
    stopped = 3
    dead = 4
