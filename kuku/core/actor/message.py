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


class Envelope(object):
    __slots__ = (
        'message',    # Contents of the envelope
        'sender',     # Actor_ref who's sending this envelope
        'req_token',  # Used in ask envelope (where to reply back)
        'resp_token'  # Used in reply envelope (correspond to previous request_token)
    )

    def __init__(self, message, sender, req_token=None, resp_token=None):
        self.message = message
        self.sender = sender
        self.req_token = req_token
        self.resp_token = resp_token
