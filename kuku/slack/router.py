import logging

from kuku import actor
from kuku.actor import action
from kuku.slack import client



# @action.child_mapping(action.MessageTypeTriggerMapping, dict)
# class SlackMessageMapping(action.TriggerMapping):
#     def __init__(self):


class SlackMessageRouter(actor.Actor):
    client_ref = None

    def before_start(self, token, port):
        self.client_ref = actor.spawn(client.SlackClientActor, self.ref, token, port)

    @action.on_message_type(dict)
    def handle_message(self, message):
        print(message)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    token = 'secret'
    router_ref = actor.spawn(SlackMessageRouter, token, 8002)
