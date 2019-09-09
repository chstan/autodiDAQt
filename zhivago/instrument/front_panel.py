import asyncio
import copy
import functools
from functools import partialmethod
import inspect
from collections import namedtuple
from functools import reduce
import instruments

from instruments.util_fns import ProxyList

from zhivago.actor import Actor
from zhivago.utils import mock_print
from zhivago.instrument.utils import (
    serialize_signature, FrontPanelBase, FrontPanelCommon, ALLOWABLE_BASES,
    is_leaf, is_property, InstrumentTypes
)

__all__ = ('FrontPanel',)


def dict_widget(template, on_change=None):
    """
    Currently this only supports flat dictionaries.
    :param template:
    :return:
    """

    read_data = dict()

    for k, v in template.items():
        read_data[k] = v.value

        def on_change_handler(key, attr, old, new):
            old_config = copy.deepcopy(read_data)
            read_data[key] = new
            new_config = copy.deepcopy(read_data)
            if not on_change is None:
                on_change(attr, old_config, new_config)

        v.on_change('value', functools.partial(on_change_handler, k))

    return read_data


Field = namedtuple('Field', ['label', 'widget_type', 'js_type', 'role'])

SKIP_ROOTS = {'doc', 'driver', 'driver_operation'}


class SkipException(Exception):
    pass


def serializable(property_name, skipped=None):
    if skipped is None:
        skipped = SKIP_ROOTS

    return property_name[0] != '_' and property_name not in skipped


def is_proxy_list(tree):
    if isinstance(tree, dict) and 'item_class' in tree and 'item_schema' in tree:
        return True

    return False


def serialize_proxy_list(proxy_list, patch=None):
    assert (isinstance(proxy_list, ProxyList))
    proxy_cls = proxy_list._proxy_cls

    if isinstance(patch, set):
        # mark for setattr patching
        patch.add(proxy_cls)

    item_schema = {}
    for k in [p for p in dir(proxy_cls) if serializable(p)]:
        try:
            item_schema[k] = serialize(k, proxy_cls, proxy_cls, patch=patch)
        except SkipException:
            pass

    return {
        'item_class': proxy_cls.__name__,
        'item_schema': item_schema,
    }


def serialize_property(p, parent=None, name=None):
    return {
        'getter': serialize_method(p.fget or p.getter, parent),
        'setter': serialize_method(p.fset or p.setter, parent),
        #'doc': (p.__doc__ or '').strip(),
        'name': name,
    }


def serialize_method(method, parent=None):
    try:
        raw_signature = inspect.signature(method)
        signature = serialize_signature(raw_signature)
    except:
        signature = {
            'parameters': [],
        }
    return {
        #'doc': (method.__doc__ or '').strip(),
        'name': method.__name__,
        'signature': signature,
    }


def serialize_function(func, parent=None):
    return {
        #'doc': (func.__doc__ or '').strip(),
        'name': func.__name__,
        'signature': serialize_signature(inspect.signature(func))
    }


def serialize(p, parent=None, parent_cls=None, patch=None):
    attr = p
    if isinstance(attr, str):
        if attr.upper() == attr:
            raise SkipException()

        try:
            attr = getattr(parent_cls, p)
        except AttributeError:
            pass

        if parent is not None:
            test_attr = getattr(parent, p)
            if isinstance(test_attr, ProxyList):
                attr = test_attr

    if isinstance(attr, ProxyList):
        return serialize_proxy_list(attr, patch=patch)

    if isinstance(attr, property):
        return serialize_property(attr, parent, p)

    if inspect.ismethod(attr):
        return serialize_method(attr, parent)

    if inspect.isfunction(attr):
        return serialize_function(attr, parent)

    raise SkipException()


