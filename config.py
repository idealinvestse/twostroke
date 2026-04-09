from dataclasses import dataclass


@dataclass(frozen=True)
class WindowConfig:
    width: int = 1300
    height: int = 720
    fps: int = 60
    title: str = "Realistisk 2-taktsmotor - Exakt Termodynamik & Gasdynamik"


@dataclass(frozen=True)
class RenderConfig:
    background_color: tuple[int, int, int] = (15, 15, 25)
    cylinder_color: tuple[int, int, int, int] = (180, 180, 210, 100)
    piston_color: tuple[int, int, int] = (120, 120, 140)
    scale: float = 3000.0
    crank_x: int = 400
    crank_y: int = 550
    # Engine geometry constants (pixels)
    piston_height_px: float = 45.0


WINDOW = WindowConfig()
RENDER = RenderConfig()
