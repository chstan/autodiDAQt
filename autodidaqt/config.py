import datetime
import json
import sys
from pathlib import Path

from autodidaqt.utils import autodidaqt_LIB_ROOT

from .collections import AttrDict, deep_update

__all__ = ("Config", "MetaData", "default_config_for_platform")


def default_config_for_platform() -> Path:
    configs = {
        "win32": "default_config_windows.json",
    }
    cfile = configs.get(sys.platform, "default_config.json")

    return autodidaqt_LIB_ROOT / "resources" / cfile


class Config:
    def __init__(self, path, defaults=None):
        if defaults:
            with open(str(path)) as f:
                self._cached_settings = json.load(f)
        else:
            self._cached_settings = {}

        with open(str(path)) as f:
            deep_update(json.load(f), self._cached_settings)

    def __getattr__(self, item):
        ret = self._cached_settings[item]
        return AttrDict(ret) if isinstance(ret, dict) else ret

    def __repr__(self):
        return repr(self._cached_settings)

    def __str__(self):
        return str(self._cached_settings)


class MetaData:
    """
    Some __getattr__ foo here. Note that because we define __getattr__
    and __setattr__ we need to reference `_internal` using __dict__ in
    the __init__, otherwise the Python data model forces an invokation to
    __getattr__ before we have actually set the attribute and
    a KeyError results.
    """

    def __init__(self):
        date_started = datetime.date.today()
        datetime_started = datetime.datetime.today()
        time_started = datetime_started.time()

        self.__dict__["_internal"] = {
            "date": lambda: MetaData.safe_time_string(datetime.date.today().isoformat()),
            "time": lambda: MetaData.safe_time_string(datetime.datetime.now().time().isoformat()),
            "datetime": lambda: MetaData.safe_time_string(datetime.datetime.now().isoformat()),
            "date_started": lambda: MetaData.safe_time_string(date_started.isoformat()),
            "time_started": lambda: MetaData.safe_time_string(time_started.isoformat()),
            "datetime_started": lambda: MetaData.safe_time_string(datetime_started.isoformat()),
        }

    @staticmethod
    def safe_time_string(time_str):
        return time_str.replace(":", "-").replace(".", "-")

    def __getattr__(self, item):
        if item in self.__dict__["_internal"]:
            v = self.__dict__["_internal"][item]
            try:
                return v()
            except TypeError:
                return v

        return super().__getattr__(item)

    def __setattr__(self, key, value):
        protected = {
            "datetime",
            "date",
            "time",
            "datetime_started",
            "date_started",
            "time_started",
        }
        self._internal[key] = value
