import asyncio
from enum import IntEnum
import inspect
from functools import reduce

from daquiri.actor import Actor

__all__ = ('InstrumentTypes', 'serialize_signature', 'FrontPanelCommon', 'FrontPanelBase', 'ALLOWABLE_BASES',)

class InstrumentTypes(IntEnum):
    DMM = 0
    OSCILLOSCOPE = 1
    FUNCTION_GENERATOR = 2
    MOTION_CONTROLLER = 3
    PIEZO_CONTROLLER = 4
    TEMPERATURE_CONTROLLER = 5
    LOCKIN_AMPLIFIER = 6

def is_property(tree):
    try:
        if 'getter' in tree:
            return True

        return False
    except:
        return False


def is_method(tree):
    try:
        if 'signature' in tree:
            return True

        return False
    except:
        return False


def is_leaf(tree):
    """
    This could be more intelligent, i.e. we could actually have a structured
    data type at the leaf, a named tuple or similar, but then serialization
    would be trickier because namedtuples dump as lists

    :param tree:
    :return:
    """
    # check if we are literally at a leaf value
    if not isinstance(tree, dict):
        return True

    # check if we are at a property
    if is_property(tree):
        return True

    # check if we are at a method
    if is_method(tree):
        return True

    return False


def serialize_signature(signature: inspect.Signature):
    sig = {
        'parameters': [(pname, ) for pname, param in signature.parameters.items()]
    }

    if signature.return_annotation != signature.empty:
        sig['return'] = signature.return_annotation

    return sig

class FrontPanelCommon(object):
    instrument_cls = None
    _kwargs = None
    PROVIDE_KWARGS = None

    @property
    def instrument_type(self):
        raise NotImplementedError()

    @property
    def data_schema(self):
        # maybe these can be inferred from the measurement function
        if self.instrument_type == InstrumentTypes.TEMPERATURE_CONTROLLER:
            # provides an event stream
            return {
                'method': 'stream',
                'type': 'event',
            }
        elif self.instrument_type == InstrumentTypes.DMM:
            # data is list of pairs, time of read and value for each channel
            return {
                'method': 'stream',
                'type': 'event',
            }
        elif self.instrument_type == InstrumentTypes.FUNCTION_GENERATOR:
            return None
        elif self.instrument_type == InstrumentTypes.MOTION_CONTROLLER:
            return None
        elif self.instrument_type == InstrumentTypes.OSCILLOSCOPE:
            raise NotImplementedError()
        elif self.instrument_type == InstrumentTypes.LOCKIN_AMPLIFIER:
            return {
                'method': 'stream',
                'type': 'event',
            }

        return None

    @property
    def schema(self):
        return {
            'instrument_cls': self.instrument_cls.__name__,
        }

    @property
    def tree_schema(self):
        return self.__class__._tree_schema

    @property
    def ui_configuration(self):
        return {k: v for k, v in self._kwargs.items() if k in self.PROVIDE_KWARGS}

    @property
    def schema(self):
        return {
            'instrument_class': self.instrument_cls.__name__,
            'instrument_type': self.instrument_type,
            'fields': self.tree_schema,
            'configuration': self.ui_configuration,
            'data_schema': self.data_schema,
        }

    def attach_attr_hooks(self, path=None, tree=None):
        raise NotImplementedError()

    def serialize_state(self):
        return self.serialize_state_from_query('*')

    def serialize_state_from_query(self, query='*', path=None, tree=None):
        if path is None:
            path = []

        if tree is None:
            tree = self.tree_schema

        if is_leaf(tree):
            # get the value
            if not isinstance(tree, dict):
                return tree

            # method, skip
            if 'signature' in tree:
                raise TypeError('Cannot serialize a method.')

            # return the value of the property
            try:
                return reduce(lambda reduced, value: getattr(reduced, value), path, self.instrument)
            except Exception as e:
                return None

        if query == '*':
            query = {k: '*' for k in tree.keys()}

        if isinstance(query, dict):
            serialized = {}
            for k in tree.keys():
                if tree[k] is None:
                    continue
                try:
                    serialized[k] = self.serialize_state_from_query(query[k], path + [k], tree[k])
                except TypeError:
                    pass
            return serialized

        if not isinstance(query, str):
            raise ValueError('Bad query: {}'.format(query))
        if query not in tree:
            raise ValueError('Residual Query {} not found in {}'.format(query, tree.keys()))

        return self.serialize_state_from_query('*', path + [query], tree[query])


class FrontPanelBase(object):
    def __init__(self, instrument, experiment, name, **kwargs):
        assert (not hasattr(instrument, '_fp_lock'))
        setattr(instrument, '_fp_lock', True)
        self.instrument = instrument
        self.experiment = experiment
        self.name = name
        self._kwargs = kwargs

    def __delete__(self):
        delattr(self.instrument, '_fp_lock')

    async def run_front_panel(self):
        while True:
            await asyncio.sleep(3)

ALLOWABLE_BASES = {
    FrontPanelBase, FrontPanelCommon, Actor,
}

