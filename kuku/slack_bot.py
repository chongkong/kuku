from kuku import base_actor
from kuku.event_loop import *


class Trigger(object):
    def __init__(self, **triggers):
        self.keywords = triggers.get('keywords')

    def match(self, text):
        if self.keywords is not None:
            for keyword in self.keywords:
                if keyword in text:
                    return True
        return False


class SlackBotActor(base_actor):
    slack_identity = None
    message_options = None
    allowed_channels = []
    allow_direct_message = True
    trigger = Trigger(keywords=[])

    _behaviors = None

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.slack_inbox = new_queue()
        self.router_ref = k['router_ref']
        self.user = k['user']
        self.channel = k['channel']

        self.future = run_coroutine(self.find_behavior(k['message']['slack_message']['text']))
        self.future.add_done_callback(self.bye)

    @classmethod
    def behaviors(cls):
        if cls._behaviors is None:
            cls._behaviors = [
                (method, getattr(method, 'trigger'))
                for name, method in cls.__dict__.items()
                if hasattr(method, 'trigger')
            ]
        return cls._behaviors

    def find_behavior(self, text):
        for behavior, trigger in self.behaviors():
            if trigger.match(text):
                return behavior(self, text)
        return self.default_behavior()

    async def default_behavior(self):
        self.help()
        await self.find_behavior(await self.hear())

    def say(self, text, attachments=None):
        message = {
            'type': 'bot_message',
            'channel': self.channel['id'],
            'text': text
        }
        if self.slack_identity:
            message.update(self.slack_identity)
        if self.message_options:
            message.update(self.message_options)
        if attachments is not None:
            message.update({'attachments': attachments})
        self.router_ref.tell(message)

    async def hear(self):
        return await self.slack_inbox.get()

    def bye(self, *args):
        print('Sending bye...')
        self.router_ref.tell({
            'type': 'bye',
            'bot_ref': self.actor_ref
        })

    def help(self):
        raise NotImplementedError

    def on_receive(self, message):
        if message.get('type') == 'slack_message':
            self.slack_inbox.put(message['slack_message']['text'])
        elif message.get('type') == 'terminate':
            self.future.cancel()
            self.stop()


def when(keywords=None):
    def deco(target):
        setattr(target, 'trigger', Trigger(keywords=keywords))
        return target

    return deco
