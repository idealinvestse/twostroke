"""Combustion model for 2-stroke engine.

Implements spark ignition, flame propagation, and energy release.
"""

import math
from dataclasses import dataclass

from physics.constants import (
    FUEL_LHV,
    STOICH_AFR,
    OPTIMAL_IGNITION_ANGLE_DEG,
    IGNITION_EFFICIENCY_SIGMA,
    MIXTURE_EFFICIENCY_OPTIMAL_LAMBDA,
    MIXTURE_EFFICIENCY_SIGMA,
)
from physics.utils import clamp01, gaussian_falloff, angle_diff


@dataclass
class CombustionState:
    """Current combustion state."""
    active: bool
    burn_fraction: float   # 0-1, progress of combustion
    theta_ign: float       # Crank angle where ignition started
    duration: float        # Burn duration in radians
    efficiency: float      # Combustion efficiency (0-1)
    lambda_value: float    # Actual AFR / stoichiometric
    available_fuel: float  # Mass of fuel that can be burned (kg)


class CombustionModel:
    """Wiebe-based combustion model with ignition timing."""
    
    @staticmethod
    def calculate_mixture_efficiency(lambda_value: float) -> float:
        """Calculate combustion efficiency based on air-fuel ratio.
        
        Gaussian curve centered at optimal lambda (~0.92 for rich).
        
        Args:
            lambda_value: Actual AFR / stoichiometric
            
        Returns:
            Efficiency in range [0.18, 1.02]
        """
        efficiency = math.exp(
            -((lambda_value - MIXTURE_EFFICIENCY_OPTIMAL_LAMBDA) / MIXTURE_EFFICIENCY_SIGMA) ** 2
        )
        return max(0.18, min(1.02, efficiency))
    
    @staticmethod
    def calculate_ignition_efficiency(ignition_angle_deg: float) -> float:
        """Calculate efficiency based on ignition timing.
        
        Args:
            ignition_angle_deg: Ignition angle (BTDC, degrees)
            
        Returns:
            Efficiency in range [0.35, 1.0]
        """
        error = angle_diff(ignition_angle_deg, OPTIMAL_IGNITION_ANGLE_DEG)
        efficiency = gaussian_falloff(error, IGNITION_EFFICIENCY_SIGMA)
        return max(0.35, min(1.0, efficiency))
    
    @staticmethod
    def can_ignite(
        theta_deg: float,
        ignition_angle_deg: float,
        combustion_active: bool,
        x: float,
        fresh_mass: float,
        ignition_enabled: bool,
        fuel_cutoff: bool,
    ) -> bool:
        """Check if ignition can occur.
        
        Args:
            theta_deg: Current crank angle (degrees)
            ignition_angle_deg: Target ignition angle (degrees)
            combustion_active: Whether combustion is already in progress
            x: Piston position from TDC (m)
            fresh_mass: Mass of fresh charge (kg)
            ignition_enabled: Whether ignition system is on
            fuel_cutoff: Whether fuel is cut off
            
        Returns:
            True if ignition should trigger
        """
        if not ignition_enabled or fuel_cutoff or combustion_active:
            return False
        
        # Ignition window: within 18 degrees of target
        angle_error = angle_diff(theta_deg, ignition_angle_deg)
        if not (0 <= angle_error < 18):
            return False
        
        # Piston must be near TDC
        if x >= 0.03:  # 30mm from TDC
            return False
        
        # Must have fresh charge
        if fresh_mass < 1e-6:
            return False
        
        return True
    
    @staticmethod
    def start_combustion(
        theta: float,
        m_fuel_cyl: float,
        m_air_cyl: float,
        throttle_factor: float,
        ignition_angle_deg: float,
        omega: float = 90.0,
    ) -> CombustionState:
        """Initialize combustion state.
        
        Args:
            theta: Current crank angle (rad)
            m_fuel_cyl: Fuel mass in cylinder (kg)
            m_air_cyl: Air mass in cylinder (kg)
            throttle_factor: Throttle position factor (0-1)
            ignition_angle_deg: Ignition angle setting
            
        Returns:
            Initialized CombustionState
        """
        # Calculate lambda
        actual_fuel_air_ratio = m_fuel_cyl / max(1e-9, m_air_cyl)
        lambda_value = (1.0 / max(1e-9, actual_fuel_air_ratio)) / STOICH_AFR
        
        # Misfire check - for 50cc engine, only check if we have any fuel at all
        # Lambda can be very rich due to fuel transfer dynamics
        available_fuel = min(m_fuel_cyl, m_air_cyl / STOICH_AFR)
        if available_fuel <= 1e-14:
            return CombustionState(
                active=False,
                burn_fraction=0.0,
                theta_ign=0.0,
                duration=0.0,
                efficiency=0.0,
                lambda_value=lambda_value,
                available_fuel=0.0,
            )
        
        # Calculate efficiencies
        mixture_eff = CombustionModel.calculate_mixture_efficiency(lambda_value)
        ignition_eff = CombustionModel.calculate_ignition_efficiency(ignition_angle_deg)
        efficiency = mixture_eff * ignition_eff
        
        # Calculate burn duration based on turbulence
        turbulence = 0.65 + 0.70 * throttle_factor + 0.25 * clamp01(abs(omega) / 260.0)
        turbulence = max(0.1, turbulence)
        duration_deg = 55.0 / turbulence
        
        # Lambda affects burn duration
        if lambda_value < 0.85:
            duration_deg *= 1.10  # Rich burns slightly slower
        elif lambda_value > 1.10:
            duration_deg *= 1.25  # Lean burns noticeably slower
        
        duration = math.radians(max(18.0, min(65.0, duration_deg)))
        
        # Fuel that actually burns
        combustible_fuel = available_fuel * min(1.0, 0.70 + 0.30 * efficiency)
        
        return CombustionState(
            active=True,
            burn_fraction=0.0,
            theta_ign=theta,
            duration=duration,
            efficiency=efficiency,
            lambda_value=lambda_value,
            available_fuel=combustible_fuel,
        )
    
    @staticmethod
    def update_combustion(
        combustion: CombustionState,
        theta: float,
        m_fuel_cyl: float,
        m_air_cyl: float,
        dt: float,
    ) -> tuple[CombustionState, float]:
        """Update combustion progress and calculate energy release.
        
        Args:
            combustion: Current combustion state
            theta: Current crank angle (rad)
            m_fuel_cyl: Current fuel mass in cylinder (kg)
            m_air_cyl: Current air mass in cylinder (kg)
            dt: Timestep (s)
            
        Returns:
            (updated CombustionState, heat_released_J)
        """
        if not combustion.active:
            return combustion, 0.0
        
        # Check for misfire conditions during combustion
        if m_fuel_cyl < 1e-9:
            return CombustionState(
                active=False,
                burn_fraction=combustion.burn_fraction,
                theta_ign=combustion.theta_ign,
                duration=combustion.duration,
                efficiency=0.0,
                lambda_value=combustion.lambda_value,
                available_fuel=0.0,
            ), 0.0
        
        # Calculate progress
        dtheta = (theta - combustion.theta_ign) % (2 * math.pi)
        
        if dtheta >= combustion.duration:
            # Combustion complete
            return CombustionState(
                active=False,
                burn_fraction=1.0,
                theta_ign=combustion.theta_ign,
                duration=combustion.duration,
                efficiency=combustion.efficiency,
                lambda_value=combustion.lambda_value,
                available_fuel=0.0,
            ), 0.0
        
        # Wiebe function for burn rate
        phase = min(1.0, dtheta / max(combustion.duration, 1e-6))
        new_fraction = 1.0 - math.exp(-5.8 * (phase ** 3.0))
        
        delta_fraction = max(0.0, new_fraction - combustion.burn_fraction)
        
        # Calculate fuel burned this step
        fuel_burned = min(
            combustion.available_fuel * delta_fraction,
            m_fuel_cyl
        )
        
        # Calculate air consumed
        air_consumed = fuel_burned * STOICH_AFR
        if air_consumed > m_air_cyl:
            air_consumed = m_air_cyl
            fuel_burned = air_consumed / STOICH_AFR
        
        # Calculate heat release
        heat_released = fuel_burned * FUEL_LHV
        
        return CombustionState(
            active=True,
            burn_fraction=new_fraction,
            theta_ign=combustion.theta_ign,
            duration=combustion.duration,
            efficiency=combustion.efficiency,
            lambda_value=combustion.lambda_value,
            available_fuel=combustion.available_fuel,
        ), heat_released
