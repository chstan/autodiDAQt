"""
The absolute, bare minimum. Open an application with no panels.
"""
from asyncio import sleep

from loguru import logger

from autodidaqt import AutodiDAQt
from autodidaqt.actor import MessagingActor


class Speaker(MessagingActor):
    async def prepare(self):
        await super().prepare()
        logger.info("Starting speaker.")

    async def run_step(self):
        await sleep(0.5)
        await self.app.actors["listens"].messages.put("Hello")


class Listener(MessagingActor):
    async def prepare(self):
        await super().prepare()
        logger.info("Starting listener.")

    async def handle_user_message(self, message):
        logger.info(message)


app = AutodiDAQt(
    __name__,
    {},
    {"speaks": Speaker, "listens": Listener},
)

if __name__ == "__main__":
    app.start()
