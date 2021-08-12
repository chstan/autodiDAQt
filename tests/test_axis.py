import asyncio
import time
from dataclasses import dataclass, field

import pytest

from autodidaqt.instrument import AxisSpecification, ManagedInstrument
from autodidaqt.instrument.axis import Axis, PolledRead, PolledWrite, ProxiedAxis
from autodidaqt.instrument.spec import AxisDescriptor, AxisListSpecification, MockDriver

from .conftest import Mockautodidaqt


class A:
    _value: int = 0

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = value


@pytest.mark.asyncio
async def test_manual_axis():
    a = A()

    async def read(driver):
        return driver.get_value()

    async def write(driver, v):
        driver.set_value(v)

    desc = AxisDescriptor(read, write)
    desc.schema = int
    axis = desc.realize("b", a, a)

    v = await axis.read()
    assert v == 0

    await axis.write(5)
    assert a.get_value() == 5


@pytest.mark.asyncio
async def test_manual_axis_mocked():
    async def mock_read(_):
        return 8

    async def mock_write(_, value):
        return

    desc = AxisDescriptor(None, None, mock_read, mock_write)
    desc.schema = float
    axis = desc.realize("b", MockDriver(), None)

    v = await axis.read()
    assert v == 8
    await axis.write(100)
    v = await axis.read()
    assert v == 8


@dataclass
class PolledFloat:
    value: float = 0.0
    last_moved: float = field(default_factory=time.time)
    sleep_for: float = 0.5

    def __post_init__(self):
        # make sure we are writable initially
        self.last_moved -= 2 * (self.sleep_for)

    @property
    def next_readable_at(self) -> float:
        return self.last_moved + self.sleep_for

    def is_readable(self) -> bool:
        return self.next_readable_at < time.time()

    def write(self, value) -> float:
        if not self.is_readable():
            raise ValueError("Axis is not finished moving")

        self.last_moved = time.time()
        self.value = value

    def read(self) -> float:
        if not self.is_readable():
            raise ValueError("Axis is not finished moving")

        return self.value


class PseudoDriver:
    x = PolledFloat(1)
    simple_value = 2
    array_of_simple_values = [
        "a",
        "b",
    ]
    xyz = [1, 2, 3]


class PseudoInstrument(ManagedInstrument):
    driver_cls = PseudoDriver

    x = AxisSpecification(
        float,
        where=["x"],
        read=PolledRead("read", "is_readable"),
        write=PolledWrite("write", "is_readable"),
    )

    xyz = AxisListSpecification(
        float,
        where=lambda i: ["xyz", i],
    )

    simple_value = AxisSpecification(float, where=["simple_value"])
    arr_a = AxisSpecification(str, where=["array_of_simple_values", 0])
    arr_b = AxisSpecification(str, where=["array_of_simple_values", 1])


@pytest.mark.asyncio
async def test_proxied_axis_simple_values(app: Mockautodidaqt):
    app.config._cached_settings["instruments"]["simulate_instruments"] = False
    app.init_with(managed_instruments=dict(p=PseudoInstrument))

    axis: Axis
    # test simple scalars
    axis = app.instruments["p"].simple_value
    assert await axis.read() == 2
    await axis.write(8) == 8
    await axis.read() == 8

    # test history
    await axis.write(7)
    await axis.write(6)
    # this includes also values emitted on explicit reads
    assert axis.collected_ys == [2, 8, 8, 7, 6]
    axis.reset_history()
    assert axis.collected_ys == []

    # test str types, indices in paths, and array handling
    axis = app.instruments["p"].arr_a
    assert await axis.read() == "a"
    await axis.write("hello") == "hello"
    await axis.read() == "hello"

    axis = app.instruments["p"].arr_b
    assert await axis.read() == "b"
    await axis.write("goodbye") == "goodbye"
    await axis.read() == "goodbye"


@pytest.mark.asyncio
async def test_proxied_axis_list(app: Mockautodidaqt):
    app.config._cached_settings["instruments"]["simulate_instruments"] = False
    app.init_with(managed_instruments=dict(p=PseudoInstrument))

    axis: Axis
    axis = app.instruments["p"].xyz[0]
    await axis.write(5)

    assert app.instruments["p"].driver.xyz == [5, 2, 3]

    axis = app.instruments["p"].xyz[2]
    assert await axis.read() == 3


@pytest.mark.asyncio
async def test_proxied_axis_polling(app: Mockautodidaqt, mocker):
    # TODO: fix this this is gross.
    app.config._cached_settings["instruments"]["simulate_instruments"] = False
    app.init_with(managed_instruments=dict(p=PseudoInstrument))
    ins = app.instruments["p"]

    x_axis = ins.x
    assert ins.driver.__class__ == PseudoDriver
    assert x_axis.__class__ == ProxiedAxis
    assert x_axis._bound_poll_write == ins.driver.x.is_readable

    # check that we can read
    assert await x_axis.read() == 1

    # check that we can read after a write if we wait sufficiently long
    poll_spy = mocker.spy(x_axis, "_bound_poll_write")
    start = time.time()

    assert await x_axis.write(5) == 5
    assert ins.driver.x.last_moved is not None

    # that write should have been slow
    elapsed = time.time() - start
    assert elapsed > ins.driver.x.sleep_for

    # but that read shouldn't have been
    assert await x_axis.read() == 5

    elapsed2 = time.time() - start
    assert elapsed + 0.5 > elapsed2

    # the exact call count may vary a little but it should be
    # at least five calls based on the standard backoff settings
    assert poll_spy.call_count > 5

    # check that if we fire a write just before a read
    # then the read is coordinated so that the write will flush
    # before the read can go through
    async def race_write():
        await x_axis.write(4)

    async def race_read():
        await asyncio.sleep(0.05)
        start = time.time()
        assert await x_axis.read() == 4
        assert time.time() - start > 0.2

    await asyncio.gather(race_read(), race_write())

    # check that a double write will cause an exception to be raised
    async def fast_write():
        await x_axis.write(7)

    async def slow_write():
        await asyncio.sleep(0.05)

        with pytest.raises(ValueError) as exc:
            await x_axis.write(6)

        assert "Already moving" in str(exc.value)

    await asyncio.gather(fast_write(), slow_write())
