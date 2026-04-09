"""Slider-crank kinematics for 2-stroke engine.

Calculates piston position, velocity, and cylinder volumes
based on crank angle.
"""

import math
from dataclasses import dataclass
from physics.constants import (
    HALF_STROKE_M,
    CON_ROD_M,
    PISTON_AREA_M2,
    CLEARANCE_VOLUME_M3,
    CRANKCASE_VOLUME_M3,
    EPSILON_VOLUME,
)


@dataclass
class KinematicState:
    """Piston kinematic state at a given crank angle."""
    x: float           # Piston position from TDC (m)
    v_cyl: float       # Cylinder volume (m³)
    v_cr: float        # Crankcase volume (m³)
    dx_dtheta: float   # Rate of change dx/dtheta (m/rad)


class SliderCrankKinematics:
    """Slider-crank mechanism for 2-stroke engine.
    
    Geometry based on crank radius R (half-stroke), connecting rod length L,
    and piston area A_p (derived from bore).
    """
    
    def __init__(self) -> None:
        self.R = HALF_STROKE_M      # Crank radius (m)
        self.L = CON_ROD_M          # Connecting rod length (m)
        self.A_p = PISTON_AREA_M2   # Piston area (m²)
        self.V_c = CLEARANCE_VOLUME_M3   # Clearance volume at TDC (m³)
        self.V_cr_base = CRANKCASE_VOLUME_M3  # Base crankcase volume (m³)
    
    def calculate(self, theta: float) -> KinematicState:
        """Calculate kinematic state at given crank angle.
        
        Args:
            theta: Crank angle in radians (0 at TDC)
            
        Returns:
            KinematicState with position, volumes, and dx/dtheta
        """
        s_theta = math.sin(theta)
        c_theta = math.cos(theta)
        
        # Connecting rod angle beta
        beta_arg = max(-1.0, min(1.0, self.R / self.L * s_theta))
        beta = math.asin(beta_arg)
        c_beta = math.cos(beta)
        
        # Guard against division by zero when c_beta approaches zero
        c_beta = max(c_beta, 1e-6)
        
        # Piston position from TDC
        x = self.R + self.L - (self.R * c_theta + self.L * c_beta)
        
        # dx/dtheta for velocity calculation
        dx_dtheta = self.R * s_theta * (1 + self.R * c_theta / (self.L * c_beta))
        
        # Volumes
        v_cyl = max(self.V_c + self.A_p * x, EPSILON_VOLUME)
        v_cr = max(self.V_cr_base + self.A_p * (2 * self.R - x), EPSILON_VOLUME)
        
        return KinematicState(x=x, v_cyl=v_cyl, v_cr=v_cr, dx_dtheta=dx_dtheta)
    
    def get_displacement(self) -> float:
        """Return engine displacement volume (m³)."""
        return self.A_p * 2 * self.R
    
    def get_compression_ratio(self) -> float:
        """Return geometric compression ratio."""
        V_d = self.get_displacement()
        return (V_d + self.V_c) / self.V_c
