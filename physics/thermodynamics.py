"""Thermodynamic calculations for engine gases.

Handles pressure calculations, mass flow computations,
and temperature changes from energy balance.
"""

import math
from dataclasses import dataclass
from physics.constants import (
    R_GAS,
    GAMMA,
    C_V,
    MIN_PRESSURE,
    MIN_CRANKCASE_PRESSURE,
    MAX_CYLINDER_PRESSURE,
    MAX_CRANKCASE_PRESSURE,
    EPSILON_MASS,
    T_ATM,
)
from physics.utils import clamp


@dataclass
class GasProperties:
    """Temperature and composition-dependent gas properties."""
    gamma: float  # Heat capacity ratio
    c_v: float    # Specific heat at constant volume (J/(kg·K))
    c_p: float    # Specific heat at constant pressure (J/(kg·K))


def gas_properties(temperature: float, burn_fraction: float = 0.0) -> GasProperties:
    """Calculate gas properties based on temperature and burn fraction.

    Unburned mixture (air+fuel): γ ≈ 1.4 at 300K, decreasing with temperature.
    Burned gas: γ ≈ 1.25-1.30 at high temperature.
    Linear interpolation between states based on burn_fraction.

    Args:
        temperature: Gas temperature (K)
        burn_fraction: Fraction of gas that is burned (0-1)

    Returns:
        GasProperties with gamma, c_v, c_p
    """
    # Unburned mixture: γ varies from 1.4 (cold) to ~1.35 (hot)
    gamma_unburned = 1.4 - 0.05 * min(1.0, max(0.0, (temperature - 300.0)) / 2000.0)

    # Burned gas: γ varies from 1.32 (warm) to ~1.25 (very hot)
    gamma_burned = 1.32 - 0.07 * min(1.0, max(0.0, (temperature - 500.0)) / 2000.0)

    # Interpolate based on burn fraction
    gamma = gamma_unburned * (1.0 - burn_fraction) + gamma_burned * burn_fraction

    # Derive C_V and C_P from γ and R_GAS
    # R = C_P - C_V, γ = C_P / C_V → C_V = R / (γ - 1)
    c_v = R_GAS / (gamma - 1.0)
    c_p = c_v + R_GAS

    return GasProperties(gamma=gamma, c_v=c_v, c_p=c_p)


@dataclass
class GasState:
    """Thermodynamic state of a gas volume."""
    mass: float        # Total mass (kg)
    m_air: float       # Air mass (kg)
    m_fuel: float      # Fuel mass (kg)
    m_burned: float    # Burned gas mass (kg)
    temperature: float # Temperature (K)
    pressure: float    # Pressure (Pa)
    volume: float      # Volume (m³)


class Thermodynamics:
    """Thermodynamic calculations for ideal gas."""
    
    @staticmethod
    def calculate_pressure(mass: float, temperature: float, volume: float) -> float:
        """Calculate pressure from ideal gas law: P = mRT/V.
        
        Args:
            mass: Gas mass (kg)
            temperature: Temperature (K)
            volume: Volume (m³)
            
        Returns:
            Pressure (Pa)
        """
        volume = max(volume, 1e-9)
        return mass * R_GAS * temperature / volume
    
    @staticmethod
    def clamp_cylinder_pressure(pressure: float) -> float:
        """Clamp cylinder pressure to safe range."""
        return clamp(pressure, MIN_PRESSURE, MAX_CYLINDER_PRESSURE)
    
    @staticmethod
    def clamp_crankcase_pressure(pressure: float) -> float:
        """Clamp crankcase pressure to safe range."""
        return clamp(pressure, MIN_CRANKCASE_PRESSURE, MAX_CRANKCASE_PRESSURE)
    
    @staticmethod
    def flow_function(p_up: float, p_down: float) -> float:
        """Calculate compressible flow function (psi).
        
        Implements choked flow correction for pressure ratios
        below critical ratio.
        
        Args:
            p_up: Upstream pressure (Pa)
            p_down: Downstream pressure (Pa)
            
        Returns:
            Flow function value psi
        """
        if p_up <= 0:
            return 0.0
        
        pr = p_down / p_up
        if pr >= 1.0:
            return 0.0
        
        pr = max(pr, 0.001)
        
        # Critical pressure ratio for choked flow
        pr_crit = (2.0 / (GAMMA + 1.0)) ** (GAMMA / (GAMMA - 1.0))
        
        if pr < pr_crit:
            pr = pr_crit
        
        term = (pr ** (2.0 / GAMMA)) - (pr ** ((GAMMA + 1.0) / GAMMA))
        return math.sqrt(abs(2.0 * GAMMA / (GAMMA - 1.0) * max(0.0, term)) + 1e-9)
    
    @staticmethod
    def mass_flow(c_d: float, area: float, p_up: float, t_up: float, p_down: float) -> float:
        """Calculate mass flow rate through an orifice.
        
        Uses compressible flow equation with discharge coefficient.
        
        Args:
            c_d: Discharge coefficient (0-1)
            area: Flow area (m²)
            p_up: Upstream pressure (Pa)
            t_up: Upstream temperature (K)
            p_down: Downstream pressure (Pa)
            
        Returns:
            Mass flow rate (kg/s)
        """
        if p_up <= p_down or area <= 0:
            return 0.0
        
        psi = Thermodynamics.flow_function(p_up, p_down)
        return c_d * area * p_up / math.sqrt(R_GAS * max(1.0, t_up)) * psi
    
    @staticmethod
    def update_temperature_from_energy(
        current_temp: float,
        heat_added: float,
        mass: float,
        cv: float = C_V,
    ) -> float:
        """Update temperature based on energy addition.
        
        Args:
            current_temp: Current temperature (K)
            heat_added: Heat energy added (J)
            mass: Mass of gas (kg)
            cv: Specific heat at constant volume (J/(kg·K))
            
        Returns:
            New temperature (K)
        """
        mass = max(mass, EPSILON_MASS)
        delta_T = heat_added / (mass * cv)
        return max(T_ATM, current_temp + delta_T)
    
    @staticmethod
    def calculate_heat_transfer(
        gas_temp: float,
        wall_temp: float,
        heat_transfer_coeff: float,
        area: float,
    ) -> float:
        """Calculate convective heat transfer.
        
        Args:
            gas_temp: Gas temperature (K)
            wall_temp: Wall temperature (K)
            heat_transfer_coeff: h (W/(m²·K))
            area: Heat transfer area (m²)
            
        Returns:
            Heat transfer rate (W, positive = into gas)
        """
        return heat_transfer_coeff * area * (wall_temp - gas_temp)
