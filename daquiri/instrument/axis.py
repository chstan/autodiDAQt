import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, List, Callable, Any

import datetime
import rx
from rx.subject import Subject
from daquiri.data import reactive_frame

__all__ = ('Axis', 'Detector', 'TestAxis', 'ProxiedAxis', 'LogicalAxis',
           'PolledRead', 'PolledWrite')


@dataclass
class PolledWrite:
    write: Optional[str] = None
    poll: Optional[str] = None


@dataclass
class PolledRead:
    read: str
    poll: Optional[str] = None


class Detector:
    """
    Representation of a detector which can read values.

    Detectors have fixed schema: in this sense, you can always expect to receive the same shape data
    back from the detector. In most cases, detectors record single points, but you can produce any Python
    primitive, as well as `np.ndarray`s and `pd.DataFrame`s if it is appropriate.

    Detectors are fundamentally asynchronous, since they represent actual hardware resources that exist over I/O.
    Additionally, measurements may take finite time, and in the case of event stream detectors, you may not know
    when values will be produced.
    """
    IDLE = 0
    MOVING = 1

    DEFAULT_VALUES = {
        int: 0,
        float: 0,
        str: '',
    }

    raw_value_stream: Optional[Subject]
    collected_value_stream: Optional[rx.Observable]

    def __init__(self, name: str, schema: type):
        self.name = name
        self.schema = schema

        # for scalar schemas we can provide a stream of values
        if schema in (float, int,):
            self.raw_value_stream, self.collected_value_stream = reactive_frame()
        else:
            self.raw_value_stream = None
            self.collected_value_stream = None

    async def read(self):
        raise NotImplementedError('')

    def sync_read(self):
        raise NotImplementedError('')

    async def trigger(self):
        raise NotImplementedError('')


class Axis(Detector):
    """
    Representation of a motor or detector
    """

    async def write(self, value):
        raise NotImplementedError('')

    async def settle(self):
        raise NotImplementedError('')


class LogicalSubaxis(Axis):
    def __init__(self, name, schema, parent_axis, subaxis_name, index):
        super().__init__(name, schema)

        self.parent_axis = parent_axis
        self.subaxis_name = subaxis_name
        self.index = index

    async def write(self, value):
        old_state = list(self.parent_axis.logical_state)
        old_state[self.index] = value
        await self.parent_axis.write(old_state)

    async def read(self):
        raise NotImplementedError('Subaxis reads not supported.')

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

    def __init__(self, name, schema,
                 physical_axes: Dict[str, Axis], forward_transforms, inverse_transforms,
                 logical_state, internal_state=None):

        self.physical_axes = physical_axes

        self.logical_coordinate_names = list(inverse_transforms.keys())
        self.physical_coordinate_names = list(forward_transforms.keys())

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
            subaxis = LogicalSubaxis(f'{self.name}.{subaxis_name}', self.schema, self, subaxis_name, index)
            setattr(self, subaxis_name, subaxis)

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


class ProxiedAxis(Axis):
    def __init__(self, name, schema, driver, where, read, write):
        super().__init__(name, schema)
        self.where = where
        self.driver = driver
        self._status = Detector.IDLE

        if read is None:
            read = where[-1]

            if write is not None:
                write = where[-1]

            self.where = where[:-1]

        if isinstance(read, str):
            read = PolledRead(read=read, poll=None)

        if isinstance(write, str) or write is None:
            write = PolledWrite(write=write, poll=None)

        # Exponential backoff constants, wait 30ms initially, then 45ms (30ms x 1.5) up to 200ms maximum
        self.backoff = (0.03, 1.5, 0.2,)

        def _bind(function_name):
            d = driver
            last = None
            for w in self.where + [function_name]:
                last = d
                if w is None:
                    raise AttributeError()
                if isinstance(w, str):
                    d = getattr(d, w)
                else:
                    d = d[w]

            if not callable(d):
                print('_bind sync', last, function_name)

                def bound(value=None):
                    if value:
                        setattr(last, function_name, value)
                    else:
                        return getattr(last, function_name)

                return bound

            print('_bind', d)
            return d

        try:
            self._bound_poll_read = _bind(read.poll)
            self._bound_read = _bind(read.read)
        except AttributeError:
            self._bound_poll_read = None
            self._bound_read = _bind(read.read)
        if write.write is not None:
            try:
                self._bound_poll_write = _bind(write.poll)
                self._bound_write = _bind(write.write)
            except AttributeError:
                self._bound_poll_write = None
                self._bound_write = _bind(write.write)
        else:
            # A proxied detector only...
            pass

    async def read(self):
        if self._status == Detector.IDLE:
            value = self._bound_read()

            if asyncio.iscoroutine(value):
                value = await value

            if self.raw_value_stream:
                self.raw_value_stream.on_next({'value': value, 'time': datetime.datetime.now().timestamp()})
            return value
        elif self._status == Detector.MOVING:
            sleep_time, sleep_backoff, sleep_maximum = self.backoff

            while True:
                await asyncio.sleep(sleep_time)
                if self._bound_poll_read():
                    self._status = Detector.IDLE
                    value = self._bound_read()
                    if self.raw_value_stream:
                        self.raw_value_stream.on_next({'value': value, 'time': datetime.datetime.now().timestamp()})
                    return value

                sleep_time *= sleep_backoff
                sleep_time = sleep_maximum if sleep_time > sleep_maximum else sleep_time

    async def write(self, value):
        if self._status == Detector.MOVING:
            raise ValueError('Already moving!')

        if self._bound_poll_write is not None:
            self._status = Detector.MOVING
            self._bound_write(value)

            sleep_time, sleep_backoff, sleep_maximum = self.backoff

            while True:
                await asyncio.sleep(sleep_time)

                if self._bound_poll_write():
                    self._status = Detector.IDLE
                    return

                sleep_time *= sleep_backoff
                sleep_time = sleep_maximum if sleep_time > sleep_maximum else sleep_time

    async def settle(self):
        """
        The default behavior here is that an axis is settled once the async write as finished. Other behavior can
        of course be provided.
        :return:
        """
        if self._status == Detector.MOVING:
            sleep_time, sleep_backoff, sleep_maximum = self.backoff

            while True:
                await asyncio.sleep(sleep_time)

                if self._bound_poll_write():
                    self._status = Detector.IDLE
                    return

                sleep_time *= sleep_backoff
                sleep_time = sleep_maximum if sleep_time > sleep_maximum else sleep_time


class TestDetector(Detector):
    def __init__(self, name, schema, mock=None, *args, **kwargs):
        super().__init__(name, schema)
        self._value = self.DEFAULT_VALUES[self.schema]
        self.mock = mock or {}
        self._mock_read = self.mock.get('read')
        self._mock_write = self.mock.get('write')
        self.init_args = args
        self.init_kwargs = kwargs

    async def read(self):
        if self._mock_read:
            value = self._mock_read()
        else:
            value = self._value

        if self.raw_value_stream:
            self.raw_value_stream.on_next({'value': value, 'time': datetime.datetime.now().timestamp()})

        return value

    def sync_read(self):
        if self._mock_read:
            value = self._mock_read()
        else:
            value = self._value

        if self.raw_value_stream:
            self.raw_value_stream.on_next({'value': value, 'time': datetime.datetime.now().timestamp()})

        return value

    async def trigger(self):
        return


class TestAxis(TestDetector):
    async def write(self, value):
        if self._mock_write:
            self._mock_write(value)
        else:
            self._value = value

    async def settle(self):
        return
