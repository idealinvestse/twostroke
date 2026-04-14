"""Menu state enumeration for PyGame UI."""
from enum import Enum, auto


class MenuState(Enum):
    """Application state enumeration."""
    MAIN_MENU = auto()
    SIMULATION = auto()
    PAUSED = auto()
