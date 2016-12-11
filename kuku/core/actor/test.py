from kuku.core import base_actor, spawn
from kuku.core.actor.base import behavior


class LoggingActor(base_actor):
    @behavior(str)
    def handle_message(self, message):
        print(message)


class EchoActor(base_actor):
    @behavior(str)
    async def handle_message(self, message):
        self.sender.reply(message)


class TestActor(base_actor):
    @behavior(str)
    async def test(self, message):
        if message == 'start':
            log = spawn(LoggingActor)
            log.tell('hello')

            echo = spawn(EchoActor)
            resp = await echo.ask('yollo')
            log.tell(resp)


if __name__ == '__main__':
    test = spawn(TestActor)
    test.tell('start')
