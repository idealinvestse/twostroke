"""Thermodynamic calculations for engine gases.

Handles pressure calculations, mass flow computations,
and temperature changes from energy balance.
Includes enhanced thermodynamics with wall temperature dynamics
and variable cp/cv based on temperature and composition.
"""

import math
from dataclasses import dataclass
from typing import Tuple
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
    T_WALL_CYLINDER,
    T_WALL_CRANKCASE,
    HEAT_TRANSFER_COEF,
    BORE_M,
    STROKE_M,
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


class EnhancedThermodynamics:
    """Enhanced thermodynamics with wall temperature dynamics and improved heat transfer.
    
    Implements:
    - Dynamic wall temperature tracking for cylinder and crankcase
    - Flow-dependent heat transfer (Woschni correlation)
    - Variable cp/cv based on temperature and composition
    - Improved gas properties calculation
    
    Based on:
    - Woschni heat transfer correlation
    - NASA polynomial gas properties
    - Heywood's Internal Combustion Engine Fundamentals
    """
    
    def __init__(
        self,
        bore: float = BORE_M,
        stroke: float = STROKE_M,
    ) -> None:
        """Initialize enhanced thermodynamics model.
        
        Args:
            bore: Cylinder bore diameter (m)
            stroke: Piston stroke (m)
        """
        self.bore = bore
        self.stroke = stroke
        
        # Wall temperatures (dynamic)
        self.t_wall_cylinder = T_WALL_CYLINDER  # K
        self.t_wall_crankcase = T_WALL_CRANKCASE  # K
        
        # Wall thermal properties
        self.wall_thermal_mass = 0.5  # kg, effective thermal mass
        self.wall_specific_heat = 500.0  # J/(kg·K), steel
        
        # Heat transfer parameters
        self.base_htc_cylinder = HEAT_TRANSFER_COEF  # W/(m²·K)
        self.base_htc_crankcase = HEAT_TRANSFER_COEF * 0.5  # Lower for crankcase
        
        # Woschni parameters
        self.woschni_c1 = 2.28  # Constant term
        self.woschni_c2 = 0.308  # Piston velocity coefficient
        self.woschni_c3 = 0.00324  # Combustion-induced velocity coefficient
    
    def calculate_cylinder_area(self, piston_position: float) -> float:
        """Calculate instantaneous cylinder surface area.
        
        Args:
            piston_position: Piston position from TDC (m)
            
        Returns:
            Surface area (m²)
        """
        # Cylinder head area
        area_head = math.pi * (self.bore / 2) ** 2
        
        # Piston crown area (same as head)
        area_piston = area_head
        
        # Cylinder wall area (depends on piston position)
        area_wall = math.pi * self.bore * max(0.0, piston_position)
        
        return area_head + area_piston + area_wall
    
    def calculate_crankcase_area(self) -> float:
        """Calculate crankcase surface area (simplified).
        
        Returns:
            Surface area (m²)
        """
        # Simplified: approximate as box with cylinder dimensions
        volume = math.pi * (self.bore / 2) ** 2 * self.stroke
        characteristic_length = volume ** (1/3)
        return 6 * characteristic_length ** 2
    
    def update_wall_temperatures(
        self,
        dt: float,
        cylinder_gas_temp: float,
        crankcase_gas_temp: float,
        cylinder_heat_rate: float,
        crankcase_heat_rate: float,
    ) -> Tuple[float, float]:
        """Update wall temperatures based on heat transfer.
        
        Args:
            dt: Timestep (s)
            cylinder_gas_temp: Cylinder gas temperature (K)
            crankcase_gas_temp: Crankcase gas temperature (K)
            cylinder_heat_rate: Heat rate into cylinder wall from gas (W)
            crankcase_heat_rate: Heat rate into crankcase wall from gas (W)
            
        Returns:
            Tuple of (new_cylinder_wall_temp, new_crankcase_wall_temp)
        """
        # Heat capacity of walls
        thermal_capacity = self.wall_thermal_mass * self.wall_specific_heat
        
        # Update cylinder wall temperature
        # Heat from gas, cooling to ambient
        ambient_cooling_rate = 0.1 * (self.t_wall_cylinder - T_ATM)  # W
        net_heat_cylinder = cylinder_heat_rate - ambient_cooling_rate
        delta_t_cylinder = net_heat_cylinder * dt / thermal_capacity
        self.t_wall_cylinder += delta_t_cylinder
        
        # Clamp to reasonable range
        self.t_wall_cylinder = clamp(self.t_wall_cylinder, T_ATM + 20.0, 600.0)
        
        # Update crankcase wall temperature
        ambient_cooling_rate_cr = 0.05 * (self.t_wall_crankcase - T_ATM)  # W
        net_heat_crankcase = crankcase_heat_rate - ambient_cooling_rate_cr
        delta_t_crankcase = net_heat_crankcase * dt / thermal_capacity
        self.t_wall_crankcase += delta_t_crankcase
        
        # Clamp to reasonable range
        self.t_wall_crankcase = clamp(self.t_wall_crankcase, T_ATM + 10.0, 450.0)
        
        return self.t_wall_cylinder, self.t_wall_crankcase
    
    def calculate_woschni_htc(
        self,
        gas_temp: float,
        gas_pressure: float,
        wall_temp: float,
        piston_velocity: float,
        combustion_active: bool,
        cylinder_pressure: float = 0.0,
        pressure_m: float = 0.0,
    ) -> float:
        """Calculate heat transfer coefficient using Woschni correlation.
        
        Args:
            gas_temp: Gas temperature (K)
            gas_pressure: Gas pressure (Pa)
            wall_temp: Wall temperature (K)
            piston_velocity: Piston velocity (m/s)
            combustion_active: Whether combustion is active
            cylinder_pressure: Current cylinder pressure (Pa)
            pressure_m: Motored cylinder pressure at same crank angle (Pa)
            
        Returns:
            Heat transfer coefficient (W/(m²·K))
        """
        # Gas properties at mean temperature
        t_mean = (gas_temp + wall_temp) / 2.0
        
        # Thermal conductivity and viscosity (simplified)
        # For air at 300K: k ≈ 0.026 W/(m·K), μ ≈ 1.8e-5 Pa·s
        # Scale with temperature
        k = 0.026 * (t_mean / 300.0) ** 0.8
        mu = 1.8e-5 * (t_mean / 300.0) ** 0.7
        
        # Characteristic velocity
        if combustion_active and cylinder_pressure > 0 and pressure_m > 0:
            # Combustion-induced velocity
            w = (self.woschni_c1 + self.woschni_c2 * piston_velocity +
                  self.woschni_c3 * 1.0 *
                  (cylinder_pressure - pressure_m) / pressure_m)
        else:
            # Gas exchange phase
            w = self.woschni_c1 + self.woschni_c2 * abs(piston_velocity)
        
        # Woschni correlation
        # h = 3.26 * B^(-0.2) * p^0.8 * T^(-0.55) * w^0.8 * k^0.8 * mu^(-0.2)
        h = (3.26 * (self.bore ** -0.2) * (gas_pressure / 1e5) ** 0.8 *
             (t_mean ** -0.55) * (w ** 0.8) * (k ** 0.8) * (mu ** -0.2))
        
        return h
    
    def calculate_variable_cp_cv(
        self,
        temperature: float,
        burn_fraction: float,
        residual_fraction: float = 0.0,
    ) -> Tuple[float, float, float]:
        """Calculate variable cp, cv, gamma based on temperature and composition.
        
        Uses NASA polynomial correlations for:
        - Air (N2, O2 mixture)
        - Fuel (C8H18 vapor, simplified)
        - Burned gas (CO2, H2O, N2 mixture)
        
        Args:
            temperature: Gas temperature (K)
            burn_fraction: Fraction of gas that is burned (0-1)
            residual_fraction: Fraction that is residual burned gas (0-1)
            
        Returns:
            Tuple of (cp, cv, gamma)
        """
        # NASA polynomial coefficients (simplified)
        # For air (unburned): cp ≈ 1005 J/(kg·K) at 300K, increases with T
        # For burned gas: cp ≈ 1150 J/(kg·K) at high T
        
        t_scaled = temperature / 1000.0  # Scale to kK
        
        # Unburned mixture (air + fuel vapor)
        cp_unburned = 1005.0 * (1.0 + 0.1 * t_scaled)  # Increases with T
        cv_unburned = cp_unburned - R_GAS
        
        # Burned gas (products)
        cp_burned = 1150.0 * (1.0 + 0.05 * t_scaled)  # Increases with T
        cv_burned = cp_burned - R_GAS
        
        # Residual gas (already burned)
        cp_residual = cp_burned
        cv_residual = cv_burned
        
        # Interpolate based on composition
        # Total = fresh_unburned + fresh_burned + residual
        fresh_unburned = 1.0 - burn_fraction - residual_fraction
        fresh_burned = burn_fraction
        
        cp = (fresh_unburned * cp_unburned +
              fresh_burned * cp_burned +
              residual_fraction * cp_residual)
        
        cv = (fresh_unburned * cv_unburned +
              fresh_burned * cv_burned +
              residual_fraction * cv_residual)
        
        gamma = cp / cv if cv > 0 else GAMMA
        
        return cp, cv, gamma
