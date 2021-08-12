from typing import Iterator, Optional, Tuple

import asyncio
import datetime

from autodidaqt_common.path import AxisPath
from autodidaqt_common.remote.command import AxisRead, ReadAxisCommand, WriteAxisCommand
from autodidaqt_common.remote.schema import RemoteAxisState, RemoteDriverInfo, RemoteInstrumentState
from loguru import logger

from autodidaqt.actor import MessagingActor
from autodidaqt.instrument.axis import Axis
from autodidaqt.instrument.spec import (
    LogicalAxisSpecification,
    MethodSpecification,
    MockDriver,
    PropertySpecification,
    Specification,
)
from autodidaqt.panels import BasicInstrumentPanel
from autodidaqt.state import InstrumentState
from autodidaqt.utils import AccessRecorder, safe_lookup


class ScanRecorder(AccessRecorder):
    def __init__(self, instrument_cls, instrument_name):
        super().__init__(scope=instrument_name)
        self.instrument_cls = instrument_cls

    def __call__(self, *args, **kwargs):
        rest = self.path
        left = []
        current = self.instrument_cls

        while rest:
            first, rest = rest[0], rest[1:]
            left += [first]
            current = safe_lookup(current, first)

            if isinstance(current, (Specification, PropertySpecification)):
                break

        return current.to_scan_axis(self.scope, left, rest, *args, **kwargs)


