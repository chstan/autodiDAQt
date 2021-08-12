"""
This module provides the ability to instrument values inside the 
system so that the value during the execution can be recorded
into the collected data. 

Generally speaking, this is a healthy thing to do because it allows
the scientist to introspect why an experiment acted the way it did
post facto.

The core API exposed here is on the singleton `registrar`:

1. `registrar.metadata` - A decorator which collects and publishes the value in the registrar
2. `registrar.collect_metadata` - Get the collected data

Internally, values are stored in a buffer per source and the buffer is cleared
each time the data is collected.
"""

from typing import Any, Dict, List

from dataclasses import dataclass, field
from functools import wraps

__all__ = ["registrar"]


@dataclass
class Registrar:
    metadata_sources: Dict[str, Any] = field(default_factory=dict)

    def collect_metadata(self) -> Dict[str, Any]:
        return {k: v.collect() for k, v in self.metadata_sources.items()}

    def register_source(self, source_name, source):
        if source_name in self.metadata_sources:
            raise ValueError(f"{source_name} is already registered as a metadata source.")

        self.metadata_sources[source_name] = source

    def metadata(self, attr_name: str, clear_buffer_on_collect=True):
        buffer = []

        def decorates(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                value = fn(*args, **kwargs)
                buffer.append(value)
                return value

            def collect() -> List[Any]:
                collected = list(buffer)

                if clear_buffer_on_collect:
                    buffer.clear()

                return collected

            wrapper.collect = collect
            self.register_source(attr_name, wrapper)

            return wrapper

        return decorates


registrar = Registrar()
