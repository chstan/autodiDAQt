from typing import List

import asyncio
import traceback
from dataclasses import dataclass, field
from multiprocessing import Process

from autodidaqt_common.remote.command import (
    HeartbeatCommand,
    RunSummary,
    ShutdownCommand,
    ShutdownEta,
)
from autodidaqt_common.remote.config import RemoteConfiguration
from autodidaqt_common.remote.middleware import (
    Middleware,
    TranslateCommandsMiddleware,
    WireMiddleware,
)
from autodidaqt_common.remote.socket import AsyncBufferedSocket
from loguru import logger
from pynng.nng import Pair1

from autodidaqt.core import CommandLineConfig

__all__ = ["PairScheduler"]


def print_header(header_text):
    header_text = " {} ".format(header_text.strip().upper())
    lpad = (80 - len(header_text)) // 2
    rpad = 80 - lpad - len(header_text)
    print(f"{lpad * '#'}{header_text}{rpad * '#'}\n")
    pass


@dataclass
class RunautodidaqtTask:
    config: RemoteConfiguration

    def __call__(self, app):
        cli_config = CommandLineConfig(headless=True, remote_configuration=self.config)
        app.configure_as_headless(cli_config)
        app.start()


def run(app, config):
    cli_config = CommandLineConfig(headless=True, remote_configuration=config)
    app.configure_as_headless(cli_config)
    app.start()


@dataclass
class PairScheduler:
    process: Process
    listen_configuration: RemoteConfiguration
    middleware: List[Middleware] = field(default_factory=list)

    socket: AsyncBufferedSocket = field(init=False)

    def start(self):
        run_future = asyncio.ensure_future(self.run())
        asyncio.get_event_loop().run_until_complete(run_future)

    async def shuts_down_normally(self):
        self.socket.send(ShutdownCommand())
        assert await self.wait_until_shutdown()

    @classmethod
    def run_with_standard_middleware(cls, process: Process, remote_config: RemoteConfiguration):
        scheduler = cls(
            listen_configuration=remote_config,
            process=process,
            middleware=[
                TranslateCommandsMiddleware(),
                WireMiddleware(),
            ],
        )
        scheduler.start()

    async def poll(self, condition, interval=0.05, max_wait=1.0):
        time_remaining = max_wait

        while True:
            if time_remaining < 0:
                return False

            if await condition():
                return True

            next_sleep_duration = min(interval, time_remaining)
            time_remaining -= interval
            await asyncio.sleep(next_sleep_duration)

    async def is_client_shutdown(self):
        return not self.process.is_alive()

    async def wait_for_message(self, timeout=1.0):
        return await asyncio.wait_for(self.socket.arecv(), timeout)

    async def run_finishes(self, timeout=5.0):
        while True:
            msg = await self.wait_for_message(timeout=timeout)
            print(type(msg))
            if isinstance(msg, RunSummary):
                return True

    async def wait_until_shutdown(self):
        try:
            msg = await self.wait_for_message(timeout=3.0)
            if not isinstance(msg, ShutdownEta):
                return False

        except:
            asyncio.TimeoutError
            return False

        return await self.poll(self.is_client_shutdown, max_wait=msg.eta)

    async def run(self):
        self.process.start()
        address = self.listen_configuration.ui_address
        with Pair1(listen=address) as socket:
            logger.info(f"Scheduler started listening at {address}")
            self.socket = AsyncBufferedSocket(socket, middleware=self.middleware)

            try:
                logger.info(f"Waiting for initial heartbeat.")
                beat = HeartbeatCommand()
                await self.socket.asend(beat)
                msg = await self.wait_for_message(timeout=5.0)
                assert isinstance(msg, HeartbeatCommand)
                assert msg.id == beat.id
                logger.info(f"Received matching heartbeat")

                logger.info(f"Running schedule")
                await self.run_schedule()
            except AssertionError:
                self.report_assertion_error()
            except:
                logger.error("Unhandled exception in schedule.")
                self.report_assertion_error()

        self.process.kill()
        self.process.join()
        self.summarize()

    def report_assertion_error(self):
        print("Running schedule failed with")
        tb_msg = traceback.format_exc()
        print(tb_msg)

    async def run_schedule(self):
        raise NotImplementedError

    def summarize(self):
        print_header("Finished without issues")
        pass
