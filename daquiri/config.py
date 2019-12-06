import datetime
import json

from .collections import AttrDict

__all__ = ('Config', 'MetaData',)


class Config:
    def __init__(self, path):
        with open(str(path)) as f:
            self._cached_settings = json.load(f)

    def __getattr__(self, item):
        ret = self._cached_settings[item]
        return AttrDict(ret) if isinstance(ret, dict) else ret


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

        self.__dict__['_internal'] = {
            'date': lambda: MetaData.safe_time_string(
                datetime.date.today().isoformat()),
            'time': lambda: MetaData.safe_time_string(
                datetime.datetime.now().time().isoformat()),
            'datetime': lambda: MetaData.safe_time_string(
                datetime.datetime.now().isoformat()),
            'date_started': lambda: MetaData.safe_time_string(
                date_started.isoformat()),
            'time_started': lambda: MetaData.safe_time_string(
                time_started.isoformat()),
            'datetime_started': lambda: MetaData.safe_time_string(
                datetime_started.isoformat()),
        }

    @staticmethod
    def safe_time_string(time_str):
        return time_str.replace(':', '-').replace('.', '-')

    def __getattr__(self, item):
        if item in self.__dict__['_internal']:
            v = self.__dict__['_internal'][item]
            try:
                return v()
            except TypeError:
                return v

        return super().__getattr__(item)

    def __setattr__(self, key, value):
        protected = {
            'datetime', 'date', 'time',
            'datetime_started', 'date_started', 'time_started',
        }
        self._internal[key] = value


