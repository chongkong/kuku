__all__ = [
    'SystemMessage',
    'Envelope'
]


class SystemMessage(object):
    def __init__(self, command, *args, **kwargs):
        self.command = command
        self.args = args
        self.kwargs = kwargs

    @staticmethod
    def kill():
        return SystemMessage('kill')


class Envelope(object):
    def __init__(self, sender_ref, message):
        self.sender_ref = sender_ref
        self.message = message
