import aiohttp
import asyncio
import json
import yarl

from aiohttp import web
from yarl import quoting

from kuku import actor


class SlackClientActor(actor.Actor):
    token = None
    session = None
    server = None
    subscriber = None

    def before_start(self, subscriber, token, port):
        self.token = token
        self.session = aiohttp.ClientSession(loop=self.context.loop)
        self.subscriber = subscriber
        self.context.run(self.listen_real_time_message())
        self.context.run(self.run_server(port))

    def before_die(self):
        if self.session and not self.session.closed:
            self.session.close()

    async def _api_call(self, method, **params):
        params = {'token': self.token, **params}
        async with self.session.post('https://slack.com/api/{}'.format(method), params=params) as resp:
            if resp.status == 200:
                return await resp.json()

    @actor.rpc(reply=True)
    async def api_call(self, method, **params):
        self.sender.tell(await self._api_call(method, **params))

    async def run_server(self, port):
        self.logger.debug('running server')
        app = web.Application(loop=self.context.loop)
        app.router.add_post('/interactive', self.listen_interactive_message)
        app.router.add_post('/slash', self.listen_slash_command)
        await app.startup()
        await self.context.loop.create_server(app.make_handler(), '127.0.0.1', port)

    async def listen_real_time_message(self):
        resp = await self._api_call('rtm.start')
        if resp is None:
            self.logger.error('rtm failed')
            return
        elif not resp['ok']:
            self.logger.error(f'Error: {resp}')
            return

        url = yarl.URL(resp['url'], encoded=True)
        async with self.session.ws_connect(url) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if 'type' not in data:
                        continue
                    else:
                        self.subscriber.tell(data)

    async def listen_interactive_message(self, request):
        asyncio.Task.current_task().actor_ctx = self.context
        try:
            text = await request.text()
            body = dict(kv.split('=') for kv in quoting.unquote(text).split('&'))
            payload = json.loads(body['payload'])
            resp = await self.subscriber.ask(payload, timeout=1)
            return web.Response(body=json.dumps(resp))
        except TimeoutError:
            return web.Response()

    async def listen_slash_command(self, request):
        asyncio.Task.current_task().actor_ctx = self.context
        self.logger.debug('received slash command')
        text = await request.text()
        body = dict(kv.split('=') for kv in text.split('&'))
        self.subscriber.tell(body)
        return web.Response()
