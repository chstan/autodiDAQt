import asyncio

from daquiri.actor import Actor
from daquiri.instrument.spec import Specification, LogicalAxisSpecification, MockDriver, PropertySpecification, \
    MethodSpecification
from daquiri.panels import BasicInstrumentPanel
from daquiri.utils import safe_lookup, AccessRecorder, tokenize_access_path


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

            if isinstance(current, (Specification, PropertySpecification,)):
                break

        return current.to_scan_axis(self.scope, left, rest, *args, **kwargs)


class ManagedInstrument(Actor):
    panel_cls = BasicInstrumentPanel

    driver_cls = None
    test_cls = None

    properties = {}
    profiles = {}
    proxy_methods = []

    def set_profile(self, profile_name):
        for name, value in self.profiles[profile_name].items():
            setattr(self, name, value)

    @property
    def ui_specification(self):
        return {
            'axes': {k: getattr(self, k) for k in self.specification_.keys()},
            'properties': {k: getattr(self, k) for k in self.properties_.keys()},
            'methods': {k: getattr(self, k) for k in self.methods_.keys()},
        }

    def lookup_axis(self, axis_path):
        return safe_lookup(self, tokenize_access_path(axis_path))

    @classmethod
    def scan(cls, instrument_name):
        return ScanRecorder(cls, instrument_name)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        simulate = self.app.config.instruments.simulate_instruments
        self.driver = MockDriver() if simulate else self.driver_cls()

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
        self.properties_ = {spec_name: getattr(self, spec_name) for spec_name in property_spec_names}
        for spec_name in property_spec_names:
            spec = getattr(self, spec_name)
            setattr(self, spec_name, spec.realize(spec_name, self.driver, self))

        # METHODS
        self.methods_ = {spec_name: getattr(self, spec_name) for spec_name in method_spec_names}
        for spec_name in method_spec_names:
            spec = getattr(self, spec_name)
            setattr(self, spec_name, spec.realize(spec_name, self.driver, self))

    async def run(self):
        while True:
            await asyncio.sleep(5)
