from typing import List

import asyncio
from asyncio.queues import QueueEmpty

from autodidaqt_common.remote.command import Log, RequestShutdown
from autodidaqt_common.remote.config import RemoteConfiguration
from autodidaqt_common.remote.middleware import Middleware
from autodidaqt_common.remote.socket import AsyncUnbufferedSocket
from loguru import logger
from pynng import Pair1, TryAgain

from autodidaqt.actor import Actor

__all__ = [
    "RemoteLink",
]


class RemoteLink(Actor):
    """
    Serves as a communications endpoint to the remote UI
    so that an experiment can be controlled. Pretty barebones
    because it is basically just a router which forwards
    messages to the appropriate party.
    """

    def __init__(self, app, config: RemoteConfiguration, middleware: List[Middleware]):
        super().__init__(app)
        self.config = config
        self.middleware = middleware
        self.middleware_socket = None

    def forward_log(self, msg):
        self.messages.put_nowait(Log(msg=msg))

    async def run(self):
        logger.info(f"Remote is preparing to dial on {self.config.ui_address}")
        with Pair1(dial=self.config.ui_address) as raw_socket:
            self.middleware_socket = AsyncUnbufferedSocket(raw_socket, middleware=self.middleware)
            logger.remove()  # remote print logging
            logger.add(self.forward_log)
            logger.info(f"Remote has opened socket on {self.config.ui_address}")
            logger.info(f"Installed log forwarding")

            while True:
                # try to forward one message to the remote ui if available
                try:
                    message = self.messages.get_nowait()
                    if isinstance(message, RequestShutdown):
                        logger.error(
                            "The remote should not be shut down. This should happen implicitly through task cancellation. Ignoring request."
                        )
                        continue
                    await self.middleware_socket.asend(message)
                except QueueEmpty:
                    pass

                # then we try to receive a message and dispatch it on the
                # local message passing system. Typically this means
                # forwarding messages to the App or to the Experiment
                # instance.
                try:
                    message = self.middleware_socket.recv(block=False)
                    self.app.messages.put_nowait(message)
                except TryAgain:
                    pass

                await asyncio.sleep(0.01)
