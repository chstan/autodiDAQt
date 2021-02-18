import asyncio
import datetime
import enum
import warnings
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from daquiri.schema import default_value_for_schema
from daquiri.state import LogicalAxisState
from rx.subject import Subject

__all__ = (
    "Axis",
    "TestAxis",
    "ProxiedAxis",
    "LogicalAxis",
    "ManualAxis",
    "TestManualAxis",
    "PolledRead",
    "PolledWrite",
)


@dataclass
class BackoffConfig:
    initial_time: float = 0.03
    maximum_time: float = 0.2
    backoff_ratio: float = 1.5

    def next_duration(self, wait_time: Optional[float] = None) -> float:
        if wait_time is None:
            return self.initial_time

        return min(self.maximum_time, self.backoff_ratio * wait_time)


@dataclass
class PolledWrite:
    write: Optional[str] = None
    poll: Optional[str] = None


@dataclass
class PolledRead:
    read: str
    poll: Optional[str] = None


class AxisStatus(int, enum.Enum):
    Idle = 0
    Moving = 1


class Axis:
    """
    Representation of an axis which can read values or write values.

    Axes have fixed schema: in this sense, you can always expect to receive the same shape data
    back from the axis. In most cases, axes record single points, but you can produce any Python
    primitive, as well as `np.ndarray`s and `pd.DataFrame`s if it is appropriate.

    See also the schema module for type hinting Arrays.

    Axes are fundamentally asynchronous, since they represent actual hardware resources that exist over I/O.
    Additionally, measurements may take finite time, and in the case of event stream axes, you may not know
    when values will be produced.
    """

    raw_value_stream: Optional[Subject]

    def collect_state(self):
        return None

    def receive_state(self, state):
        pass

    def append_point_to_history(self, point):
        self.collected_xs.append(point["time"])
        self.collected_ys.append(point["value"])

    def reset_history(self):
        self.collected_xs = []
        self.collected_ys = []

    def __init__(self, name: str, schema: type):
        self.name = name
        self.schema = schema

        self.raw_value_stream = Subject()

        # for scalar schemas we can provide a stream of values
        if schema in (float, int):
            self.collected_xs = []
            self.collected_ys = []
            self.raw_value_stream.subscribe(self.append_point_to_history)

    def emit(self, value):
        if self.raw_value_stream:
            self.raw_value_stream.on_next(
                {"value": value, "time": datetime.datetime.now().timestamp()}
            )

    async def trigger(self):
        return

    async def settle(self):
        raise NotImplementedError

    # We use a two level API in order to make the code here
    # more straightforward. *_internal methods are virtual
    # and set the internal behavior for an axis
    # the high level API provides synchronous (if available)
    # and asynchronous bindings which also handle emitting
    # values for subscribers
    async def write_internal(self, value):
        raise NotImplementedError

    async def read_internal(self) -> Any:
        raise NotImplementedError

    async def sync_write_internal(self, value):
        raise NotImplementedError

    async def sync_read_internal(self) -> Any:
        raise NotImplementedError

    # in general, you do not need to implement
    # the top level methods, unless you need to control how
    # values are emitted. You should be able to implement the
    # low level API above and be a client to the high level API
    # below
    async def write(self, value):
        value = await self.write_internal(value)
        self.emit(value)
        return value

    async def read(self):
        value = await self.read_internal()
        self.emit(value)
        return value

    def sync_read(self):
        value = self.sync_read_internal()
        self.emit(value)
        return value

    def sync_write(self, value):
        value = self.sync_write_internal(value)
        self.emit(value)
        return value


class ManualAxis(Axis):
    raw_value_stream: Optional[Subject]

    def __init__(self, name, schema, axis_descriptor, instrument):
        super().__init__(name, schema)

        self.axis_descriptor = axis_descriptor
        self.instrument = instrument

    async def write_internal(self, value):
        return await self.axis_descriptor.fwrite(self.instrument, value)

    async def read_internal(self):
        return await self.axis_descriptor.fread(self.instrument)


