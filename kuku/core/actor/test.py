from kuku.core import base_actor, behavior, spawn


class LoggingActor(base_actor):
    @behavior(str)
    def handle_message(self, message):
        print(message)


class EchoActor(base_actor):
    @behavior(str)
    async def handle_message(self, message):
        self.sender.tell(message)


if __name__ == '__main__':
    log = spawn(LoggingActor)
    log.tell('hello')
    log.handle_message('world')

    echo = spawn(EchoActor)
    echo.tell('yollo', sender=log)

    from asyncio import ensure_future
    ensure_future(echo.ask('foo')).add_done_callback(lambda fut: print(fut.result()))
