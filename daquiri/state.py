"""
Mostly contains types and data definitions related to state serialization and deserialization. This
is pulled out of other relevant modules because it is a declaration of relevant data (for the most part)
and because other components sometimes need access to the data types of another otherwise isolated
component.

The serialization and deserialization scheme is essentially that at startup,
the most recent pickled state file is found, if available, loaded, and its contents
distributed over the parts of the application that are allowed to provide state to the application.
"""
import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from PyQt5.QtCore import QRect

__all__ = ('find_newest_state_filename', 'generate_state_filename',)


@dataclass
class PanelState:
    geometry: QRect


@dataclass
class SerializationSchema:
    daquiri_version: str = ''
    user_version: str = ''
    commit: str = ''
    app_root: str = ''


@dataclass
class InstrumentPanelState(PanelState):
    pass


@dataclass
class InstrumentState:
    panel_state: InstrumentPanelState
    axes: Dict[str, Any]
    properties: Dict[str, Any]


@dataclass
class AppState:
    user: str = 'test_user'
    session_name: str = 'test_session'
    profile: str = None


@dataclass
class ActorState:
    pass


@dataclass
class AxisState:
    pass


@dataclass
class LogicalAxisState(AxisState):
    internal_state: Any
    physical_state: Optional[List[Any]]
    logical_state: Optional[List[Any]]


@dataclass
class DaquiriStateAtRest:
    # metadata
    schema: SerializationSchema

    daquiri_state: AppState

    # content
    panels: Dict[str, PanelState]
    actors: Dict[str, ActorState]
    managed_instruments: Dict[str, InstrumentState]


def _base_state_path(app) -> Path:
    return Path(str(app.app_root / app.config.state_directory))


def find_newest_state_filename(app) -> Optional[Path]:
    base = _base_state_path(app)
    state_files = sorted(base.glob('*.state.pickle'), key=lambda p: p.stat().st_mtime, reverse=True)
    return state_files[0] if state_files else None


def generate_state_filename(app) -> Path:
    base = _base_state_path(app)
    now = datetime.datetime.now().isoformat().replace(':', '-').replace('.', '-')
    return base / f'{now}.state.pickle'
