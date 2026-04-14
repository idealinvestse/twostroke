"""Combustion model for 2-stroke engine.

Implements spark ignition, flame propagation, and energy release.
Includes residual-sensitive combustion with variable Wiebe parameters.
"""

import math
from dataclasses import dataclass
from typing import Tuple

from physics.constants import (
    FUEL_LHV,
    STOICH_AFR,
    OPTIMAL_IGNITION_ANGLE_DEG,
    IGNITION_EFFICIENCY_SIGMA,
    MIXTURE_EFFICIENCY_OPTIMAL_LAMBDA,
    MIXTURE_EFFICIENCY_SIGMA,
    T_ATM,
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
    residual_fraction: float = 0.0  # Fraction of cylinder that is residual gas
    charge_temperature: float = T_ATM  # Initial charge temperature (K)


class AdvancedCombustionModel:
    """Advanced combustion model with residual sensitivity and variable Wiebe parameters.
    
    Implements:
    - Residual gas fraction effects on burn rate and efficiency
    - Charge temperature effects on ignition and burn duration
    - Mixture homogeneity effects from scavenging zones
    - Variable Wiebe parameters based on operating conditions
    - Knock detection based on end-gas autoignition
    
    Based on:
    - Heywood's Internal Combustion Engine Fundamentals
    - SAE papers on 2-stroke combustion optimization
    - Blair's Two-Stroke Engine Tuning
    """
    
    def __init__(self) -> None:
        """Initialize advanced combustion model with base parameters."""
        # Base Wiebe parameters for premixed phase
        self.base_a1 = 6.0    # Premixed shape factor
        self.base_m1 = 2.0    # Premixed exponent
        
        # Base Wiebe parameters for diffusion phase
        self.base_a2 = 3.0    # Diffusion shape factor
        self.base_m2 = 1.0    # Diffusion exponent
        
        # Residual sensitivity
        self.residual_burn_slowdown = 0.8  # How much residuals slow burn
        self.residual_efficiency_penalty = 0.5  # Efficiency loss from residuals
        
        # Temperature sensitivity
        self.temp_burn_factor = 0.001  # Burn rate change per K
        self.ignition_temp_threshold = 600.0  # K, min temp for reliable ignition
        
        # Homogeneity sensitivity (from scavenging zones)
        self.homogeneity_burn_bonus = 0.3  # Burn rate bonus from good mixing
        self.homogeneity_eff_bonus = 0.15  # Efficiency bonus from good mixing
    
    def calculate_residual_factor(self, residual_fraction: float) -> Tuple[float, float]:
        """Calculate residual gas effects on combustion.
        
        Args:
            residual_fraction: Fraction of cylinder mass that is residual (0-1)
            
        Returns:
            Tuple of (burn_rate_factor, efficiency_factor)
        """
        # Higher residuals = slower burn, lower efficiency
        # Use exponential decay model
        burn_rate_factor = math.exp(-self.residual_burn_slowdown * residual_fraction)
        efficiency_factor = 1.0 - self.residual_efficiency_penalty * residual_fraction
        
        return clamp01(burn_rate_factor), clamp01(efficiency_factor)
    
    def calculate_temperature_factor(self, charge_temp: float) -> Tuple[float, float]:
        """Calculate charge temperature effects on combustion.
        
        Args:
            charge_temp: Initial charge temperature (K)
            
        Returns:
            Tuple of (burn_rate_factor, ignition_factor)
        """
        # Higher temperature = faster burn (Arrhenius-like)
        temp_rise = max(0.0, charge_temp - T_ATM)
        burn_rate_factor = 1.0 + self.temp_burn_factor * temp_rise
        
        # Ignition reliability drops at low temperatures
        ignition_factor = clamp01((charge_temp - T_ATM) / max(1.0, self.ignition_temp_threshold - T_ATM))
        
        return min(1.5, burn_rate_factor), ignition_factor
    
    def calculate_homogeneity_factor(self, charge_purity: float) -> Tuple[float, float]:
        """Calculate mixture homogeneity effects from scavenging quality.
        
        Args:
            charge_purity: Fraction of charge that is fresh (0-1)
            
        Returns:
            Tuple of (burn_rate_factor, efficiency_factor)
        """
        # Higher purity (better scavenging) = more homogeneous = better burn
        # Use quadratic to emphasize high purity
        purity_factor = charge_purity ** 2
        burn_rate_factor = 1.0 + self.homogeneity_burn_bonus * purity_factor
        efficiency_factor = 1.0 + self.homogeneity_eff_bonus * purity_factor
        
        return min(1.4, burn_rate_factor), min(1.2, efficiency_factor)
    
    def calculate_wiebe_parameters(
        self,
        lambda_value: float,
        residual_fraction: float,
        charge_temp: float,
        charge_purity: float,
    ) -> Tuple[float, float, float, float, float]:
        """Calculate variable Wiebe parameters based on operating conditions.
        
        Args:
            lambda_value: Air-fuel ratio (actual/stoich)
            residual_fraction: Residual gas fraction (0-1)
            charge_temp: Charge temperature (K)
            charge_purity: Charge purity from scavenging (0-1)
            
        Returns:
            Tuple of (a1, m1, a2, m2, alpha) where:
            - a1, m1: Premixed Wiebe parameters
            - a2, m2: Diffusion Wiebe parameters
            - alpha: Blending factor between phases
        """
        # Calculate condition factors
        residual_burn, residual_eff = self.calculate_residual_factor(residual_fraction)
        temp_burn, temp_ign = self.calculate_temperature_factor(charge_temp)
        purity_burn, purity_eff = self.calculate_homogeneity_factor(charge_purity)
        
        # Combined burn rate factor
        burn_factor = residual_burn * temp_burn * purity_burn
        
        # Adjust Wiebe parameters based on conditions
        # Higher burn rate = higher shape factors (faster burn)
        a1 = self.base_a1 * burn_factor
        m1 = self.base_m1 * burn_factor
        
        a2 = self.base_a2 * burn_factor
        m2 = self.base_m2 * burn_factor
        
        # Blend factor: rich mixtures have more premixed, lean more diffusion
        # Also affected by homogeneity - better mixing = more premixed
        alpha = clamp01(0.6 + 0.2 * (1.0 - lambda_value) + 0.1 * charge_purity)
        
        return a1, m1, a2, m2, alpha
    
    def calculate_combustion_efficiency(
        self,
        lambda_value: float,
        residual_fraction: float,
        charge_purity: float,
        ignition_angle_deg: float,
    ) -> float:
        """Calculate overall combustion efficiency including all factors.
        
        Args:
            lambda_value: Air-fuel ratio
            residual_fraction: Residual gas fraction
            charge_purity: Charge purity from scavenging
            ignition_angle_deg: Ignition timing
            
        Returns:
            Overall efficiency (0-1)
        """
        # Base mixture efficiency
        mixture_eff = math.exp(
            -((lambda_value - MIXTURE_EFFICIENCY_OPTIMAL_LAMBDA) / MIXTURE_EFFICIENCY_SIGMA) ** 2
        )
        mixture_eff = max(0.18, min(1.02, mixture_eff))
        
        # Ignition timing efficiency
        error = angle_diff(ignition_angle_deg, OPTIMAL_IGNITION_ANGLE_DEG)
        ignition_eff = gaussian_falloff(error, IGNITION_EFFICIENCY_SIGMA)
        ignition_eff = max(0.35, min(1.0, ignition_eff))
        
        # Residual efficiency penalty
        _, residual_eff = self.calculate_residual_factor(residual_fraction)
        
        # Homogeneity efficiency bonus
        _, purity_eff = self.calculate_homogeneity_factor(charge_purity)
        
        # Combined efficiency
        total_eff = mixture_eff * ignition_eff * residual_eff * purity_eff
        
        return clamp01(total_eff)
    
    def check_knock(
        self,
        cylinder_pressure: float,
        cylinder_temp: float,
        lambda_value: float,
        burn_fraction: float,
    ) -> bool:
        """Check for knock conditions (end-gas autoignition).
        
        Args:
            cylinder_pressure: Cylinder pressure (Pa)
            cylinder_temp: Cylinder temperature (K)
            lambda_value: Air-fuel ratio
            burn_fraction: Current burn progress
            
        Returns:
            True if knock is likely
        """
        # Knock is more likely at:
        # - High pressure
        # - High temperature
        # - Lean mixtures (faster flame speed = higher end-gas pressure)
        # - Early in combustion (high end-gas mass)
        
        if burn_fraction > 0.7:
            return False  # Too late in combustion
        
        # Simple knock criterion based on pressure and temperature
        # This is a simplified model - real knock prediction is complex
        knock_pressure_threshold = 3000000.0  # 30 bar
        knock_temp_threshold = 2500.0  # 2500 K
        
        pressure_factor = cylinder_pressure / knock_pressure_threshold
        temp_factor = cylinder_temp / knock_temp_threshold
        lambda_factor = 1.0 if lambda_value >= 1.0 else 0.8  # Lean more prone
        
        knock_score = pressure_factor * temp_factor * lambda_factor
        
        return knock_score > 1.0


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
        
        # Two-phase Wiebe function for burn rate
        # Phase 1: Premixed (rapid initial burn)
        # Phase 2: Diffusion (slower trailing burn)
        phase = min(1.0, dtheta / max(combustion.duration, 1e-6))
        
        # Premixed phase: a1=6.0, m1=1.0 (fast)
        x_b1 = 1.0 - math.exp(-6.0 * (phase ** 2.0))
        # Diffusion phase: a2=3.0, m2=0.5 (slower)
        x_b2 = 1.0 - math.exp(-3.0 * (phase ** 1.5))
        
        # Blend based on lambda: rich mixtures have more premixed, lean more diffusion
        # α = 0.6 for stoichiometric, higher for rich, lower for lean
        alpha = clamp01(0.6 + 0.2 * (1.0 - combustion.lambda_value))
        new_fraction = alpha * x_b1 + (1.0 - alpha) * x_b2
        
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
