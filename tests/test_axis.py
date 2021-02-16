from daquiri.instrument.spec import AxisDescriptor, MockDriver
from daquiri.instrument.axis import ManualAxis
import pytest

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
    axis = desc.realize("b", MockDriver(), None)

    v = await axis.read()
    assert v == 8
    await axis.write(100)
    v = await axis.read()
    assert v == 8
