import asyncio
import datetime

import numpy as np

from autodidaqt import AutodiDAQt, Panel
from autodidaqt.actor import MessagingActor
from autodidaqt.data import ReactivePlot, reactive_frame
from autodidaqt.ui import vertical


class BasicPlot(Panel):
    SIZE = (800, 400)

    def layout(self):
        fig = self.register_figure("plot", toolbar=True)

        vertical(self.toolbars["plot"], self.canvases["plot"], widget=self)

        ax = fig.subplots()
        ReactivePlot.link_scatter(ax, self.app.actors["pub"].data_stream, x="time")
        now = datetime.datetime.now()
        ax.set_xlim([now - datetime.timedelta(0, 5), now + datetime.timedelta(0, 60)])
        fig.tight_layout()


class PublishData(MessagingActor):
    async def prepare(self):
        await super().prepare()
        self.data_pub, self.data_stream = reactive_frame()

    async def run_step(self):
        await asyncio.sleep(0.5)

        # publish a data point consisting of two temperatures
        self.data_pub.on_next(
            {
                "temperature_a": np.random.normal() + 3,
                "temperature_b": np.random.normal() + 6,
                "time": datetime.datetime.now(),
            }
        )


app = AutodiDAQt(
    __name__,
    {"Plot": BasicPlot},
    {"pub": PublishData},
)

if __name__ == "__main__":
    app.start()
