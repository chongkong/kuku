import logging

from kuku import actor

logging.basicConfig(level=logging.DEBUG)


class LoggingActor(actor.Actor):
    @actor.rpc
    def log(self, message):
        print(message)


class EchoActor(actor.Actor):
    @actor.rpc(reply=True)
    async def echo(self, message):
        self.sender.tell(message)


class TestActor(actor.Actor):
    @actor.on_message_type(str)
    async def test(self, message):
        if message == 'start':
            log = actor.spawn(LoggingActor)
            log.log('hello')

            echo = actor.spawn(EchoActor)
            resp = await echo.echo('yollo')
            log.log(resp)


if __name__ == '__main__':
    test = actor.spawn(TestActor)
    test.tell('start')
