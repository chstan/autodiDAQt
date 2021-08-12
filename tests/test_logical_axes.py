import asyncio

import pytest

from .utils import LogicalMockMotionController


@pytest.mark.asyncio
async def test_logical_axis(app):
    app.init_with(managed_instruments={"mc": LogicalMockMotionController})

    # check that logical writes actually proxy
    await app.instruments.mc.offset_x_y_z.x.write(5)
    s0 = await app.instruments.mc.stages[0].read()
    x = await app.instruments.mc.offset_x_y_z.read()
    assert s0 == 5 and x == [5, 0, 0]

    # check that we can manipulate the internal state and perform writes
    app.instruments.mc.offset_x_y_z.internal_state.x_off = 3
    await app.instruments.mc.offset_x_y_z.x.write(5)
    s0 = await app.instruments.mc.stages[0].read()
    xyz = await app.instruments.mc.offset_x_y_z.read()
    assert s0 == 8 and xyz == [5, 0, 0]

    # check full axis writes work
    await app.instruments.mc.offset_x_y_z.write([0, 1, 2])
    xyz = await app.instruments.mc.offset_x_y_z.read()
    s012 = await asyncio.gather(*[app.instruments.mc.stages[i].read() for i in range(3)])
    assert xyz == [0, 1, 2], s012 == [3, 1, 2]

    # Test a coordinate transform with linked axes
    await app.instruments.mc.x_y_z.write((1, -1, 0))
    xyz = await app.instruments.mc.x_y_z.read()
    s012 = await asyncio.gather(*[app.instruments.mc.stages[i].read() for i in range(3)])
    assert xyz == [1, -1, 0], s012 == [2, 0, 0]
