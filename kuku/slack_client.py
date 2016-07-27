import threading
import time

from slackclient import *
from kuku.router import *


class SlackClientActor(base_actor):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.client = SlackClient(k['token'])
        self.router = k['router']
        self.bot_username = k['bot_username']
        self.router_ref = None
        self.channels = {}
        self.users = {}
        self.last_updated = None
        self.slack_thread = threading.Thread(target=self._slack_loop)

    def on_start(self):
        self.update_slack_info()
        bot = [
            user for user in self.users.values()
            if user['name'] == self.bot_username and user['is_bot']
        ]
        assert len(bot) == 1, 'No bot matching username {} found'.format(self.bot_username)
        self.router_ref = self.router.start(
            client_ref=self.actor_ref,
            channels=self.channels,
            bot_id=bot[0]['id']
        )
        self.client.rtm_connect()
        self.slack_thread.start()

    def update_slack_info(self):
        resp = self.client.api_call('channels.list')
        if resp and resp.get('ok'):
            channels = resp['channels']
            self.channels = {ch['id']: ch for ch in channels}

        resp = self.client.api_call('users.list')
        if resp and resp.get('ok'):
            users = resp['members']
            self.users = {user['id']: user for user in users}

        self.last_updated = time.time()

    def _slack_loop(self):
        print('Start listening Slack real time messages')
        while not self.actor_stopped.is_set():
            if time.time() > self.last_updated + 86400:
                print('Update Slack information')
                self.actor_ref.tell({
                    'type': 'update_slack_info'
                })
            for event in self.client.rtm_read():
                print('Slack event received:', event)
                self.actor_ref.tell({
                    'type': 'slack_event',
                    'event': event
                })

    def on_receive(self, message):
        if message.get('type') == 'slack_event':
            self.handle_slack_event(message)
        elif message.get('type') == 'bot_message':
            self.handle_bot_message(message)
        elif message.get('type') == 'update_slack_info':
            self.update_slack_info()

    def handle_slack_event(self, message):
        if self.router_ref is None:
            return

        event = message['event']
        if event.get('type') == 'message' and event.get('subtype') != 'bot_message':
            message_event = message['event']
            if 'user' not in message_event or 'channel' not in message_event:
                return
            if message_event['user'] not in self.users:
                return
            self.router_ref.tell({
                'type': 'slack_message',
                'slack_message': message_event,
                'channel': self.channels.get(message_event['channel'], {
                    'id': message_event['channel'],
                    'name': None,
                    'is_channel': False,
                    'members': [message_event['user']]
                }),
                'user': self.users[message_event['user']],
            })

    def handle_bot_message(self, message):
        self.client.api_call('chat.postMessage', **message)
