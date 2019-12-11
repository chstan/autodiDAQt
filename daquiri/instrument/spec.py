import asyncio
import functools

from daquiri.instrument.property import Property, ChoiceProperty, Specification, LogicalAxisSpecification
from daquiri.mock import MockDriver
from daquiri.panels.basic_instrument_panel import BasicInstrumentPanel
from daquiri.actor import Actor
from daquiri.utils import safe_lookup, tokenize_access_path


def build_instrument_property(prop: Property, name: str):
    where = prop.where_list or [name]

    def property_getter(self):
        return functools.reduce(safe_lookup, where, self.driver)

    if isinstance(prop, ChoiceProperty):
        def property_setter(self, value):
            assert(value in prop.choices)
            interim = functools.reduce(safe_lookup, where[:-1], self.driver)
            setattr(interim, where[-1], value)
    else:
        def property_setter(self, value):
            interim = functools.reduce(safe_lookup, where[:-1], self.driver)
            setattr(interim, where[-1], value)

    return property(property_getter, property_setter, doc=f'Proxy Property for {prop} at {where}.')


def build_proxy_method(proxy_name):
    def proxy_method(self, *args, **kwargs):
        return getattr(self.driver, proxy_name)(*args, **kwargs)

    return proxy_method


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
            'axis_root': {k: getattr(self, k) for k in self.specification_.keys()},
            'properties': {}
        }

    def lookup_axis(self, axis_path):
        axis_path = tokenize_access_path(axis_path)

        current = self
        for elem in axis_path:
            if isinstance(elem, str):
                current = getattr(current, elem)
            else:
                current = current[elem]

        return current

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        simulate = self.app.config.instruments.simulate_instruments
        self.driver = MockDriver() if simulate else self.driver_cls()

        def is_spec(s):
            try:
                return isinstance(getattr(self, s), Specification)
            except:
                return False

        spec_names = [s for s in dir(self) if is_spec(s)]
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

    async def run(self):
        while True:
            await asyncio.sleep(5)
