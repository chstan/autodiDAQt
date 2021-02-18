from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

import pyrsistent as pr
from PyQt5.QtCore import (
    QAbstractListModel,
    QAbstractTableModel,
)

import rx
from rx import Observable
from rx import operators as ops
from rx.subject import Subject


def left(a: Observable) -> Observable:
    return a.pipe(ops.map(lambda v: (v, None)))


def right(a: Observable) -> Observable:
    return a.pipe(ops.map(lambda v: (None, v)))


def merge_either(a: Observable, b: Observable) -> Observable:
    return rx.merge(left(a), right(b))


def accumulate_and_clear(values: Observable, clear: Observable) -> Observable:
    return merge_either(values, clear.pipe(ops.map(lambda _: True))).pipe(
        ops.scan(
            lambda collected, either: [] if either[1] else collected + [either[0]],
            [],
        )
    )


class TransactionKind(Enum):
    Add = 0
    Remove = 1
    Reindex = 2
    Clear = 3
    Swap = 4

    AddColumn = 5
    RemoveColumn = 6


@dataclass
class IndexedTransaction:
    index: Optional[int] = None
    payload: Any = None


@dataclass
class ReindexTransaction:
    from_index: int
    to_index: int


@dataclass
class Transaction:
    kind: TransactionKind
    message: Any

    @classmethod
    def swap(cls, index: int, new_value: Any):
        return cls(
            kind=TransactionKind.Swap,
            message=IndexedTransaction(index, new_value),
        )

    @classmethod
    def add(cls, index: int = None, new_value: Any = None):
        return cls(
            kind=TransactionKind.Add,
            message=IndexedTransaction(index, new_value),
        )

    @classmethod
    def remove(cls, index: int):
        return cls(kind=TransactionKind.Remove, message=IndexedTransaction(index))

    @classmethod
    def clear(cls):
        return cls(kind=TransactionKind.Clear, message=None)

    @classmethod
    def reindex(cls, from_index: int, to_index: int):
        return cls(
            kind=TransactionKind.Reindex,
            message=ReindexTransaction(from_index, to_index),
        )


class RxListPattern:
    # raw
    add: Observable
    remove: Observable
    reindex: Observable
    clear: Observable
    edit_at_index: Observable

    history: Observable

    # intermediary
    values: Observable

    # values
    initial_state: pr.PVector

    @staticmethod
    def reduce_list_state(state: pr.PVector, tx: Transaction) -> pr.PVector:
        if tx.kind == TransactionKind.Clear:
            return pr.v()
        elif tx.kind == TransactionKind.Add:
            if tx.message.index is None:
                return state.append(tx.message.payload)
            else:
                return (
                    state[: tx.message.index]
                    .append(tx.message.payload)
                    .extend(state[tx.message.index :])
                )

        elif tx.kind == TransactionKind.Remove:
            return state.delete(tx.message.index)

        elif tx.kind == TransactionKind.Reindex:
            old = state[tx.message.to_index]
            state = state.set(tx.message.to_index, state[tx.message.from_index])
            return state.set(tx.message.from_index, old)

        elif tx.kind == TransactionKind.Swap:
            return state.set(tx.message.index, tx.message.payload)
        else:
            raise ValueError(f"Unhandled Transaction {tx}")

    def __init__(
        self,
        add=None,
        remove=None,
        reindex=None,
        clear=None,
        edit_at_index=None,
        initial_state=None,
    ):
        self.add = Subject() if add is None else add
        self.remove = Subject() if remove is None else remove
        self.reindex = Subject() if reindex is None else reindex
        self.clear = Subject() if clear is None else clear
        self.edit_at_index = Subject() if edit_at_index is None else edit_at_index

        self.initial_state = pr.v() if initial_state is None else initial_state

        self.history = rx.merge(self.add, self.remove, self.reindex, self.clear, self.edit_at_index)

        self._values = self.history.pipe(ops.scan(self.reduce_list_state, self.initial_state))
        self.values = self._values
        self.values_with_history = self._values.pipe(
            ops.zip(self.history),
            # ops.replay(buffer_size=1)
        )

    def bind_to_model(self, model_cls=None) -> QAbstractListModel:
        if model_cls is None:
            from daquiri.ui import models

            model_cls = models.RxListModel

        return model_cls(self)


class RxTablePattern:
    # raw
    add_row: Observable
    remove_row: Observable
    reindex_row: Observable
    edit_row_at_index: Observable

    clear: Observable

    history: Observable

    # intermediary
    values: Observable

    @staticmethod
    def reduce_table_state(
        state: Tuple[pr.PVector, pr.PVector], tx: Transaction
    ) -> Tuple[pr.PVector, pr.PVector]:
        """
        For now we are only doing row operations so we can be lazy and recycle
        Args:
            state:
            tx:

        Returns:
        """
        rows, cols = state
        return RxListPattern.reduce_list_state(rows, tx), cols

    def __init__(
        self,
        columns,
        add_row=None,
        remove_row=None,
        edit_row_at_index=None,
        clear=None,
        initial_rows=None,
    ):
        self.add_row = Subject() if add_row is None else add_row
        self.remove_row = Subject() if remove_row is None else remove_row
        self.clear = Subject() if clear is None else clear
        self.edit_row_at_index = Subject() if edit_row_at_index is None else edit_row_at_index

        self.initial_rows = pr.v() if initial_rows is None else initial_rows
        self.initial_columns = pr.v(*columns)

        self.history = rx.merge(self.add_row, self.remove_row, self.clear, self.edit_row_at_index)
        self._values_with_columns = self.history.pipe(
            ops.scan(
                self.reduce_table_state,
                (self.initial_rows, self.initial_columns),
            )
        )

        self.values = self._values_with_columns.pipe(ops.map(lambda x: x[0]))
        self.columns = self._values_with_columns.pipe(ops.map(lambda x: x[1]))
        self.values_with_history = self.values.pipe(ops.zip(self.history))

    def bind_to_model(self, model_cls=None) -> QAbstractTableModel:
        if model_cls is None:
            from daquiri.ui import models

            model_cls = models.RxTableModel

        return model_cls(self)
