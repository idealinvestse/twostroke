"""Analog gauge rendering system for dashboard."""

import math
import pygame
from typing import Tuple, List


class AnalogGauge:
    """Analog gauge with needle, scale, and background."""
    
    def __init__(self, x: int, y: int, radius: int, 
                 min_val: float, max_val: float, 
                 title: str, unit: str = ""):
        """Initialize analog gauge.
        
        Args:
            x: Center X position
            y: Center Y position
            radius: Gauge radius
            min_val: Minimum value
            max_val: Maximum value
            title: Gauge title
            unit: Unit string
        """
        self.x = x
        self.y = y
        self.radius = radius
        self.min_val = min_val
        self.max_val = max_val
        self.title = title
        self.unit = unit
        
        # Color zones (start_angle_deg, end_angle_deg, color)
        self.zones: List[Tuple[float, float, Tuple[int, int, int]]] = []
    
    def add_zone(self, start_angle_deg: float, end_angle_deg: float, color: Tuple[int, int, int]) -> None:
        """Add color zone to gauge.
        
        Args:
            start_angle_deg: Start angle in degrees (0 = right, clockwise)
            end_angle_deg: End angle in degrees
            color: RGB color tuple
        """
        self.zones.append((start_angle_deg, end_angle_deg, color))
    
    def value_to_angle(self, value: float) -> float:
        """Convert value to angle in radians.
        
        Args:
            value: Value to convert
            
        Returns:
            Angle in radians (0 = right, clockwise)
        """
        clamped = max(self.min_val, min(self.max_val, value))
        normalized = (clamped - self.min_val) / (self.max_val - self.min_val)
        # Gauge spans 225 degrees (from -157.5 to +67.5)
        start_angle = math.radians(-157.5)
        end_angle = math.radians(67.5)
        return start_angle + normalized * (end_angle - start_angle)
    
    def draw(self, surface: pygame.Surface, value: float, font) -> None:
        """Draw gauge to surface.
        
        Args:
            surface: Target surface
            value: Current value to display
            font: Font for text
        """
        # Draw background (radial gradient simulation)
        for i in range(self.radius, 0, -2):
            shade = 30 + int(20 * (1 - i / self.radius))
            pygame.draw.circle(surface, (shade, shade, shade + 5), (self.x, self.y), i)
        
        # Draw color zones
        for start_deg, end_deg, color in self.zones:
            self._draw_arc(surface, start_deg, end_deg, color)
        
        # Draw scale (tick marks)
        self._draw_scale(surface, font)
        
        # Draw needle
        self._draw_needle(surface, value)
        
        # Draw center cap
        pygame.draw.circle(surface, (200, 200, 210), (self.x, self.y), 8)
        pygame.draw.circle(surface, (50, 50, 60), (self.x, self.y), 8, 2)
        
        # Draw title and value
        self._draw_text(surface, value, font)
    
    def _draw_arc(self, surface: pygame.Surface, start_deg: float, end_deg: float, color: Tuple[int, int, int]) -> None:
        """Draw colored arc segment."""
        start_rad = math.radians(start_deg)
        end_rad = math.radians(end_deg)
        thickness = 6
        
        points = []
        steps = max(10, int(abs(end_deg - start_deg) / 2))
        for i in range(steps + 1):
            angle = start_rad + (end_rad - start_rad) * (i / steps)
            px = self.x + (self.radius - 15) * math.cos(angle)
            py = self.y + (self.radius - 15) * math.sin(angle)
            points.append((px, py))
        
        if len(points) >= 2:
            pygame.draw.lines(surface, color, False, points, thickness)
    
    def _draw_scale(self, surface: pygame.Surface, font) -> None:
        """Draw tick marks and labels."""
        start_angle = math.radians(-157.5)
        end_angle = math.radians(67.5)
        
        # Major ticks
        for i in range(9):  # 8 major ticks
            angle = start_angle + (end_angle - start_angle) * (i / 8)
            inner_r = self.radius - 15
            outer_r = self.radius - 8
            x1 = self.x + inner_r * math.cos(angle)
            y1 = self.y + inner_r * math.sin(angle)
            x2 = self.x + outer_r * math.cos(angle)
            y2 = self.y + outer_r * math.sin(angle)
            pygame.draw.line(surface, (200, 200, 200), (x1, y1), (x2, y2), 2)
        
        # Minor ticks
        for i in range(40):  # 40 minor ticks
            angle = start_angle + (end_angle - start_angle) * (i / 40)
            inner_r = self.radius - 15
            outer_r = self.radius - 12
            x1 = self.x + inner_r * math.cos(angle)
            y1 = self.y + inner_r * math.sin(angle)
            x2 = self.x + outer_r * math.cos(angle)
            y2 = self.y + outer_r * math.sin(angle)
            pygame.draw.line(surface, (150, 150, 160), (x1, y1), (x2, y2), 1)
    
    def _draw_needle(self, surface: pygame.Surface, value: float) -> None:
        """Draw needle with shadow."""
        angle = self.value_to_angle(value)
        
        # Needle shadow
        shadow_offset = 2
        needle_length = self.radius - 20
        sx = self.x + shadow_offset + needle_length * math.cos(angle + math.pi)
        sy = self.y + shadow_offset + needle_length * math.sin(angle + math.pi)
        pygame.draw.line(surface, (30, 30, 35), 
                        (self.x + shadow_offset, self.y + shadow_offset), 
                        (sx, sy), 3)
        
        # Needle
        nx = self.x + needle_length * math.cos(angle + math.pi)
        ny = self.y + needle_length * math.sin(angle + math.pi)
        pygame.draw.line(surface, (220, 50, 50), (self.x, self.y), (nx, ny), 3)
    
    def _draw_text(self, surface: pygame.Surface, value: float, font) -> None:
        """Draw title and current value."""
        # Title
        title_surf = font.render(self.title, True, (200, 200, 210))
        title_rect = title_surf.get_rect(center=(self.x, self.y + self.radius + 15))
        surface.blit(title_surf, title_rect)
        
        # Value
        val_str = f"{value:.1f} {self.unit}"
        val_surf = font.render(val_str, True, (255, 255, 255))
        val_rect = val_surf.get_rect(center=(self.x, self.y + self.radius + 30))
        surface.blit(val_surf, val_rect)


