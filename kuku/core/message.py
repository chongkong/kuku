from collections import namedtuple

__all__ = [
    'SystemMessage',
    'Envelope'
]


class SystemMessage(namedtuple('SystemMessage', ['command', 'args', 'kwargs'])):
    def __new__(cls, command, *args, **kwargs):
        return super().__new__(cls, command, args, kwargs)

    @staticmethod
    def kill():
        return SystemMessage('kill')


Envelope = namedtuple('Envelope', ['message', 'sender'])
