__all__ = [
    'Error',
    'BadEnvelopeError',
    'BadMessageError',
    'OutOfContextError',
    'UnknownMessageTypeError',
    'MultipleRootMappingsError'
]


class Error(Exception):
    """Base Error class for all error in actor."""
    description: str = None

    def __init__(self, description=None):
        if description is not None:
            self.description = description

    def __repr__(self):
        return '{}({})'.format(type(self), self.description)


class BadEnvelopeError(Error):
    pass


class BadMessageError(Error):
    pass


class OutOfContextError(Error):
    description = 'Actor action called out of ActorContext'


class UnknownMessageTypeError(Error):
    pass


class MultipleRootMappingsError(Error):
    pass


class MessageResolveError(Error):
    description = 'Failed to resolve action from given message'
