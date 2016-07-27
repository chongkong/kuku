import functools
import logging

from kuku.actor import *
from kuku.event_loop import *
from kuku.router import *
from kuku.slack_bot import *
from kuku.slack_client import *


logging.basicConfig(level=logging.DEBUG)
logging.getLogger('pykka').setLevel(logging.INFO)


def configure(bot, **k):
    bot.start = functools.partial(bot.start, **k)
    return bot


def run_kuku(token, bots, bot_username='kuku'):
    print('Starting KUKU with token={}, bots={}'.format(
        token, ', '.join([cls.__name__ for cls in bots])))

    client_ref = SlackClientActor.start(
        token=token,
        router=configure(SlackMessageRouterActor, bots=bots),
        bot_username=bot_username
    )

    try:
        while client_ref.is_alive():
            continue
    finally:
        print('Terminating KUKU...')