class TestManualAxis(ManualAxis):
    @property
    def readonly(self):
        return self.axis_descriptor.fmockwrite is None

    async def write_internal(self, value):
        return await self.axis_descriptor.fmockwrite(self.instrument, value)

    async def read_internal(self):
        return await self.axis_descriptor.fmockread(self.instrument)


class LogicalSubaxis(Axis):
    def __init__(self, name, schema, parent_axis, subaxis_name, index):
        schema = schema[subaxis_name]
        super().__init__(name, schema)

        self.parent_axis = parent_axis
        self.subaxis_name = subaxis_name
        self.index = index
        self.readonly = False

    async def write(self, value):
        old_state = list(self.parent_axis.logical_state)
        old_state[self.index] = value
        await self.parent_axis.write(old_state)

    async def read(self):
        raise NotImplementedError("Subaxis reads not supported.")

    async def settle(self):
        await self.parent_axis.settle()


class LogicalAxis(Axis):
    physical_axes: Dict[str, Axis]

    logical_coordinate_names: List[str]
    physical_coordinate_names: List[str]

    forward_transforms: Dict[str, Callable[[Any], Any]]
    inverse_transforms: Dict[str, Callable[[Any], Any]]

    logical_state: List[Any] = None
    physical_state: List[Any] = None

    internal_state_cls: type = None
    internal_state: Any = None

    def __init__(
        self,
        name,
        schema,
        physical_axes: Dict[str, Axis],
        forward_transforms,
        inverse_transforms,
        logical_state,
        internal_state=None,
    ):

        self.physical_axes = physical_axes
        self.logical_coordinate_names = list(inverse_transforms.keys())
        self.physical_coordinate_names = list(forward_transforms.keys())

        if schema is None:
            schema = {k: float for k in self.logical_coordinate_names}

        self.forward_transforms = forward_transforms
        self.inverse_transforms = inverse_transforms

        self.logical_state = logical_state
        self.internal_state = internal_state

        if self.internal_state is not None:
            if type(self.internal_state) == type:
                self.internal_state_cls = self.internal_state
                self.internal_state = self.internal_state_cls()
            else:
                self.internal_state_cls = type(self.internal_state)

        super().__init__(name, schema)

        for index, subaxis_name in enumerate(self.logical_coordinate_names):
            subaxis = LogicalSubaxis(
                f"{self.name}.{subaxis_name}",
                self.schema,
                self,
                subaxis_name,
                index,
            )
            setattr(self, subaxis_name, subaxis)

    def collect_state(self) -> LogicalAxisState:
        return LogicalAxisState(
            internal_state=self.internal_state,
            logical_state=self.logical_state,
            physical_state=self.physical_state,
        )

    def receive_state(self, state: LogicalAxisState):
        if self.internal_state_cls and not isinstance(
            state.internal_state, self.internal_state_cls
        ):
            warnings.warn(
                f"Logical Axis received invalid state {state}, "
                f"type did not match expected {self.internal_state_cls}."
            )
        else:
            self.internal_state = state.internal_state

    async def write(self, value):
        writes = []
        new_physical_state = []

        for axis_name, coordinate_transform in self.forward_transforms.items():
            physical_value = coordinate_transform(self.internal_state, *value)
            new_physical_state.append(physical_value)
            writes.append(self.physical_axes[axis_name].write(physical_value))

        await asyncio.gather(*writes)
        self.logical_state = value
        self.physical_state = new_physical_state

    async def read(self):
        axis_names, axes = zip(*self.physical_axes.items())
        values = await asyncio.gather(*[axis.read() for axis in axes])

        logical_values = []
        for inverse_transform in self.inverse_transforms.values():
            logical_values.append(inverse_transform(self.internal_state, *values))

        self.physical_state = values
        self.logical_state = logical_values
        return self.logical_state

    async def settle(self):
        await asyncio.gather(*[axis.settle() for axis in self.physical_axes.values()])


