import asyncio
import copy
import json
from typing import List

from dataclasses import dataclass

from zhivago.collections import AttrDict, map_treelike_nodes
from zhivago.panels.basic_instrument_panel import BasicInstrumentPanel
from zhivago.actor import Actor
from .axis import Axis, Detector, TestAxis, TestDetector


class Generate:
    """
    A sentinel for code generation
    """

    def __init__(self, capture=None):
        self.capture = capture

class Properties:
    """
    Represents a collection of settings associated to an instrument, axis,
    or detector.
    """

    def __init__(self):
        pass

    def __repr__(self):
        return 'Properties()'

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

class PathRecorder:
    def __init__(self):
        self.path = []

    def __getattr__(self, item):
        self.path.append(item)
        return self

    def __getitem__(self, item):
        self.path.append(item)
        return self

class PhonyDriver:
    def __getattr__(self, item):
        return getattr(PathRecorder(), item)

Driver = PhonyDriver()

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

    def __init__(self, wrapper):
        self.axis_tree = {}
        self.wheremap = {}
        self.wrapper = wrapper

        for spec_name, spec in self.specification.items():
            if isinstance(spec, AxisListSpecification):
                current_tree = self.axis_tree
                where = _unwrapped_where(spec.where)

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
                where = _unwrapped_where(spec.where)

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

            self.wheremap[spec_name] = _unwrapped_where(spec.where)
        self.axis_tree = map_treelike_nodes(self.axis_tree, AttrDict)

    def __getattr__(self, item):
        current_tree = self.axis_tree
        for w in self.wheremap[item]: current_tree = current_tree[w]

        return current_tree

class ZhivagoInstrumentMeta(type):
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

            if isinstance(namespace['test_cls'], Generate):
                class SpecializedTestInstrument(TestInstrument):
                    specification = namespace['specification_']
                    context = namespace['test_cls'].capture

                namespace['test_cls'] = SpecializedTestInstrument

        return super().__new__(cls, name, bases, namespace)

class ManagedInstrument(Actor, metaclass=ZhivagoInstrumentMeta):
    panel_cls = BasicInstrumentPanel
    driver_cls = None
    test_cls = None
    proxy_to_driver = False

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
                print(spec, axis)
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
