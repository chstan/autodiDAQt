import datetime
import functools
import json
import operator
import pickle
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import xarray as xr
from daquiri.utils import RichEncoder

__all__ = ["Run"]

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
            str(
                app.app_root / app.config.data_directory / app.config.data_format
            ).format(
                user=self.user,
                session=self.session,
                run=self.number,
                time=datetime.datetime.now()
                .time()
                .isoformat()
                .split(".")[0]
                .replace(":", "-"),
                date=datetime.date.today().isoformat(),
            )
        )

        if directory.exists():
            warnings.warn(
                "Save directory already exists. Postfixing with the current time."
            )
            directory = (
                str(directory)
                + "_"
                + datetime.datetime.now()
                .time()
                .isoformat()
                .replace(".", "-")
                .replace(":", "-")
            )
            directory = Path(directory)

        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def save(self, save_directory: Path, extra=None, extra_attrs=None, save_format="zarr"):
        if extra is None:
            extra = {}

        if extra_attrs is None:
            extra_attrs = {}

        with open(str(save_directory / "metadata-small.json"), "w+") as f:
            json.dump({"metadata": self.metadata,}, f, cls=RichEncoder, indent=2)

        with open(str(save_directory / "metadata.json"), "w+") as f:
            json.dump(
                {
                    "metadata": self.metadata,
                    "point_started": self.point_started,
                    "point_ended": self.point_ended,
                    "steps_taken": self.steps_taken,
                },
                f,
                cls=RichEncoder,
                indent=2,
            )

        def daq_to_xarray(stream_name, data_stream) -> xr.Dataset:
            """
            Data streams are always lists of dictionaries with a
            point, a step number, and the acquisition time. Here we

            Args:
                data_stream:

            Returns:
                xr.Dataset: All accumulated data as an xr.Dataset
                with dims and appropriate coords for the DAQ session.
            """
            step, points, data, time = [
                [p[name] for p in data_stream]
                for name in ["step", "point", "data", "time"]
            ]
            time = np.vectorize(np.datetime64)(np.asarray(time))
            time_dim = f"{stream_name}-time"

            peeked = data[0]
            
            # if the data consists of numpy arrays and they are the same shape, then we can
            # create dimensions and axes for them. It would probably be better to specify this
            # more directly. A few possible mechanisms exist:
            #   - Allow data schemas to specify how they collate data/multiple observations
            #   - Look at the schema value and special case ArrayType from ObjectType
            if isinstance(peeked, np.ndarray) and functools.reduce(operator.eq, [arr.shape for arr in data]):
                data = np.stack(data, axis=-1)
                data_coords = {
                    f"dim_{i}": np.arange(s) for i, s in enumerate(peeked.shape)
                }
                data_coords[time_dim] = time
                data_dims = [f"dim_{i}" for i in range(len(peeked.shape))] + [time_dim]
            else:
                data = np.asarray(data)
                data_coords = {f"{stream_name}-time": time}
                data_dims = [time_dim]

            ds = xr.Dataset(
                {
                    f"{stream_name}-step": xr.DataArray(
                        np.asarray(step),
                        coords={f"{stream_name}-time": time},
                        dims=[time_dim],
                    ),
                    f"{stream_name}-point": xr.DataArray(
                        np.asarray(points),
                        coords={f"{stream_name}-time": time},
                        dims=[time_dim],
                    ),
                    f"{stream_name}-data": xr.DataArray(
                        data, coords=data_coords, dims=data_dims,
                    ),
                }
            )
            return ds

        daq = xr.merge(
            [
                daq_to_xarray("-".join(str(k) for k in ks), v)
                for ks, v in self.daq_values.items()
            ]
        )
        daq = daq.assign_attrs(extra_attrs)

        if save_format == "zarr":
            daq.to_zarr(save_directory / "raw_daq.zarr")

            for k, v in extra.items():
                if v is None:
                    continue

                v.to_zarr(save_directory / f"{k}.zarr")
        elif save_format == "pickle":
            with open(str(save_directory / "raw_daq.pickle"), "wb+") as fpickle:
                pickle.dump(daq, fpickle, protocol=-1)
            
            for k, v in extra.items():
                if v is None:
                    continue

                with open(str(save_directory / f"{k}.pickle"), "wb+") as fpickle:
                    pickle.dump(v, fpickle, protocol=-1)

