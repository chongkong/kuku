from kuku.actor import base_actor


class BotRegistry(object):
    def __init__(self):
        self._bot_ref_info = {}
        self._bot_refs = {}

    def add(self, user, channel, bot_ref):
        self._bot_refs[(user, channel)] = bot_ref
        self._bot_ref_info[bot_ref] = (user, channel)

    def remove(self, user=None, channel=None, bot_ref=None):
        if bot_ref is not None:
            user, channel = self._bot_ref_info.pop(bot_ref)
            self._bot_refs.pop((user, channel))
        elif user is not None and channel is not None:
            bot_ref = self._bot_refs.pop((user, channel))
            self._bot_ref_info.pop(bot_ref)

    def __contains__(self, item):
        if isinstance(item, tuple):
            return item in self._bot_refs
        else:
            return item in self._bot_ref_info

    def get(self, user=None, channel=None, bot_ref=None):
        if bot_ref is not None:
            return self._bot_ref_info.get(bot_ref)
        elif user is not None and channel is not None:
            return self._bot_refs.get((user, channel))


class SlackMessageRouterActor(base_actor):
    initiate_keywords = ['!']
    terminate_keywords = ['!!']

    def is_initiate_message(self, text):
        bot_name = '<@{}>'.format(self.bot_id)
        return any(
            text.startswith(keyword)
            for keyword in self.initiate_keywords + [bot_name]
        )

    def is_terminate_message(self, text):
        return text in self.terminate_keywords

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.registry = BotRegistry()
        self.client_ref = k['client_ref']
        self.channels = k['channels']
        self.bot_id = k['bot_id']
        self.channel_id = {
            channel['name']: channel_id
            for channel_id, channel in self.channels.items()
        }
        self.bots = k['bots']

    def find_route(self, channel, text):
        for bot in self.bots:
            if channel not in self.channels:
                if bot.allow_direct_message and bot.trigger.match(text):
                    return bot
            else:
                channels = [
                    self.channel_id[name]
                    for name in bot.allowed_channels
                    if name in self.channel_id
                ]
                if channel in channels and bot.trigger.match(text):
                    return bot

        return None

    def on_receive(self, message):
        if message.get('type') == 'slack_message':
            self.handle_slack_message(message)
        if message.get('type') == 'bot_message':
            self.handle_bot_message(message)
        if message.get('type') == 'bye':
            self.registry.remove(bot_ref=message['bot_ref'])

    def handle_slack_message(self, message):
        slack_message = message['slack_message']
        user = slack_message['user']
        channel = slack_message['channel']
        text = slack_message['text']

        if (user, channel) not in self.registry:
            if self.is_initiate_message(text):
                bot = self.find_route(channel, text)
                if bot is not None:
                    self.registry.add(user, channel, bot.start(
                        router_ref=self.actor_ref,
                        user=message.pop('user'),
                        channel=message.pop('channel'),
                        message=message
                    ))
        else:
            bot_ref = self.registry.get(user=user, channel=channel)
            if self.is_terminate_message(text):
                bot_ref.tell({'type': 'terminate'})
            else:
                bot_ref.tell(message)

    def handle_bot_message(self, message):
        self.client_ref.tell(message)