def _bind(function_name, driver, where):
    d = driver
    last = None
    for w in where + [function_name]:
        last = d
        if w is None:
            raise AttributeError()
        if isinstance(w, str):
            d = getattr(d, w)
        else:
            d = d[w]

    if callable(d):
        return d

    if isinstance(function_name, str):

        def bound(value=None):
            if value:
                setattr(last, function_name, value)
            else:
                return getattr(last, function_name)

    else:
        assert isinstance(function_name, int)

        def bound(value=None):
            if value:
                last[function_name] = value
            else:
                return last[function_name]

    return bound


class ProxiedAxis(Axis):
    backoff = BackoffConfig()

    _bound_write: Optional[Callable] = None
    _bound_read: Optional[Callable] = None
    _bound_poll_write: Optional[Callable] = None
    _bound_poll_read: Optional[Callable] = None

    def __init__(self, name, schema, driver, where, read, write, settle):
        super().__init__(name, schema)
        self.where = where
        self.driver = driver
        self._status = AxisStatus.Idle

        if read is None:
            read = where[-1]

            if write is None:
                write = where[-1]

            self.where = where[:-1]

        self.readonly = write is None

        if isinstance(read, (str, int)):
            read = PolledRead(read=read, poll=None)

        if isinstance(write, (str, int)) or write is None:
            write = PolledWrite(write=write, poll=None)

        try:
            self._bound_poll_read = _bind(read.poll, driver, self.where)
            self._bound_read = _bind(read.read, driver, self.where)
        except AttributeError:
            self._bound_read = _bind(read.read, driver, self.where)
        if write.write is not None:
            try:
                self._bound_poll_write = _bind(write.poll, driver, self.where)
                self._bound_write = _bind(write.write, driver, self.where)
            except AttributeError:
                self._bound_write = _bind(write.write, driver, self.where)
        else:
            # A proxied detector only...
            pass

    async def read_internal(self):
        if self._status == AxisStatus.Idle:
            value = self._bound_read()

            return await value if asyncio.iscoroutine(value) else value
        elif self._status == AxisStatus.Moving:
            await self._settle(True)
            return self._bound_read()

    async def write_internal(self, value):
        if self._status == AxisStatus.Moving:
            raise ValueError("Already moving!")

        self._bound_write(value)

        if self._bound_poll_write is not None:
            self._status = AxisStatus.Moving
            await self._settle(False)

        return value

    async def settle(self):
        await self._settle(False)

    async def _settle(self, poll_by_read=False):
        """
        The default behavior here is that an axis is settled once the async write as finished. Other behavior can
        of course be provided.
        :return:
        """
        poll = self._bound_poll_read if poll_by_read else self._bound_poll_write

        if self._status == AxisStatus.Moving:
            sleep_duration = self.backoff.next_duration()

            while True:
                await asyncio.sleep(sleep_duration)
                sleep_duration = self.backoff.next_duration(sleep_duration)

                if poll():
                    self._status = AxisStatus.Idle
                    return


class TestAxis(Axis):
    def __init__(self, name, schema, mock=None, readonly=True, *args, **kwargs):
        super().__init__(name, schema)
        self._value = default_value_for_schema(schema)
        self.mock = mock or {}
        self._mock_read = self.mock.get("read")
        self._mock_write = self.mock.get("write")
        self._mock_settle = self.mock.get("settle")
        self.init_args = args
        self.init_kwargs = kwargs
        self.readonly = readonly

    async def read(self):
        return self.sync_read_internal()

    async def write(self, value):
        return self.sync_write_internal(value)

    def sync_read_internal(self):
        return self._value if not self._mock_read else self._mock_read()

    def sync_write_internal(self, value):
        if self._mock_write:
            return self._mock_write(value)
        else:
            self._value = value
            return value

    async def settle(self):
        if self._mock_settle:
            self._mock_settle()
