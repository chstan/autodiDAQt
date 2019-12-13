from typing import Any, Union, Tuple, Dict

__all__ = ('Property', 'ChoiceProperty', 'TestProperty',)


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
        raise NotImplementedError()

    def get(self):
        raise NotImplementedError()


class ChoiceProperty(Property):
    choices = Dict[str, Any]
    labels = Dict[str, str]

    def __init__(self, name, where, driver, choices, labels):
        self.choices = choices
        self.labels = labels
        super().__init__(name, where, driver)

        self._bound_write = None
        self._bound_read = None

    def get(self):
        print('get', self.name, self.driver)
        return self.value

    def set(self, value):
        self.value = value
        print('set', value, self.name, self.driver)


class TestProperty(Property):
    value = None

    def get(self):
        return self.value

    def set(self, value):
        self.value = value