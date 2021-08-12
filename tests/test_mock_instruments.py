import asyncio

import pytest

from autodidaqt.mock import MockMotionController, MockScalarDetector
from tests.conftest import Mockautodidaqt


@pytest.mark.asyncio
async def test_mock_motion_controller(app: Mockautodidaqt):
    app.init_with(managed_instruments={"mc": MockMotionController})

    # test writing
    await app.instruments.mc.stages[0].write(5.6)
    read_value = await app.instruments.mc.stages[0].read()

    assert read_value == 5.6

    # test default value
    read_second = await app.instruments.mc.stages[1].read()
    assert read_second == 0


@pytest.mark.asyncio
async def test_mock_detector(app: Mockautodidaqt):
    app.init_with(managed_instruments={"det": MockScalarDetector})
    det = app.instruments.det

    x, y = await asyncio.gather(det.device.read(), det.device.read())
    assert x != y
    assert isinstance(x, float) and isinstance(x, float)
