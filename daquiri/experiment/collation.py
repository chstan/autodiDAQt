from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Union

import numpy as np
import xarray as xr

__all__ = ["Collation"]

@dataclass
class Collation:
    independent: Dict[Tuple[Union[str, int]], str] = None
    dependent: Dict[Tuple[Union[str, int]], str] = None

    # contains the min, max, and observed values
    statistics: Dict[str, Tuple[float, float, Set[float]]] = field(default_factory=dict)

    def receive(self, device, value):
        """
        Records statistics and observed values for the given axis, if it is independent
        Args:
            device: Path/ID of the virtual axis/device
            value: Received value
        """
        if device in self.independent:
            if device in self.statistics:
                minimum, maximum, seen = self.statistics[device]
            else:
                minimum, maximum, seen = np.inf, -np.inf, set()

            minimum, maximum = min(minimum, value), max(maximum, value)
            seen.add(value)
            self.statistics[device] = (minimum, maximum, seen)

    def internal_axes(self):
        coords = {}
        dims = []
        for full_path, name in self.independent.items():
            dims.append(name)
            coords[name] = np.asarray(sorted(list(self.statistics[full_path][2])))

        return coords, dims

    def template(self, peeked_values):
        common_coords, common_dims = self.internal_axes()
        base_shape = [len(common_coords[d]) for d in common_dims]

        built_empty_arrays = {}
        for k, peeked in peeked_values.items():
            current_dims = list(common_dims)
            current_coords = common_coords.copy()
            current_shape = list(base_shape)

            dtype = np.float64
            if isinstance(peeked, np.ndarray):
                dtype = peeked.dtype

                current_shape = current_shape + list(peeked.shape)
                for i, s in enumerate(peeked.shape):
                    current_dims.append(f"{k}-dim_{i}")
                    current_coords[f"{k}-dim_{i}"] = np.arange(s)

            if k in current_dims:
                k = f"{k}-values"
            built_empty_arrays[k] = xr.DataArray(
                np.zeros(shape=current_shape, dtype=dtype),
                coords=current_coords,
                dims=current_dims,
            )

        return xr.Dataset(built_empty_arrays)

    @classmethod
    def iter_single_group(cls, daq_stream, group_key="point"):
        group = 0
        collected = []
        for daq in daq_stream:
            current_group = daq[group_key]

            if current_group == group:
                collected.append(daq["data"])
            else:
                yield collected
                collected = [daq["data"]]
                group = current_group
        
        yield collected

    @classmethod
    def iter_grouped(cls, daq_values, group_key="point"):
        names = list(daq_values.keys())
        single_streams = [
            cls.iter_single_group(daq_values[n], group_key=group_key) for n in names
        ]

        for point in zip(*single_streams):
            point = [x[0] if len(x) == 1 else x for x in point]
            yield dict(zip(names, point))

    def to_xarray(self, daq_values, group_key="point"):
        all_names = self.independent.copy()
        all_names.update(self.dependent)
        independent_names = {n: f"{n}-values" for n in self.independent.values()}

        namespaced_daq_values = {all_names[k]: v for k, v in daq_values.items()}

        ds = None
        for point in Collation.iter_grouped(namespaced_daq_values, group_key):
            if ds is None:
                ds = self.template(point)

            iter_coords = {k: v for k, v in point.items() if k in independent_names}

            for k, value in point.items():
                kname = independent_names.get(k, k)
                index = [
                    np.searchsorted(ds.coords[d].values, iter_coords[d])
                    for d in ds[kname].dims
                    if d in iter_coords
                ]
                ds[kname].values[tuple(index)] = value

        return ds

