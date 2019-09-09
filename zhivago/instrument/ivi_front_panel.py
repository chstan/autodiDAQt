import ivi
import asyncio
import random
import datetime
import inspect

from functools import reduce

from zhivago.actor import Actor
from zhivago.instrument.utils import (
    serialize_signature, InstrumentTypes, FrontPanelBase,
    ALLOWABLE_BASES, FrontPanelCommon, is_leaf, is_property
)


__all__ = ('IVIFrontPanel',)

SKIP_IVI_ITEMS = {
    'lock_object',
    'unlock_object',
    'reset_with_defaults',
}

def serialize_param(param: inspect.Parameter):
    sparam = {
        'name': param.name,
    }

    if param.default != param.empty:
        sparam['default'] = param.default

    return sparam


def serialize_method(method, method_name, nearest_property_collection=None):
    doc = method.__doc__
    try:
        doc = nearest_property_collection._doc[method_name]
    except:
        pass

    return {
        'doc': doc,
        'name': method_name,
        'signature': serialize_signature(inspect.signature(method))
    }


def serialize_property(item, name, nearest_property_collection=None):
    return {
        'getter': serialize_method(item[0], item[0].__name__,
                                   nearest_property_collection),
        'setter': serialize_method(item[1], item[1].__name__,
                                   nearest_property_collection),
        'name': name,
    }


def serialize_generic(item, name, nearest_property_collection=None):
    if inspect.ismethod(item):
        return serialize_method(item, name, nearest_property_collection)

    if isinstance(item, ivi.ivi.PropertyCollection):
        return serialize_property_collection(item)

    if isinstance(item, tuple) and len(item) == 3 and callable(item[0]) and callable(item[1]):
        return serialize_property(item, name, nearest_property_collection)

    return None


def resolve(coll, k):
    try:
        return coll._props[k]
    except:
        return getattr(coll, k, None)


def serialize_property_collection(prop_collection):
    items = [p for p in dir(prop_collection) if p[0] != '_' and p not in SKIP_IVI_ITEMS]
    built = {k: serialize_generic(resolve(prop_collection, k), k, prop_collection) for k in items}
    return {k: v for k, v in built.items() if v is not None}


class IVIFrontPanelMeta(type):
    def __init__(cls, name, bases, namespace, **kwargs):
        if not all(b in ALLOWABLE_BASES for b in bases):
            _ = getattr(cls, 'instrument_cls')

    def __new__(cls, name, bases, namespace, **kwargs):
        instrument_cls = namespace.get('instrument_cls')
        is_abstract_subclass = all(b in ALLOWABLE_BASES for b in bases)

        if not is_abstract_subclass:
            temp_item = instrument_cls(simulate=True)
            SKIP_ROOTS = ['doc', 'driver_operation', 'close', 'help', 'initialize', 'initialized']
            roots = [p for p in dir(temp_item) if p[0] != '_' and p not in SKIP_ROOTS]
            schema = {p: serialize_generic(resolve(temp_item, p), p, temp_item)
                      for p in roots}

            setattr(cls, '_tree_schema', schema)

            instrument_mod_name = inspect.getmodule(instrument_cls).__name__
            base_mod_name = instrument_mod_name.split('.')[0]

            namespace['_tree_schema'] = schema
            namespace['_instrument_module_name'] = base_mod_name
            namespace['_instrument_module'] = instrument_mod_name

        return super().__new__(cls, name, bases, namespace)


