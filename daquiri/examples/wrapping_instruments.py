import asyncio
from random import random

from instruments.newport.newportesp301 import NewportESP301
from instruments.lakeshore.lakeshore340 import Lakeshore340

from daquiri import Daquiri, Actor

from daquiri.instrument.spec import (
    ManagedInstrument,
    AxisListSpecification, AxisSpecification,
    Properties, Generate,
    DetectorSpecification,
    PolledWrite, PolledRead,
)

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

    properties = Properties()


class ManagedTemperatureController(ManagedInstrument):
    driver_cls = Lakeshore340
    test_cls = Generate()

    sensor_a = DetectorSpecification(float, where=['sensor', 0], read='temperature')
    sensor_b = DetectorSpecification(float, where=['sensor', 1], read='temperature')

    properties = Properties()


class RandomlyMove(Actor):
    async def run(self):
        while True:
            # simultaneously move the three stages to random positions every three seconds
            print('RandomlyMove: Moving...')
            await asyncio.gather(
                asyncio.sleep(3), # sleep here means we discount the motion time
                *[self.app.managed_instruments['motion_controller']
                      .stages[i].write(100 * random())
                  for i in range(3)]
            )

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
