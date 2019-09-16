import asyncio
from random import random

from instruments.newport.newportesp301 import NewportESP301
from pymeasure.instruments.signalrecovery import dsp7265
from pymeasure.instruments.lakeshore import LakeShore331

from daquiri import Daquiri, Actor

from daquiri.instrument.spec import ManagedInstrument, Generate
from daquiri.instrument.property import (
    AxisListSpecification, AxisSpecification, DetectorSpecification,
    PolledWrite, PolledRead
)


class ManagedDSP7265(ManagedInstrument):
    driver_cls = dsp7265.DSP7265
    test_cls = Generate()

    phase = AxisSpecification(float, where=['phase'])
    # you can also omit where if it is the same as the specified name
    x = AxisSpecification(float)
    y = AxisSpecification(float)
    mag = AxisSpecification(float)


class ManagedNewportESP301(ManagedInstrument):
    driver_cls = NewportESP301
    test_cls = Generate({'stages': {'length': 3}})

    stages = AxisListSpecification(
        lambda index: AxisSpecification(
            float, where=['axis', index],
            read=PolledRead(read='position', poll='is_motion_finished'),
            write=PolledWrite(write='move', poll='is_motion_finished')),
        where='axis',
    )


class ManagedTemperatureController(ManagedInstrument):
    driver_cls = LakeShore331
    test_cls = Generate()

    sensor_a = DetectorSpecification(float, where=[], read='temperature_A')
    sensor_b = DetectorSpecification(float, where=[], read='temperature_B')


class RandomlyMove(Actor):
    async def run(self):
        while True:
            # simultaneously move the three stages to random positions every three seconds
            print('RandomlyMove: Moving...')
            await asyncio.gather(
                asyncio.sleep(0.5), # sleep here means we discount the motion time
                *[self.app.managed_instruments['motion_controller']
                      .stages[i].write(100 * random())
                  for i in range(3)]
            )
            await asyncio.gather(*[self.app.managed_instruments['motion_controller'].stages[i].read()
                                   for i in range(3)])

            # read the temperature
            print('RandomlyMove: Reading temp...')
            temp = await self.app.managed_instruments['temp_controller']\
                .sensor_a.read()
            print(temp)


app = Daquiri(__name__, {}, {
    'randomly_move': RandomlyMove,
}, managed_instruments={
    'motion_controller': ManagedNewportESP301,
    'temp_controller': ManagedTemperatureController,
})

if __name__ == '__main__':
    app.start()
