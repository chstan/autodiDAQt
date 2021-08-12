from pathlib import Path

import pytest

from autodidaqt.version import VERSION
from autodidaqt.mock import MockScalarDetector
from autodidaqt.state import AppState, AutodiDAQtStateAtRest, InstrumentState, SerializationSchema
from tests.conftest import Mockautodidaqt

from .utils import CoordinateOffsets, LogicalMockMotionController


@pytest.mark.asyncio
async def test_basic_state_collection(app: Mockautodidaqt):
    app.init_with(managed_instruments={"mc": MockScalarDetector})

    # test that state defaults are reasonably populated
    state = app.collect_state()
    root = Path(__file__).parent.parent
    assert state == AutodiDAQtStateAtRest(
        schema=SerializationSchema(autodidaqt_version=VERSION, user_version="0.0.0", app_root=root),
        autodidaqt_state=AppState(),
        panels={},
        actors={},
        managed_instruments={
            "mc": InstrumentState(axes={"device": None}, properties={}, panel_state=None)
        },
    )


@pytest.mark.asyncio
async def test_logical_axis_state(app: Mockautodidaqt):
    """Tests that logical axis state behaves appropriately.

    Note that state is only deepcopied at ``core.autodidaqt.collect_state`` at the moment,
    so if you want to unit test something coarser you will need to copy it yourself.
    """
    app.init_with(managed_instruments={"mc": LogicalMockMotionController})
    x_y_z, stages = app.instruments.mc.offset_x_y_z, app.instruments.mc.stages

    x_y_z.internal_state.x_off = 4.1
    state = app.collect_state()
    assert state.managed_instruments["mc"].axes["offset_x_y_z"].internal_state == CoordinateOffsets(
        x_off=4.1, y_off=0, z_off=0
    )

    x_y_z.internal_state.x_off = 0
    app.receive_state(state)
    assert state.managed_instruments["mc"].axes["offset_x_y_z"].internal_state == CoordinateOffsets(
        x_off=4.1, y_off=0, z_off=0
    )
