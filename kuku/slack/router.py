import logging
from yarl import quoting

from kuku import actor
from kuku.actor import action
from kuku.slack import client


@action.child_mapping(action.MessageTypeTriggerMapping, dict)
class SlackInboundMessageMapping(action.TriggerMapping):
    inbound_msg_type_key = 'inbound_slack_msg_type'

    def __init__(self):
        self.handlers = {}

    def put(self, trigger_args, item):
        inbound_msg_type = trigger_args[0]
        self.handlers[inbound_msg_type] = item

    def resolve(self, message):
        assert self.inbound_msg_type_key in message
        return self.handlers.get(message[self.inbound_msg_type_key])

on_slack_inbound_msg_type = action.create_trigger_decorator(SlackInboundMessageMapping)


@action.child_mapping(SlackInboundMessageMapping, 'slash_command')
class SlackSlashCommandMapping(action.TriggerMapping):
    def __init__(self):
        self.handlers = {}

    def put(self, trigger_args, item):
        self.handlers[trigger_args] = item

    def resolve(self, message):
        command = quoting.unquote(message['command'])
        text = quoting.unquote(message['text'])
        args = (command, *text.split())
        for i in range(len(args), 0, -1):
            if args[:i] in self.handlers:
                return self.handlers[args[:i]]

on_slash_command = action.create_trigger_decorator(SlackSlashCommandMapping)


class SlackMessageRouter(actor.Actor):
    client_ref = None

    def before_start(self, token, port):
        self.client_ref = actor.spawn(client.SlackClientActor, self.ref, token, port)

    @on_slack_inbound_msg_type('rtm')
    def handle_rtm(self, message):
        print(f'rtm: {message}')

    @on_slack_inbound_msg_type('interactive')
    def handle_interactive(self, message):
        print(f'interactive: {message}')

    @on_slash_command('/kuku')
    def handle_kuku_command(self, message):
        self.client_ref.api_call('chat.postMessage',
                                 channel=message['channel_id'],
                                 text='I\'m kuku!')

    @on_slash_command('/kuku', 'hi')
    def handle_slash_command(self, message):
        self.client_ref.api_call('chat.postMessage',
                                 channel=message['channel_id'],
                                 text=f'Hello, <@{message["user_id"]}>')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    token = 'secret'
    router_ref = actor.spawn(SlackMessageRouter, token, 8002)
