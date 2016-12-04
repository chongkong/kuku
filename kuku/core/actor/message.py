from collections import namedtuple

__all__ = (
    'SystemMessage',
    'Envelope'
)


class SystemMessage(object):
    __slots__ = ('command', 'args', 'kwargs')

    def __init__(self, command, *args, **kwargs):
        self.command = command
        self.args = args
        self.kwargs = kwargs

    @staticmethod
    def kill():
        return SystemMessage('kill')


Envelope = namedtuple('Envelope', ['message', 'sender'])
