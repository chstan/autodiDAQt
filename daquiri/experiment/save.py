import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from daquiri.utils import RichEncoder

__all__ = [
    "save_cls_from_short_name",
    "SaveContext",

    "RunSaver",
    "ZarrSaver",
    "PickleSaver",
    "ForgetfulSaver",
]

@dataclass
class SaveContext:
    save_directory: Path

class RunSaver:
    """
    Encapsulates logic around saving the result of a run.
    This was previously handled entirely by run itself, 
    but now that we support different save mechanisms this makes 
    sense to split out. Additionally, by having this split,
    it becomes straightforward for us to support multiple
    mechanisms for saving data, and more straightforward eventually
    to stream data when we are working with larger datasets.
    """

    short_name: str = None
    
    @classmethod
    def save_run(cls, metadata, data, context: SaveContext):
        raise NotImplementedError

    @staticmethod
    def save_pickle(path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "wb+") as f:
            pickle.dump(data, f, protocol=-1)

    @staticmethod
    def save_json(path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "w+") as f:
            json.dump(data, f, cls=RichEncoder, indent=2)

    @staticmethod
    def save_metadata(path: Path, metadata: Dict[str, Any]):
        RunSaver.save_json(path / "metadata-small.json", {k: v for k, v in metadata.items() if k == "metadata"})
        RunSaver.save_json(path / "metadata.json", metadata)

    @staticmethod
    def save_user_extras(extra_data, context: SaveContext):
        raise NotImplementedError


class ZarrSaver(RunSaver):
    short_name = "zarr"

    @staticmethod
    def save_user_extras(extra_data, context: SaveContext):
        for k, v in extra_data.items():
            if v is None:
                continue

            v.to_zarr(context.save_directory / f"{k}.zarr")

    @staticmethod
    def save_run(metadata, data, context: SaveContext):
        ZarrSaver.save_metadata(context.save_directory, metadata)

        data.to_zarr(context.save_directory / "raw_daq.zarr")


class PickleSaver(RunSaver):
    short_name = "pickle"

    @staticmethod
    def save_user_extras(extra_data, context: SaveContext):
        for k, v in extra_data.items():
            if v is None:
                continue
            
            PickleSaver.save_pickle(context.save_directory / f"{k.pickle}", v)
        
    @staticmethod
    def save_run(metadata, data, context: SaveContext):
        PickleSaver.save_metadata(context.save_directory, metadata)
        PickleSaver.save_pickle(context.save_directory / "raw_daq.pickle", data)
        
class ForgetfulSaver(RunSaver):
    """
    This one doesn't do anything. This is useful if you are just
    trying to test something and don't actually want to produce data.
    """
    short_name = "forget"

    @staticmethod
    def save_run(metadata, data, context: SaveContext):
        return

    @staticmethod
    def save_user_extras(extras, context: SaveContext):
        return

_by_short_names = {cls.short_name: cls for cls in [
    ZarrSaver, PickleSaver, ForgetfulSaver
]}
save_cls_from_short_name = _by_short_names.get