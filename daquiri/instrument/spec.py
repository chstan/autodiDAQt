import asyncio
import copy
import functools
from typing import Any, List, Optional, Union

from dataclasses import dataclass, field

from daquiri.collections import AttrDict, map_treelike_nodes
from daquiri.panels.basic_instrument_panel import BasicInstrumentPanel
from daquiri.actor import Actor
from .axis import Axis, Detector, TestAxis, TestDetector


class Generate:
    """
    A sentinel for code generation
    """

    def __init__(self, capture=None):
        self.capture = capture


@dataclass
class Property:
    where: Optional[str] = None


@dataclass
class ChoiceProperty(Property):
    choices: List[Any] = field(default_factory=list)


class Specification:
    pass


class AxisListSpecification(Specification):
    """
    Represents the specification for a list of axes, such as is present on
    a motion controller.
    """
    def __init__(self, internal_specification, where=None):
        self.internal_specification = internal_specification
        self.name = None
        self.where = where

    def __repr__(self):
        return ('AxisListSpecification('
                f'name={self.name!r},'
                f'where={self.where!r},'
                f'internal_specification={self.internal_specification!r},'
                ')')


class AxisSpecification(Specification):
    """
    Represents a single axis or detector.
    """
    def __init__(self, schema, where=None, range=None, validator=None, axis=True, read=None, write=None):
        self.name = None
        self.schema = schema
        self.range = range
        self.validator = validator
        self.is_axis = axis
        self.read = read
        self.write = write
        self.where = where

    def __repr__(self):
        return ('AxisSpecification('
                f'name={self.name!r},'
                f'where={self.where!r},'
                f'schema={self.schema!r},'
                f'range={self.range!r},'
                f'validator={self.validator!r},'
                f'is_axis={self.is_axis!r},'
                f'read={self.read}'
                f'write={self.write}'
                ')')


class DetectorSpecification(AxisSpecification):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, axis=True)


@dataclass
class PolledWrite:
    write: str
    poll: str


@dataclass
class PolledRead:
    read: str
    poll: str


def _unwrapped_where(where):
    as_list = where.split('.') if isinstance(where, str) else where
    return as_list

def _test_axis(axis_specification: AxisSpecification, **kwargs):
    cls = TestAxis if axis_specification.is_axis else TestDetector
    return cls(axis_specification.name, axis_specification.schema, **kwargs)


def _axis_from_specification(axis_specification: Specification, driver=None):
    if isinstance(axis_specification, AxisListSpecification):
        pass

class TestInstrument:
    specification = None
    context = None
    properties = None
    proxy_methods = None

    def __init__(self, wrapper):
        self.axis_tree = {}
        self.wheremap = {}
        self.wrapper = wrapper
        if self.properties is None:
            self.properties = {}

        if self.proxy_methods is None:
            self.proxy_methods = []

        if self.context is None:
            self.context = {}

        for spec_name, spec in self.specification.items():
            if isinstance(spec, AxisListSpecification):
                current_tree = self.axis_tree
                where = _unwrapped_where(spec.where or [spec_name])

                for key in where[:-1]:
                    if key not in current_tree:
                        current_tree[key] = {}

                    current_tree = current_tree[key]

                length = self.context[spec_name]['length']

                assert(where[-1] not in current_tree)
                current_tree[where[-1]] = {}

                for i in range(length):
                    current_tree[where[-1]][i] = _test_axis(spec.internal_specification(i))
            elif isinstance(spec, AxisSpecification):
                current_tree = self.axis_tree
                where = _unwrapped_where(spec.where or [spec_name])

                for key in where[:-1]:
                    if key not in current_tree:
                        current_tree[key] = {}

                    current_tree = current_tree[key]

                assert(where[-1]) not in current_tree

                test_axis_context = copy.copy(self.context.get(spec_name, {}))
                if 'mock_read' in test_axis_context:
                    test_axis_context['mock_read'] = getattr(self.wrapper, test_axis_context['mock_read'])
                if 'mock_write' in test_axis_context:
                    test_axis_context['mock_write'] = getattr(self.wrapper, test_axis_context['mock_write'])

                current_tree[where[-1]] = _test_axis(spec, **test_axis_context)

            self.wheremap[spec_name] = _unwrapped_where(spec.where or [spec_name])
        self.axis_tree = map_treelike_nodes(self.axis_tree, AttrDict)

    def __getattr__(self, item):
        if item in self.proxy_methods:
            def test_proxy_method(*args, **kwargs):
                print(f'Called proxy method {item} with {args}, {kwargs}.')

            return test_proxy_method

        if item in self.properties:
            return super().__getattribute__(self, item)

        return functools.reduce(safe_lookup, self.wheremap[item], self.axis_tree)


