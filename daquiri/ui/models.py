import contextlib
from typing import Any, List, Tuple

from PyQt5.QtCore import (
    QAbstractListModel,
    QAbstractTableModel,
    QModelIndex,
    Qt,
)
from PyQt5.QtWidgets import QAbstractItemView

from daquiri.reactive_utils import (
    RxListPattern,
    RxTablePattern,
    Transaction,
    TransactionKind,
)


class DeferredAttachmentModel:
    late_bindings = None
    cached_data = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.late_bindings = []

    def bind_to_ui(self, view: QAbstractItemView, late=True):
        if self.cached_data is None and late:
            self.late_bindings.append(view)
        else:
            view.setModel(self)
            view.show()

    def attempt_to_bind(self):
        if self.cached_data is None:
            for late_binding in self.late_bindings:
                self.bind_to_ui(late_binding, late=False)

            self.late_bindings.clear()

    @contextlib.contextmanager
    def transaction(self, new_data, tx: Transaction):
        if tx.kind == TransactionKind.Add:
            index = len(new_data) - 1 if tx.message.index is None else tx.message.index
            self.beginInsertRows(QModelIndex(), index, index)
        elif tx.kind == TransactionKind.Remove:
            self.beginRemoveRows(QModelIndex(), tx.message.index, tx.message.index)
        elif tx.kind == TransactionKind.Clear:
            self.beginResetModel()
        elif tx.kind == TransactionKind.Reindex:
            pass
        elif tx.kind == TransactionKind.Swap:
            pass

        yield

        if tx.kind == TransactionKind.Add:
            self.endInsertRows()
        elif tx.kind == TransactionKind.Remove:
            self.endRemoveRows()
        elif tx.kind == TransactionKind.Clear:
            self.endResetModel()
        elif tx.kind == TransactionKind.Reindex:
            self.dataChanged.emit(tx.message.from_index, tx.message.from_index, [])
            self.dataChanged.emit(tx.message.to_index, tx.message.to_index, [])
        elif tx.kind == TransactionKind.Swap:
            self.dataChanged.emit(tx.message.index, tx.message.index, [])


class RxTableModel(DeferredAttachmentModel, QAbstractTableModel):
    def __init__(self, pattern: RxTablePattern, parent=None):
        super().__init__(parent=parent)
        self.pattern = pattern
        self.pattern.values_with_history.subscribe(self.update)

    def update(self, values_and_tx: Tuple[List[Any], Transaction]):
        rows, tx = values_and_tx
        self.attempt_to_bind()

        with self.transaction(rows, tx):
            self.cached_data = rows

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self.cached_data or [])

    def columnCount(self, parent=None, *args, **kwargs):
        return len(self.pattern.initial_columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.pattern.initial_columns[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        row = index.row()
        column = index.column()

        if 0 <= row < self.rowCount() and 0 <= column < self.columnCount() and index.isValid():
            if role == Qt.DisplayRole:
                return str(self.cached_data[row][column])

        return None


class RxListModel(DeferredAttachmentModel, QAbstractListModel):
    def __init__(self, pattern: RxListPattern, parent=None):
        super().__init__(parent=parent)
        self.pattern = pattern
        self.pattern.values_with_history.subscribe(self.update)

    def update(self, values_and_tx: Tuple[List[Any], Transaction]):
        values, tx = values_and_tx
        self.attempt_to_bind()

        with self.transaction(values, tx):
            self.cached_data = values

    def data(self, index, role=Qt.DisplayRole):
        row = index.row()
        if 0 <= row < self.rowCount() and index.isValid():

            if role == Qt.DisplayRole:
                return str(self.cached_data[row])

        return None

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self.cached_data or [])
