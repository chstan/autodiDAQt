"""
The absolute, bare minimum. Open an application with no panels.
"""
from zhivago import Zhivago, Actor
from asyncio import sleep
from loguru import logger

class Speaker(Actor):
    async def run(self):
        logger.info('Starting speaker.')
        while True:
            await sleep(0.5)
            await self.app.actors['listens'].messages.put('Hello')


class Listener(Actor):
    async def run(self):
        logger.info('Starting listener.')
        while True:
            message = await self.messages.get()
            logger.info(message)

app = Zhivago(__name__, {}, {
    'speaks': Speaker,
    'listens': Listener,
})
app.start()
