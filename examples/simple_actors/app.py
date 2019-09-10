"""
The absolute, bare minimum. Open an application with no panels.
"""
from daquiri import Daquiri, Actor
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

app = Daquiri(__name__, {}, {
    'speaks': Speaker,
    'listens': Listener,
})
app.start()
