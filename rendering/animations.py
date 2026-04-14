"""Animation system for mechanical and thermal effects."""

import math
import random
import time
import pygame
from typing import Tuple
from dataclasses import dataclass


@dataclass
class AnimationState:
    """Current state of all animations."""
    reed_flex: float = 0.0  # Reed valve flex amount (0.0-1.0)
    exhaust_pulse: float = 0.0  # Exhaust pipe pulse amplitude
    vibration_amplitude: float = 0.0  # Motor vibration amplitude
    screen_shake: Tuple[float, float] = (0.0, 0.0)  # Screen shake offset (x, y)
    heat_wobble: float = 0.0  # Heat distortion amount
    camera_offset: Tuple[float, float] = (0.0, 0.0)  # Camera follow offset


class AnimationManager:
    """Manage all visual animations based on engine state."""
    
    def __init__(self):
        self.state = AnimationState()
        self._shake_decay = 0.85  # Screen shake decay factor
        self._vibration_smoothing = 0.1  # RPM-based vibration smoothing
        
    def update(self, engine_state, rpm: float, cylinder_pressure: float, 
               crankcase_pressure: float, reed_opening: float,
               combustion_active: bool, dt: float = 1.0) -> None:
        """Update animation state based on engine physics.
        
        Args:
            engine_state: Engine physics state snapshot
            rpm: Current engine RPM
            cylinder_pressure: Cylinder pressure in Pa
            crankcase_pressure: Crankcase pressure in Pa
            reed_opening: Reed valve opening (0.0-1.0)
            combustion_active: Whether combustion is active
            dt: Delta time multiplier
        """
        # Reed valve flex animation
        self._update_reed_flex(reed_opening, dt)
        
        # Exhaust pipe pulse
        self._update_exhaust_pulse(crankcase_pressure, dt)
        
        # Motor vibration based on RPM
        self._update_vibration(rpm, dt)
        
        # Screen shake from combustion
        if combustion_active and cylinder_pressure > 5e5:  # > 5 Bar
            self._trigger_combustion_shake(cylinder_pressure)
        
        # Decay screen shake
        self._decay_screen_shake(dt)
        
        # Heat wobble based on cylinder temperature
        self._update_heat_wobble(engine_state, dt)
        
        # Camera follow (subtle movement toward interesting events)
        self._update_camera_follow(engine_state, dt)
    
    def _update_reed_flex(self, reed_opening: float, dt: float) -> None:
        """Update reed valve flex animation.
        
        Reed valve flexes outward when open due to pressure differential.
        """
        target_flex = reed_opening
        # Smooth transition
        self.state.reed_flex += (target_flex - self.state.reed_flex) * 0.3 * dt
    
    def _update_exhaust_pulse(self, crankcase_pressure: float, dt: float) -> None:
        """Update exhaust pipe pulse based on crankcase pressure.
        
        Higher pressure causes radial expansion of exhaust pipe.
        """
        # Normalize pressure to pulse amplitude (0.5-2.0 Bar typical)
        pressure_bar = crankcase_pressure / 1e5
        target_pulse = max(0.0, (pressure_bar - 1.0) / 2.0) * 0.05  # Max 5% expansion
        self.state.exhaust_pulse += (target_pulse - self.state.exhaust_pulse) * 0.5 * dt
    
    def _update_vibration(self, rpm: float, dt: float) -> None:
        """Update motor vibration amplitude based on RPM.
        
        Vibration increases quadratically with RPM (RPM²).
        """
        # Normalize RPM (0-12000 typical)
        rpm_norm = min(1.0, rpm / 12000.0)
        target_amplitude = rpm_norm * rpm_norm * 3.0  # Max 3 pixels amplitude
        
        # Smooth transition
        self.state.vibration_amplitude += (
            target_amplitude - self.state.vibration_amplitude
        ) * self._vibration_smoothing * dt
    
    def _trigger_combustion_shake(self, cylinder_pressure: float) -> None:
        """Trigger screen shake from combustion pressure spike.
        
        Higher pressure = stronger shake.
        """
        pressure_bar = cylinder_pressure / 1e5
        shake_intensity = min(5.0, (pressure_bar / 50.0) * 3.0)  # Max 5 pixels
        
        # Random direction
        angle = random.uniform(0, 2 * math.pi)
        shake_x = math.cos(angle) * shake_intensity
        shake_y = math.sin(angle) * shake_intensity
        
        self.state.screen_shake = (shake_x, shake_y)
    
    def _decay_screen_shake(self, dt: float) -> None:
        """Decay screen shake over time."""
        sx, sy = self.state.screen_shake
        self.state.screen_shake = (
            sx * self._shake_decay * dt,
            sy * self._shake_decay * dt
        )
        
        # Stop when very small
        if abs(self.state.screen_shake[0]) < 0.1 and abs(self.state.screen_shake[1]) < 0.1:
            self.state.screen_shake = (0.0, 0.0)
    
    def _update_heat_wobble(self, engine_state, dt: float) -> None:
        """Update heat distortion wobble based on temperature.
        
        Hot surfaces cause visual distortion (heat haze).
        """
        # Get cylinder temperature if available
        temp = getattr(engine_state, 'T_cyl', 450.0)  # Default 450K
        
        # Normalize temperature (293K-2000K typical)
        temp_norm = max(0.0, (temp - 293.0) / (2000.0 - 293.0))
        self.state.heat_wobble = temp_norm * 2.0  # Max 2 pixels wobble
    
    def _update_camera_follow(self, engine_state, dt: float) -> None:
        """Subtle camera movement toward interesting events.
        
        Currently follows combustion events and backfire.
        """
        # Reset camera offset
        self.state.camera_offset = (0.0, 0.0)
        
        # Could be extended to follow specific events
        # For now, keep it simple
    
    def get_vibration_offset(self) -> Tuple[float, float]:
        """Get current vibration offset for rendering.
        
        Returns:
            (x, y) offset in pixels
        """
        if self.state.vibration_amplitude < 0.1:
            return (0.0, 0.0)
        
        angle = random.uniform(0, 2 * math.pi)
        offset = self.state.vibration_amplitude
        return (
            math.cos(angle) * offset,
            math.sin(angle) * offset
        )
    
    def get_total_offset(self) -> Tuple[float, float]:
        """Get total render offset (vibration + screen shake + camera).
        
        Returns:
            (x, y) total offset in pixels
        """
        vib_x, vib_y = self.get_vibration_offset()
        shake_x, shake_y = self.state.screen_shake
        cam_x, cam_y = self.state.camera_offset
        
        return (
            vib_x + shake_x + cam_x,
            vib_y + shake_y + cam_y
        )
    
    def apply_reed_flex(self, rect: pygame.Rect) -> pygame.Rect:
        """Apply reed valve flex to rectangle.
        
        Args:
            rect: Original reed valve rectangle
            
        Returns:
            Deformed rectangle with flex applied
        """
        if self.state.reed_flex < 0.01:
            return rect
        
        # Flex outward (increase width)
        flex_amount = int(self.state.reed_flex * 8)  # Max 8 pixels
        return pygame.Rect(
            rect.x - flex_amount,
            rect.y,
            rect.width + flex_amount * 2,
            rect.height
        )
    
    def apply_exhaust_pulse(self, rect: pygame.Rect) -> pygame.Rect:
        """Apply exhaust pulse to rectangle.
        
        Args:
            rect: Original exhaust pipe rectangle
            
        Returns:
            Deformed rectangle with pulse applied
        """
        if self.state.exhaust_pulse < 0.001:
            return rect
        
        # Radial expansion (increase size)
        pulse_amount = int(self.state.exhaust_pulse * rect.width)
        return pygame.Rect(
            rect.x - pulse_amount // 2,
            rect.y - pulse_amount // 2,
            rect.width + pulse_amount,
            rect.height + pulse_amount
        )
    
    def get_heat_distortion_offset(self, base_y: float) -> float:
        """Get heat distortion offset for a Y position.
        
        Args:
            base_y: Base Y coordinate
            
        Returns:
            Vertical offset in pixels
        """
        if self.state.heat_wobble < 0.1:
            return 0.0
        
        # Wavy pattern based on position and time
        wave = math.sin(base_y * 0.05 + time.time() * 5.0)
        return wave * self.state.heat_wobble
