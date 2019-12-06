import asyncio
import copy
import functools
from typing import List

from loguru import logger

from daquiri.collections import AttrDict, map_treelike_nodes
from daquiri.instrument.property import Property, ChoiceProperty, Specification, AxisListSpecification, \
    AxisSpecification
from daquiri.panels.basic_instrument_panel import BasicInstrumentPanel
from daquiri.actor import Actor
from daquiri.utils import InstrumentScanAccessRecorder, safe_lookup
from .axis import Axis, Detector, TestAxis, TestDetector, ProxiedAxis


class Generate:
    """
    A sentinel for code generation
    """

    def __init__(self, capture=None):
        self.capture = capture


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
                where = spec.where_list or [spec_name]

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
                where = spec.where_list or [spec_name]

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

            self.wheremap[spec_name] = spec.where_list or [spec_name]
        self.axis_tree = map_treelike_nodes(self.axis_tree, AttrDict)

    def __setattr__(self, key, value):
        if self.properties and key in self.properties:
            logger.info(f'Writing attribute {key} -> {value}')

        # should be pretty harmless
        super().__setattr__(key, value)

    def __getattr__(self, item):
        if item in self.proxy_methods:
            def test_proxy_method(*args, **kwargs):
                logger.info(f'Called proxy method {item} with {args}, {kwargs}.')

            return test_proxy_method

        if item in self.properties:
            logger.info(f'Reading attribute {item}')
            try:
                return super().__getattribute__(item)
            except AttributeError:
                return None

        return functools.reduce(safe_lookup, self.wheremap[item], self.axis_tree)


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
            namespace['scan'] = lambda s: InstrumentScanAccessRecorder(s, specification, namespace.get('properties', {}))

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

    def build_axes(self):
        self.axes_and_detectors = {}
        for k, v in self.specification_.items():
            if isinstance(v, AxisSpecification):
                self.axes_and_detectors[k] = ProxiedAxis(
                    name=k, schema=v.schema, where=v.where, driver=self.driver, read=v.read, write=v.write
                )
            elif isinstance(v, AxisListSpecification):
                print(k, v)
            else:
                raise ValueError(f'Unknown Axis Specification {v}')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.app.config.instruments.simulate_instruments:
            self.proxy_to_driver = True
            self.driver = self.test_cls(wrapper=self)
        else:
            self.driver = self.driver_cls()
            self.build_axes()

    def __getattribute__(self, name):
        if name in ['__dict__', 'axis_and_detectors', 'proxy_to_driver', 'specification_'] or name not in self.specification_:
            return super().__getattribute__(name)

        if self.proxy_to_driver:
            return getattr(self.driver, name)
        elif name in self.axes_and_detectors:
            return self.axes_and_detectors[name]

        return super().__getattribute__(name)

    async def run(self):
        while True:
            await asyncio.sleep(5)