def safe_lookup(d: Any, s: Union[str, int]):
    if isinstance(s, str):
        return getattr(d, s)
    return d[s]


def build_instrument_property(prop: Property, name: str):
    where = _unwrapped_where(prop.where or [name])

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


class DaquiriInstrumentMeta(type):
    """
    Represents a wrapped physical instrument. This metaclass is
    responsible for:

    1. Collecting and compiling user specifications for detectors and axes
    2. Generating a test class if required
    3. Collecting and making available a schema for the UI
    """

    def __new__(cls, name, bases, namespace, **kwargs):
        driver_cls = namespace.get('driver_cls')
        is_abstract_subclass = driver_cls is None

        if not is_abstract_subclass:
            specification = {k: v for k, v in namespace.items() if isinstance(v, Specification)}
            namespace['specification_'] = specification

            if 'properties' in namespace:
                for name, prop in namespace['properties'].items():
                    assert name not in namespace
                    namespace[name] = build_instrument_property(prop, name)

            namespace['profiles_'] = namespace.pop('profiles', {})

            if 'proxy_methods' in namespace:
                for proxy_method in namespace['proxy_methods']:
                    assert proxy_method not in namespace

                    namespace[proxy_method] = build_proxy_method(proxy_method)

            if isinstance(namespace['test_cls'], Generate):
                class SpecializedTestInstrument(TestInstrument):
                    specification = namespace['specification_']
                    context = namespace['test_cls'].capture
                    properties = namespace.get('properties')
                    proxy_methods = namespace.get('proxy_methods', [])

                namespace['test_cls'] = SpecializedTestInstrument

        return super().__new__(cls, name, bases, namespace)


class ManagedInstrument(Actor, metaclass=DaquiriInstrumentMeta):
    panel_cls = BasicInstrumentPanel
    driver_cls = None
    test_cls = None
    proxy_to_driver = False

    def set_profile(self, profile_name):
        for name, value in self.profiles_[profile_name].items():
            setattr(self, name, value)

    @property
    def axes(self) -> List[Axis]:
        return []

    @property
    def detectors(self) -> List[Detector]:
        return []

    @property
    def ui_specification(self):
        ui_spec = {
            'axis_root': {},
            'properties': {},
        }

        for spec_name, spec in self.specification_.items():
            axis = getattr(self, spec_name)

            if isinstance(spec, AxisListSpecification):
                ui_spec['axis_root'][spec_name] = [spec.internal_specification(i) for i in range(len(axis))]
            else:
                ui_spec['axis_root'][spec_name] = spec

        return ui_spec

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.app.config.instruments.simulate_instruments:
            self.proxy_to_driver = True
            self.driver = self.test_cls(wrapper=self)
        else:
            self.driver = self.driver_cls()

    def __getattribute__(self, name):
        if name in ['__dict__', 'proxy_to_driver', 'specification_'] or name not in self.specification_:
            return super().__getattribute__(name)

        if self.proxy_to_driver:
            return getattr(self.driver, name)

        return super().__getattribute__(name)

    async def run(self):
        while True:
            await asyncio.sleep(5)