class ManagedInstrument(MessagingActor):
    panel_cls = BasicInstrumentPanel
    panel = None

    driver_cls = None
    test_cls = None

    profiles = {}
    proxy_methods = []
    active_profile_name: Optional[str] = None

    def set_profile(self, profile_name):
        self.active_profile_name = profile_name
        for name, value in self.profiles[profile_name].items():
            setattr(self, name, value)

    async def handle_user_message(self, message):
        if isinstance(message, ReadAxisCommand):
            axis_path = AxisPath.to_tuple(message.axis_path)
            axis = self.lookup(axis_path[1:])
            value = await axis.read()
            self.app.send_to_remote(
                AxisRead(
                    axis_path=axis_path,
                    value=axis.type_def.to_value(value),
                    read_time=datetime.datetime.now().isoformat(),
                )
            )

        elif isinstance(message, WriteAxisCommand):
            axis_path = AxisPath.to_tuple(message.axis_path)
            axis = self.lookup(axis_path[1:])
            value = await axis.write(message.value.to_instance())
            self.app.send_to_remote(
                AxisRead(
                    axis_path=axis_path,
                    value=axis.type_def.to_value(value),
                    read_time=datetime.datetime.now().isoformat(),
                )
            )

    def lookup(self, path_to_target):
        target = self
        for p in path_to_target:
            if isinstance(p, int):
                target = target[p]
            else:
                target = getattr(target, p)

        return target

    def collect_state(self) -> InstrumentState:
        try:
            panel_state = self.panel.collect_state()
        except:
            panel_state = None
        return InstrumentState(
            axes={
                k: [vs.collect_state() for vs in v] if isinstance(v, list) else v.collect_state()
                for k, v in self.axes.items()
            },
            properties={},
            panel_state=panel_state,
        )

    def receive_state(self, state: InstrumentState):
        for k in set(state.axes).intersection(self.axes):
            if isinstance(self.axes[k], list):
                for axis, axis_state in zip(self.axes[k], state.axes[k]):
                    axis.receive_state(axis_state)
            else:
                self.axes[k].receive_state(state.axes[k])

        if self.panel is not None:
            self.panel.receive_state(state.panel_state)

    @property
    def axes(self):
        return {k: getattr(self, k) for k in self.specification_.keys()}

    @property
    def properties(self):
        return {k: getattr(self, k) for k in self.properties_.keys()}

    @property
    def methods(self):
        return {k: getattr(self, k) for k in self.methods_.keys()}

    @property
    def ui_specification(self):
        return {
            "axes": self.axes,
            "properties": self.properties,
            "methods": {k: getattr(self, k) for k in self.methods_.keys()},
        }

    def lookup_axis(self, axis_path):
        return safe_lookup(self, AxisPath.to_tuple(axis_path))

    @classmethod
    def scan(cls, instrument_name):
        return ScanRecorder(cls, instrument_name)

    def __init__(self, driver_init=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if driver_init is None:
            driver_init = {}

        simulate = self.app.config.instruments.simulate_instruments
        self.driver = (
            MockDriver()
            if simulate
            else self.driver_cls(*driver_init.get("args", []), **driver_init.get("kwargs", {}))
        )
        if simulate:
            logger.warning(f"Simulating instrument: {type(self).__name__}")

        def is_spec(s, kind: type = Specification):
            try:
                return isinstance(getattr(self, s), kind)
            except:
                return False

        # AXES
        spec_names = [s for s in dir(self) if is_spec(s, kind=Specification)]
        property_spec_names = [s for s in dir(self) if is_spec(s, kind=PropertySpecification)]
        method_spec_names = [s for s in dir(self) if is_spec(s, kind=MethodSpecification)]

        self.specification_ = {spec_name: getattr(self, spec_name) for spec_name in spec_names}
        for spec_name in spec_names:
            spec = getattr(self, spec_name)
            if not isinstance(spec, LogicalAxisSpecification):
                setattr(self, spec_name, spec.realize(spec_name, self.driver, self))

        # logical axes require physical axes instantiated so we do this in a second pass for now
        for spec_name in spec_names:
            spec = getattr(self, spec_name)
            if isinstance(spec, LogicalAxisSpecification):
                setattr(self, spec_name, spec.realize(spec_name, self.driver, self))

        # PROPERTIES
        self.properties_ = {
            spec_name: getattr(self, spec_name) for spec_name in property_spec_names
        }
        for spec_name in property_spec_names:
            spec = getattr(self, spec_name)
            setattr(self, spec_name, spec.realize(spec_name, self.driver, self))

        # METHODS
        self.methods_ = {spec_name: getattr(self, spec_name) for spec_name in method_spec_names}
        for spec_name in method_spec_names:
            spec = getattr(self, spec_name)
            setattr(self, spec_name, spec.realize(spec_name, self.driver, self))

    async def run_step(self):
        await asyncio.sleep(0.25)

    async def shutdown(self):
        """
        Essentially, we need to put this instrument into a safed configuration.
        How this is to be done may depend on the driver, or on the axis.
        """

        # we can consider gathering here instead, but there are safety reasons to want to avoid
        # running shutdown code for the same instrument simultaneously
        for path, axis in self.flat_axes():
            logger.info(f"Shutting down {path}")
            await axis.shutdown()
            logger.info(f"Finished shutting down {path}")

    def flat_axes(self) -> Iterator[Tuple[str, Axis]]:
        for axis_name, axis in self.axes.items():
            if isinstance(axis, list):
                for idx, a in enumerate(axis):
                    yield [axis_name, idx], a
            else:
                yield [axis_name], axis

    @property
    def is_simulating(self):
        return isinstance(self.driver, MockDriver)

    def collect_remote_property_state(self, property_name, property_spec):
        raise NotImplementedError

    def collect_remote_method_state(self, method_name, method_spec):
        raise NotImplementedError

    def collect_remote_state(self):
        axes_state = []
        for path, axis in self.flat_axes():
            axes_state.append(RemoteAxisState(path, axis.type_def.id))

        return RemoteInstrumentState(
            is_simulating=self.is_simulating,
            flat_axes=axes_state,
            driver_info=RemoteDriverInfo(self.driver.__class__.__name__),
            methods_info={k: self.collect_remote_method_state(k, v) for k, v in self.methods},
            properties_info={
                k: self.collect_remote_property_state(k, v) for k, v in self.properties
            },
            active_profile_name=self.active_profile_name,
            profiles_info=self.profiles,
        )
