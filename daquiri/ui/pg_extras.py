import pyqtgraph as pg
import math
import numpy as np
from rx.subject import BehaviorSubject, Subject
from scipy import interpolate
from daquiri.utils import temporary_attrs

__all__ = ("CursorRegion", "ArrayImageView", "ArrayPlot",)


class CoordAxis(pg.AxisItem):
    def __init__(self, dim_index, *args, **kwargs):
        self.dim_index = dim_index
        self.coord = None
        self.interp = None
        super().__init__(*args, **kwargs)

    def set_ndarray(self, arr):
        # set the coordinate
        axis_len = arr.shape[self.dim_index]
        if not isinstance(self.coord, np.ndarray) or self.coord[0] != 0 or self.coord[-1] != axis_len - 1:
            self.coord = np.linspace(0, axis_len - 1, axis_len, dtype=int)
            self.interp = interpolate.interp1d(np.arange(0, len(self.coord)), self.coord, fill_value="extrapolate")

    def set_dataarray(self, image):
        self.coord = image.coords[image.dims[self.dim_index]].values
        self.interp = interpolate.interp1d(np.arange(0, len(self.coord)), self.coord, fill_value='extrapolate')

    def setImage(self, image):
        if isinstance(image, np.ndarray):
            self.set_ndarray(image)
        else:
            self.set_dataarray(image)

    def tickStrings(self, values, scale, spacing):
        try:
            return ['{:.3f}'.format(f) for f in self.interp(values)]
        except TypeError:
            return super().tickStrings(values, scale, spacing)


class ArrayPlot(pg.PlotWidget):
    def __init__(self, orientation, *args, **kwargs):
        self.orientation = orientation

        axis_or = 'bottom' if orientation == 'horiz' else 'left'
        self._coord_axis = CoordAxis(dim_index=0, orientation=axis_or)

        super().__init__(axisItems=dict([[axis_or, self._coord_axis]]), *args, **kwargs)

    def plot(self, data, *args, **kwargs):
        self._coord_axis.setImage(data)

        if self.orientation == 'horiz':
            self.plotItem.plot(np.arange(0, len(data)), data, *args, **kwargs)
        else:
            self.plotItem.plot(data, np.arange(0, len(data)), *args, **kwargs)


class ArrayImageView(pg.ImageView):
    """
    ImageView for np.ndarrays with index axes
    """
    transpose = False

    def __init__(self, transpose=False, *args, **kwargs):
        self.transpose = transpose
        self._coord_axes = {
            "left": CoordAxis(dim_index=1, orientation="left"),
            "bottom": CoordAxis(dim_index=0, orientation="bottom"),
        }

        self.plot_item = pg.PlotItem(axisItems=self._coord_axes)
        super().__init__(view=self.plot_item, *args, **kwargs)
        self.view.invertY(False)

    def setImage(self, arr, keep_levels=False, *args, **kwargs):
        if self.transpose:
            arr = arr.T

        levels = self.getLevels()
        
        for axis in self._coord_axes.values():
            axis.setImage(arr)
        
        super().setImage(arr, *args, **kwargs)

        if keep_levels:
            self.setLevels(*levels)

    def recompute(self):
        pass

class CursorRegion(pg.LinearRegionItem):
    _region_width: int = 5
    subject: BehaviorSubject

    def __init__(self, *args, subject=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.subject = subject or BehaviorSubject((self.lines[0].value(), self.lines[1].value()))
        self.lines[1].setMovable(False)
        self.sigRegionChanged.connect(self.update_subject)
        self.subject.subscribe(self.update_from_subject)
    
    def update_subject(self, line):
        low, high = line.getRegion()
        low, high = int(math.floor(low)), int(math.floor(high))
        self.subject.on_next((low, high))
    
    def update_from_subject(self, new_value):
        low, high = new_value
        low, high = min(low, high), max(low, high)

        old_low, old_high = self.lines[0].value(), self.lines[1].value()

        with temporary_attrs(self, blockLineSignal=True):
            self.lines[0].setValue(low)
            self.lines[1].setValue(high)
            self.set_width(high - low)

            if low != old_low:
                self.lineMoved(0)
            if high != old_high:
                self.lineMoved(1)

    def set_width(self, value):
        self._region_width = value
        self.lineMoved(0)

    def lineMoved(self, i):
        if self.blockLineSignal:
            return
        
        self.lines[1].setValue(self.lines[0].value() + self._region_width)
        self.prepareGeometryChange()
        self.sigRegionChanged.emit(self)
    
    def set_location(self, value):
        with temporary_attrs(self, blockLineSignal=True):
            self.lines[1].setValue(value + self._region_width)
            self.lines[0].setValue(value)

