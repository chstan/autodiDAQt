from typing import Any, Dict, Tuple, Union

from daquiri.utils import safe_lookup

__all__ = (
    "Property",
    "ChoiceProperty",
    "TestProperty",
)


class Property:
    driver: Any
    where: Tuple[Union[str, int]]
    name: str

    value: Any = None

    def __init__(self, name, where, driver):
        self.driver = driver
        self.where = where
        self.name = name

    def set(self, value):
        raise NotImplementedError

    def get(self):
        raise NotImplementedError


class SimpleProperty(Property):
    def __init__(self, name, where, driver):
        super().__init__(name, where, driver)

        self._bound_driver = safe_lookup(driver, where[:-1])

    def set(self, value):
        self.value = value
        setattr(self._bound_driver, self.where[-1], value)

    def get(self):
        return getattr(self._bound_driver, self.where[-1])


class ChoiceProperty(Property):
    choices = Dict[str, Any]
    labels = Dict[str, str]

    def __init__(self, name, where, driver, choices, labels):
        self.choices = choices
        self.labels = labels
        super().__init__(name, where, driver)

        self._bound_driver = safe_lookup(driver, where[:-1])

        def bound_get():
            return getattr(self._bound_driver, where[-1])

        def bound_set(value):
            setattr(self._bound_driver, where[-1], value)

        self._bound_get = bound_get
        self._bound_set = bound_set

    def get(self):
        return self._bound_get()

    def set(self, value):
        self.value = value
        self._bound_set(value)


class TestProperty(Property):
    value = None

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