class FrontPanelMeta(type):
    """
    representation of a physical instrument. This Metaclass
    enforces some constraints about subclasses, such as specifying the class of
    the instrument driver.

    It also attempts to inspect the instrument driver in order to determine the rough
    characteristics of the driver's front panel.

    This is slightly different than IVIFrontPanelMeta, but they perform more or less the same
    function.
    """
    instrument_cls = None

    def __init__(cls, name, bases, namespace, **kwargs):
        if not all(b in ALLOWABLE_BASES for b in bases):
            _ = getattr(cls, 'instrument_cls')

    def __new__(cls, name, bases, namespace, **kwargs):
        instrument_cls = namespace.get('instrument_cls')
        is_abstract_subclass = all(b in ALLOWABLE_BASES for b in bases)

        # need to patch some __setattr__'s in order to ensure that we have reactivity to changes in instrument state
        patch_classes = {instrument_cls,}

        if not is_abstract_subclass:
            temp_item = instrument_cls.open_test()

            schema = {}
            for p in dir(temp_item):
                if serializable(p):
                    try:
                        schema[p] = serialize(p, temp_item, instrument_cls, patch=patch_classes)
                    except SkipException:
                        pass

            instrument_mod_name = inspect.getmodule(instrument_cls).__name__
            base_mod_name = instrument_mod_name.split('.')[0]

            namespace['_tree_schema'] = schema
            namespace['_instrument_module_name'] = base_mod_name
            namespace['_instrument_module'] = instrument_mod_name

        for patch_cls in patch_classes:
            if patch_cls is None:
                continue
            try:
                PatchableSetattr(patch_cls)
            except SetattrAlreadyPatchedException:
                pass

        return super().__new__(cls, name, bases, namespace)


class SetattrAlreadyPatchedException(Exception):
    pass


class PatchableSetattr(object):
    def __init__(self, cls_to_patch):
        try:
            if getattr(cls_to_patch, '_patched'):
                raise SetattrAlreadyPatchedException()
        except AttributeError:
            pass

        cls_to_patch._patched = True
        self._cls = cls_to_patch
        self._real__setattr__ = self._cls.__setattr__
        self._cls.__setattr__ = partialmethod(self.do_setattr)

    def do_setattr(self, *args, **kwargs):
        # Currently we aren't going to do anything here except to defer to the original setattr
        # in the future we need to track changes, there are difficulties though with ProxyLists,
        # because we want to be able to let the owning instrument panel know of changes, but
        # the ways in which ProxyList items know their index gets messy.
        self._real__setattr__(*args, **kwargs)


class FrontPanel(Actor, FrontPanelBase, FrontPanelCommon, metaclass=FrontPanelMeta):
    PROVIDE_KWARGS = {
        'locations',
        'trajectories',
    }

    def __init__(self, instrument, experiment, name, **kwargs):
        super().__init__(instrument, experiment, name, **kwargs)
        self.attach_attr_hooks()

    async def run(self):
        while True:
            asyncio.sleep(1)

    def setattr_hook(self, path, oldattr, newattr):
        payload = {}
        payload[self.name] = reduce(lambda value, key: dict([[key, value]]), path[::-1], newattr)
        self.experiment.forwarding_queue.put_nowait({
            'type': 'RECEIVE_INSTRUMENT_STATE',
            'payload': payload,
        })

    @mock_print
    def call_method(self, path, **kwargs):
        raise NotImplementedError('')

    @mock_print
    def set_property(self, path, value):
        raise NotImplementedError('')

    def serialize_state_from_query(self, query='*', path=None, tree=None):
        """
        We are overriding this temporarily because we don't have access to anything
        other than test instruments at the moment.
        :param query:
        :param path:
        :param tree:
        :return:
        """

        if path is None:
            path = []

        if tree is None:
            tree = self.tree_schema

        if is_proxy_list(tree):
            return None

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


    def attach_attr_hooks(self, path=None, tree=None):
        return None

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
                import pdb
                pdb.set_trace()
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
        MOTION_CONTROLLERS = {
            instruments.newport.newportesp301.NewportESP301,
        }
        TEMPERATURE_CONTROLLERS = {}
        LOCKIN_AMPLIFIERS = {}

        if issubclass(self.instrument_cls, instruments.abstract_instruments.Multimeter):
            return int(InstrumentTypes.DMM)
        if issubclass(self.instrument_cls, instruments.abstract_instruments.Oscilloscope):
            return int(InstrumentTypes.OSCILLOSCOPE)
        if issubclass(self.instrument_cls, instruments.abstract_instruments.FunctionGenerator):
            return int(InstrumentTypes.FUNCTION_GENERATOR)

        if any(issubclass(self.instrument_cls, ins) for ins in MOTION_CONTROLLERS):
            return int(InstrumentTypes.MOTION_CONTROLLER)
        # if issubclass(self.instrument_cls, piezo_controller.Base):
        #    return int(InstrumentTypes.PIEZO_CONTROLLER)
        if any(issubclass(self.instrument_cls, ins) for ins in TEMPERATURE_CONTROLLERS):
            return int(InstrumentTypes.TEMPERATURE_CONTROLLER)
        if any(issubclass(self.instrument_cls, ins) for ins in LOCKIN_AMPLIFIERS):
            return int(InstrumentTypes.LOCKIN_AMPLIFIER)

        return None

