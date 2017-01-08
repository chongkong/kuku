__all__ = (
    'SystemMessage',
    'ErrorForward',
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


class ErrorForward(object):
    __slots__ = ('error', )

    def __init__(self, error):
        self.error = error


class RPCMessage(object):
    __slots__ = ['action_name', 'args', 'kwargs']

    def __init__(self, action_name, args, kwargs):
        self.action_name = action_name
        self.args = args
        self.kwargs = kwargs


class Envelope(object):
    __slots__ = (
        'message',    # Contents of the envelope
        'rpc',        # RPC definition
        'internal',   # For internal usage
        'sender',     # Actor_ref who's sending this envelope
        'req_token',  # Used in ask envelope (where to reply back)
        'resp_token'  # Used in reply envelope (correspond to previous request_token)
    )

    def __init__(self, message, sender, req_token=None, resp_token=None):
        self.message = message
        self.sender = sender
        self.req_token = req_token
        self.resp_token = resp_token
