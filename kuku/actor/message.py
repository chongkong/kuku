import collections
import enum

__all__ = [
    'RpcMessage',
    'MsgType',
    'Envelope'
]

RpcMessage = collections.namedtuple('RpcMessage', [
    'action_name',
    'args',
    'kwargs'
])


class RpcMessage(object):
    __slots__ = ['action_name', 'args', 'kwargs']

    def __init__(self, action_name, args, kwargs):
        self.action_name = action_name
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        params = (list(repr(arg) for arg in self.args) +
                  list(f'{k}={repr(v)}' for k, v in self.kwargs.items()))
        return f'{self.action_name}({", ".join(params)})'


class MsgType(enum.Enum):
    NORMAL = 0
    INTERNAL = 1
    RPC = 2
    ERROR = 3


class Envelope(object):
    __slots__ = ['type', 'message', 'sender', 'req_token', 'resp_token']

    def __init__(self, type, message, sender, req_token=None, resp_token=None):
        self.type = type
        self.message = message
        self.sender = sender
        self.req_token = req_token
        self.resp_token = resp_token

    @staticmethod
    def normal(msg, sender, req_token=None, resp_token=None):
        return Envelope(MsgType.NORMAL, msg, sender,
                        req_token=req_token, resp_token=resp_token)

    @staticmethod
    def internal(msg, sender):
        return Envelope(MsgType.INTERNAL, msg, sender)

    @staticmethod
    def rpc(msg, sender, req_token=None):
        return Envelope(MsgType.RPC, msg, sender, req_token=req_token)

    @staticmethod
    def error(msg, sender, resp_token):
        return Envelope(MsgType.ERROR, msg, sender, resp_token=resp_token)
