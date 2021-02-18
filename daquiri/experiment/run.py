import datetime
import functools
import operator
import pickle
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Type, Union

import numpy as np

import xarray as xr

from .save import RunSaver, SaveContext, save_cls_from_short_name

__all__ = ["Run"]

SaveFormat = Union[str, Type[RunSaver]]


def daq_to_timesequence_xarray(stream_name: str, data_stream) -> xr.Dataset:
    """
    Data streams are always lists of dictionaries with a
    point, a step number, and the acquisition time. Here we

    Args:
        stream_name:
        data_stream:

    Returns:
        xr.Dataset: All accumulated data as an xr.Dataset
        with dims and appropriate coords for the DAQ session.
    """
    step, points, data, time = [
        [p[name] for p in data_stream] for name in ["step", "point", "data", "time"]
    ]
    time = np.vectorize(np.datetime64)(np.asarray(time))
    time_dim = f"{stream_name}-time"

    peeked = data[0]

    # if the data consists of numpy arrays and they are the same shape, then we can
    # create dimensions and axes for them. It would probably be better to specify this
    # more directly. A few possible mechanisms exist:
    #   - Allow data schemas to specify how they collate data/multiple observations
    #   - Look at the schema value and special case ArrayType from ObjectType
    if isinstance(peeked, np.ndarray) and functools.reduce(
        operator.eq, [arr.shape for arr in data]
    ):
        data = np.stack(data, axis=-1)
        data_coords = {f"dim_{i}": np.arange(s) for i, s in enumerate(peeked.shape)}
        data_coords[time_dim] = time
        data_dims = [f"dim_{i}" for i in range(len(peeked.shape))] + [time_dim]
    else:
        data = np.asarray(data)
        data_coords = {f"{stream_name}-time": time}
        data_dims = [time_dim]

    time_coords = {f"{stream_name}-time": time}
    ds = xr.Dataset(
        {
            f"{stream_name}-step": xr.DataArray(
                np.asarray(step), coords=time_coords, dims=[time_dim]
            ),
            f"{stream_name}-point": xr.DataArray(
                np.asarray(points), coords=time_coords, dims=[time_dim]
            ),
            f"{stream_name}-data": xr.DataArray(data, coords=data_coords, dims=data_dims),
        }
    )
    return ds


@dataclass
class Run:
    # Configuration/Bookkeeping
    number: int  # the current run number
    session: str
    user: str

    config: Any
    sequence: Any

    step: int = 0
    point: int = 0
    is_inverted: bool = True

    # UI Configuration
    additional_plots: List[Dict] = field(default_factory=list)

    # DAQ
    metadata: List[Dict[str, Any]] = field(default_factory=list)
    steps_taken: List[Dict[str, Any]] = field(default_factory=list)
    point_started: List[Dict[str, Any]] = field(default_factory=list)
    point_ended: List[Dict[str, Any]] = field(default_factory=list)
    daq_values: Dict[str, Any] = field(default_factory=lambda: defaultdict(list))

    # used for updating UI, represents the accumulated "flat" value
    # or the most recent value for
    streaming_daq_xs: Dict[str, Any] = field(default_factory=lambda: defaultdict(list))
    streaming_daq_ys: Dict[str, Any] = field(default_factory=lambda: defaultdict(list))

    def finalize(self):
        self.config = None
        self.sequence = None

    def save_directory(self, app):
        directory = Path(
            str(app.app_root / app.config.data_directory / app.config.data_format).format(
                user=self.user,
                session=self.session,
                run=self.number,
                time=datetime.datetime.now().time().isoformat().split(".")[0].replace(":", "-"),
                date=datetime.date.today().isoformat(),
            )
        )

        if directory.exists():
            warnings.warn("Save directory already exists. Postfixing with the current time.")
            directory = (
                str(directory)
                + "_"
                + datetime.datetime.now().time().isoformat().replace(".", "-").replace(":", "-")
            )
            directory = Path(directory)

        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def save(
        self,
        save_directory: Path,
        extra=None,
        extra_attrs=None,
        save_format=Union[SaveFormat, List[SaveFormat]],
    ):
        # first, normalize all the formats to the respective classes
        if not isinstance(save_format, (list, tuple)):
            save_format = [save_format]

        save_format = [
            save_cls_from_short_name(format) if isinstance(format, str) else format
            for format in save_format
        ]

        # prep metadata and data for save
        all_metadata = {
            "metadata": self.metadata,
            "point_started": self.point_started,
            "point_ended": self.point_ended,
            "steps_taken": self.steps_taken,
        }
        daq = xr.merge(
            [
                daq_to_timesequence_xarray("-".join(map(str, ks)), v)
                for ks, v in self.daq_values.items()
            ]
        )
        daq = daq.assign_attrs({} if extra_attrs is None else extra_attrs)

        # for each specified format, save the data
        format: Type[RunSaver]
        for format in save_format:
            save_context = SaveContext(save_directory / format.short_name)
            format.save_run(all_metadata, daq, save_context)
            format.save_user_extras(extra or {}, save_context)