class IVIFrontPanel(Actor, FrontPanelBase, FrontPanelCommon, metaclass=IVIFrontPanelMeta):
    """
    Implementing a front panel amounts to implementing the methods

    1. serialize_state_from_query
    2. schema
    3. call_method
    4. set_property
    """

    PROVIDE_KWARGS = {
        'locations',
        'trajectories'
    }

    def __init__(self, instrument, experiment, name, **kwargs):
        super().__init__(instrument, experiment, name, **kwargs)
        self.attach_attr_hooks()

    async def run(self):
        test_instrument_types = [InstrumentTypes.DMM, InstrumentTypes.TEMPERATURE_CONTROLLER]
        if self.instrument_type in test_instrument_types:
            while True:
                timer = asyncio.sleep(1)
                payload = {}
                payload[self.name] = {
                    'time': datetime.datetime.now().isoformat(),
                    'values': {
                        'ch1': random.random(),
                        'ch2': 3 * random.random() + 2,
                        'ch3': 4 * random.random(),
                        'ch4': 2 * random.random() - 1,
                    }
                }

                self.experiment.forwarding_queue.put_nowait({
                    'type': 'RECEIVE_INSTRUMENT_DELTA',
                    'payload': payload,
                })

                await timer
        else:
            super().run_front_panel()


    def setattr_hook(self, path, oldattr, newattr):
        payload = {}
        payload[self.name] = reduce(lambda value, key: dict([[key, value]]), path[::-1], newattr)
        self.experiment.forwarding_queue.put_nowait({
            'type': 'RECEIVE_INSTRUMENT_STATE',
            'payload': payload,
        })

    def attach_attr_hooks(self, path=None, tree=None):
        if path is None:
            path = []
        if tree is None:
            if len(path) == 0:
                tree = self.tree_schema
            else:
                return

        if is_leaf(tree):
            if is_property(tree):
                last = path[-1]
                rest = path[:-1]
                property_set = reduce(lambda reduced, key: getattr(reduced, key), rest, self.instrument)

                # monkeypatch __setattr__
                if path[-1] in property_set._props:
                    old_setattr = property_set._props[last][1]

                    try:
                        if old_setattr.patched:
                            return
                    except:
                        # we haven't patched this method
                        pass

                    def new_setattr(value, *args, **kwargs):
                        self.setattr_hook(path, getattr(property_set, last), value)
                        old_setattr(value, *args, **kwargs)

                    new_setattr.patched = True
                    property_set._props[last] = (
                        property_set._props[last][0],
                        new_setattr,
                        property_set._props[last][2],
                    )

        else:
            for k in tree.keys():
                self.attach_attr_hooks(path + [k], tree[k])

    def call_method(self, path, **kwargs):
        description = reduce(lambda reduced, key: reduced[key], path, self.tree_schema)
        method = reduce(lambda reduced, key: getattr(reduced, key), path, self.instrument)

        # method is bound, so it shouldn't need a self argument
        args = [kwargs.get(k[0], None) for k in description['signature']['parameters']]
        method(*args)

    def set_property(self, path, value):
        p = reduce(lambda reduced, key: getattr(reduced, key), path[:-1], self.instrument)
        setattr(p, path[-1], value)

    @property
    def instrument_type(self):
        from ivi import (dmm, fgen, scope,
                         #motion_controller,
                         #temperature_controller,
                         #lockin_amplifier
                         )  # piezo_controller

        if issubclass(self.instrument_cls, dmm.Base):
            return int(InstrumentTypes.DMM)
        if issubclass(self.instrument_cls, scope.Base):
            return int(InstrumentTypes.OSCILLOSCOPE)
        if issubclass(self.instrument_cls, fgen.Base):
            return int(InstrumentTypes.FUNCTION_GENERATOR)
        #if issubclass(self.instrument_cls, motion_controller.Base):
        #    return int(InstrumentTypes.MOTION_CONTROLLER)
        # if issubclass(self.instrument_cls, piezo_controller.Base):
        #    return int(InstrumentTypes.PIEZO_CONTROLLER)
        #if issubclass(self.instrument_cls, temperature_controller.Base):
        #    return int(InstrumentTypes.TEMPERATURE_CONTROLLER)
        #if issubclass(self.instrument_cls, lockin_amplifier.Base):
        #    return int(InstrumentTypes.LOCKIN_AMPLIFIER)

        return None

