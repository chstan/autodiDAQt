from typing import Dict, Optional, Tuple

import pandas as pd
import rx
import rx.operators as ops
from rx.subject import Subject

__all__ = (
    "reactive_frame",
    "ReactivePlot",
)


def reactive_frame(
    initial: Optional[pd.DataFrame] = None, mutate=False
) -> Tuple[Subject, rx.Observable]:
    """
    Creates a pair of observables, a subject that allows generating a stream of data, and
    a DataFrame accumulator computed from the data. This can operate in either mutable (where the
    data frame is modified rather than concatenated with each new point) or immutable (default) operation.

    In concurrent applications, you should be wary of setting `mutable=True`, unless you are okay
    with the data being updated behind your back. That being said, this option is more performant as pandas
    does not need to make a new copy of the frame with every push of data onto the stream.

    Args:
        initial (pd.DataFrame): Initial data frame which can be used to populate the types and column names.
        mutate (bool): Whether to modify or concat (make new copy) new data onto the accumulated DataFrame.

    Returns:
        A tuple of an rx.Subject and an rx.Observable providing the raw value
        and accumulated value streams respectively.
    """
    subject = Subject()

    def append_to_frame(old_frame: pd.DataFrame, new_item: Dict[str, any]):
        if mutate:
            old_frame.loc[len(old_frame)] = new_item
            return old_frame

        return pd.concat([old_frame, pd.DataFrame([new_item])], ignore_index=True)

    accumulated = subject.pipe(ops.scan(append_to_frame, initial))

    return subject, accumulated


class ReactivePlot:
    """
    Links a `reactive_frame` to an axes so that data is updated whenever the stream updates.

    Different strategies for writing data onto the stream are supported:

    1. strategy='call', calls plt.[plot_fn] as appropriate with the same "style arguments"
    2. strategy='set_data', appends to the data and calls matplotlib's `set_data` family of functions
    3. strategy='replot', the safest and slowest, deletes and replots the element each time
    """

    def __init__(
        self,
        ax,
        source: rx.Observable,
        method: str,
        x=None,
        y=None,
        strategy="call",
    ):
        self.source = source
        self.method = method
        self.ax = ax
        self.x = x
        self.y = y
        self.strategy = strategy
        self.last_index = None
        self.source.subscribe(self.on_plot)

    @classmethod
    def link_plot(cls, axes, source: rx.Observable, x=None, y=None, strategy="call"):
        return ReactivePlot(axes, source, method="plot", x=x, y=y, strategy=strategy)

    @classmethod
    def link_scatter(cls, axes, source: rx.Observable, x=None, y=None, strategy="call"):
        return ReactivePlot(axes, source, method="scatter", x=x, y=y, strategy=strategy)

    def infer_x(self, df: pd.DataFrame):
        """
        Once we have received the first data, determine which axis is "x"

        Args:
            df: The data frame for which we are hoping to infer the index/independent variable column.
        """
        if self.x:
            assert self.x in df.columns
        else:
            self.x = df.index.name

    def infer_y(self, df: pd.DataFrame):
        """
        Like infer_x, once we have received the first data, determine which axis is "y".
        Importantly, this should be called after self.infer_x because otherwise we might mistakenly
        plot x against x.

        Args:
            df: The data frame from which we hope to infer the dependent (y).
        """

        if isinstance(self.y, str):
            self.y = [self.y]
        if self.y is None:
            self.y = [y for y in list(df.columns) if y != self.x]

        assert all(y in df.columns for y in self.y)

    def received_first_data(self, df: pd.DataFrame):
        self.infer_x(df)
        self.infer_y(df)

    def collect_new_data(self, df: pd.DataFrame):
        if self.last_index is None:
            return df

        return (
            df.loc[df.index > self.last_index]
            if self.x is None
            else df.loc[df[self.x] > self.last_index]
        )

    def on_plot(self, df: pd.DataFrame):
        if self.last_index is None:
            self.received_first_data(df)

        data_since = self.collect_new_data(df)

        x = data_since.index.values if self.x is None else data_since[self.x].values
        self.last_index = x[-1]

        lim = self.ax.get_xlim()
        for i, y in enumerate(self.y):
            self.ax.scatter(x, data_since[y].values, c=f"C{i}")
        self.ax.set_xlim(lim)

        self.ax.figure.canvas.draw()
        self.ax.figure.canvas.flush_events()
