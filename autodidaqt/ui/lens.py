from typing import Any, Callable

import operator

import rx.operators as ops
from rx.subject import BehaviorSubject, Subject

__all__ = (
    "LensSubject",
    "Lens",
)


class LensBase:
    """
    Exists primarily to define transforms between lenses.
    Subclasses must provide the "view" method which actually constructs
    the lens.
    """

    def id(self):
        return self.view(lambda value: value, lambda old, new: new)

    def view_index(self, item_index):
        def itemsetter(value, update):
            original_type = type(value)
            if isinstance(value, (list, tuple)):
                temporary = list(value)
                temporary[item_index] = update
                return original_type(temporary)
            else:
                value = original_type(value)
                value[item_index] = update
                return value

        return self.view(operator.itemgetter(item_index), itemsetter)

    def view_as_type(self, from_type, to_type):
        return self.view(to_type, lambda old, new: from_type(new))


class Lens(LensBase):
    """
    Lens provides a view into a LensSubject. This allows cutting data out
    of some piece of shared state, as well as writing into it, making
    it straightforward to share object properties across objects.

    The LensSubject provides a single source of truth for the state
    so that the lenses are independent. To prevent value-thrashing/circular
    dependencies, a LensSubject enforces equality sematics: setting the same value
    into the state as already exists does nothing.
    """

    internal_observable = None
    owner: Subject
    cuts: Callable
    inserts: Callable

    def __init__(self, owner: Subject, cuts: Callable, inserts: Callable):
        self.owner = owner
        self.cuts = cuts
        self.internal_observable = owner.pipe(ops.map(self.cuts))
        self.inserts = inserts

    @property
    def value(self):
        return self.cuts(self.owner.value)

    def pipe(self, *args, **kwargs):
        return self.internal_observable.pipe(*args, **kwargs)

    def on_next(self, value):
        full_value = self.inserts(self.owner.value, value)
        self.owner.on_next(full_value)

    def subscribe(self, *args, **kwargs):
        self.internal_observable.subscribe(*args, **kwargs)

    def view(self, cuts, inserts):
        """
        Creates a sub-lens. In order for this to work, we need to be able
        to maintain an owner which is itself a lens. It's for this reason
        (and for convenience), that Lens implements ".value" like
        rx.subject.BehaviorSubject does.
        """

        return Lens(self, cuts, inserts)


class LensSubject(BehaviorSubject, LensBase):
    """
    Much like a behavior subject, but suppresses identical values. LensSubject
    models a changing shared value with lens-like getters and setters.
    """

    def on_next(self, value: Any) -> None:
        if self.value == value:
            return

        super().on_next(value)

    def view(self, cuts, inserts):
        return Lens(self, cuts, inserts)
