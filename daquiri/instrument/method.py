import inspect
from typing import Any, Dict, Tuple, Union

from daquiri.schema import DEFAULT_VALUES
from daquiri.utils import safe_lookup

__all__ = (
    "Method",
    "TestMethod",
)


class Method:
    driver: Any
    where: Tuple[Union[str, int]]
    name: str

    last_kwargs: Dict[str, Any]
    value: Any = None

    def __init__(self, name, where, driver, return_annotation=None, parameters=None):
        self.driver = driver
        self.where = where
        self.name = name
        self.parameters = parameters
        self.return_annotation = return_annotation

        self.driver_method = self.find_method()
        self.signature = inspect.signature(self.driver_method)
        self.last_kwargs = {}

        if parameters:
            params = dict(self.signature.parameters.items())
            params.update(parameters)
            self.signature = self.signature.replace(parameters=params)
        if return_annotation:
            self.signature = self.signature.replace(return_annotation=return_annotation)

        for parameter in self.signature.parameters.values():
            if not parameter.default == self.signature.empty:
                self.last_kwargs[parameter.name] = parameter.default
            else:
                self.last_kwargs[parameter.name] = DEFAULT_VALUES.get(parameter.annotation)

    def find_method(self):
        return safe_lookup(self.driver, self.where)

    def call(self, *args, **kwargs):
        self.last_kwargs = self.signature.bind(*args, **kwargs).arguments

        self.value = self.driver_method(*args, **kwargs)
        return self.value


class TestMethod(Method):
    def find_method(self):
        def mocked(x: float, y: int, z: str) -> float:
            return 5

        return mocked

    def call(self, *args, **kwargs):
        print(f"Calling {self.name}: args={args}, kwargs={kwargs}")
        super().call(*args, **kwargs)