class Dashboard:
    """Dashboard containing multiple gauges."""
    
    def __init__(self, x: int, y: int):
        """Initialize dashboard.
        
        Args:
            x: Dashboard X position
            y: Dashboard Y position
        """
        self.x = x
        self.y = y
        self.gauges: List[AnalogGauge] = []
    
    def add_gauge(self, gauge: AnalogGauge) -> None:
        """Add gauge to dashboard.
        
        Args:
            gauge: AnalogGauge instance
        """
        self.gauges.append(gauge)
    
    def draw(self, surface: pygame.Surface, values: dict, font) -> None:
        """Draw all gauges.
        
        Args:
            surface: Target surface
            values: Dictionary mapping gauge titles to values
            font: Font for text
        """
        for gauge in self.gauges:
            value = values.get(gauge.title, gauge.min_val)
            gauge.draw(surface, value, font)


def create_default_dashboard(x: int, y: int) -> Dashboard:
    """Create default dashboard with common gauges.
    
    Args:
        x: Dashboard X position
        y: Dashboard Y position
        
    Returns:
        Dashboard instance with RPM, pressure, and temperature gauges
    """
    dashboard = Dashboard(x, y)
    
    # RPM Gauge
    rpm_gauge = AnalogGauge(x, y, 60, 0, 12000, "RPM")
    rpm_gauge.add_zone(0, 30, (50, 200, 50))    # Green - low RPM
    rpm_gauge.add_zone(30, 60, (200, 200, 50))  # Yellow - mid RPM
    rpm_gauge.add_zone(60, 100, (200, 50, 50))  # Red - high RPM
    dashboard.add_gauge(rpm_gauge)
    
    # Cylinder Pressure Gauge
    cyl_press_gauge = AnalogGauge(x + 140, y, 60, 0, 80, "Cyl Press", "Bar")
    cyl_press_gauge.add_zone(0, 30, (50, 200, 50))
    cyl_press_gauge.add_zone(30, 50, (200, 200, 50))
    cyl_press_gauge.add_zone(50, 80, (200, 50, 50))
    dashboard.add_gauge(cyl_press_gauge)
    
    # Temperature Gauge
    temp_gauge = AnalogGauge(x + 280, y, 60, 293, 2000, "Temp", "K")
    temp_gauge.add_zone(0, 40, (50, 100, 200))   # Blue - cold
    temp_gauge.add_zone(40, 70, (50, 200, 50))   # Green - normal
    temp_gauge.add_zone(70, 100, (200, 200, 50)) # Yellow - warm
    temp_gauge.add_zone(100, 130, (200, 50, 50)) # Red - hot
    dashboard.add_gauge(temp_gauge)
    
    return dashboard
