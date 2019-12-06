import asyncio
from typing import Optional

import datetime
import rx
from rx.subject import Subject
from daquiri.data import reactive_frame
from daquiri.instrument.property import PolledWrite, PolledRead

__all__ = ('Axis', 'Detector', 'TestAxis', 'TestDetector', 'ProxiedAxis',)


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


class ProxiedAxis(Axis):
    def __init__(self, name, schema, driver, where, read, write):
        super().__init__(name, schema)
        self.where = where
        self.driver = driver
        self._status = Detector.IDLE

        if isinstance(read, str):
            read = PolledRead(read=read, poll=None)

        if isinstance(write, str) or write is None:
            write = PolledWrite(write=write, poll=None)

        # Exponential backoff constants, wait 30ms initially, then 45ms (30ms x 1.5) up to 200ms maximum
        self.backoff = (0.03, 1.5, 0.2,)

        def _bind(function_name):
            d = driver
            for w in where + [function_name]:
                if w is None:
                    raise AttributeError()
                if isinstance(w, str):
                    d = getattr(d, w)
                else:
                    d = d[w]

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
    DEFAULT_VALUES = {
        int: 0,
        float: 0,
        str: '',
    }

    def __init__(self, name, schema, mock_read=None, mock_write=None):
        super().__init__(name, schema)
        self._value = self.DEFAULT_VALUES[self.schema]
        self._mock_read = mock_read
        self._mock_write = mock_write

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