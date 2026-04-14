"""Carburetor model with venturi physics and fuel metering.

Implements:
- Venturi pressure drop for fuel suction
- Main jet and idle circuit fuel metering
- Throttle position effects on fuel delivery
- Temperature compensation (choke)

Based on:
- Standard carburetor physics (Bernoulli equation)
- Heywood's IC Engine Fundamentals
- Typical motorcycle carburetor designs
"""

import math
from dataclasses import dataclass
from physics.constants import P_ATM, T_ATM
from physics.utils import clamp01
from physics.fuel_drops import (
    DropletEnsemble, calculate_sauter_mean_diameter,
    FUEL_DENSITY
)

# Gas constants
AIR_GAMMA = 1.4  # Heat capacity ratio
AIR_R = 287.0    # J/(kg·K), specific gas constant

# Carburetor geometry defaults (typical 50cc motorcycle carburetor)
DEFAULT_VENTURI_DIAMETER = 0.018  # m (18mm, typical for 50cc)
DEFAULT_MAIN_JET_DIAMETER = 0.00085  # m (0.85mm, larger for richer 2-stroke mixture)
DEFAULT_IDLE_JET_DIAMETER = 0.0004  # m (0.4mm)
DEFAULT_THROTTLE_BORE = 0.020  # m (20mm)

# Flow coefficients
DISCHARGE_COEF_VENTURI = 0.95
DISCHARGE_COEF_FUEL_JET = 0.70
DISCHARGE_COEF_THROTTLE = 0.82


@dataclass
class CarburetorState:
    """Current state of carburetor."""
    p_venturi: float      # Venturi pressure (Pa)
    T_venturi: float      # Venturi temperature (K)
    v_air: float          # Air velocity in venturi (m/s)
    m_dot_air: float      # Air mass flow (kg/s)
    m_dot_fuel_main: float  # Main jet fuel flow (kg/s)
    m_dot_fuel_idle: float  # Idle circuit fuel flow (kg/s)
    throttle_angle: float  # Throttle plate angle (deg, 0=closed, 90=open)
    choke_position: float  # Choke enrichment (0-1, 0=off)
    
    @property
    def total_fuel_flow(self) -> float:
        return self.m_dot_fuel_main + self.m_dot_fuel_idle
    
    @property
    def fuel_air_ratio(self) -> float:
        total_fuel = self.total_fuel_flow
        if self.m_dot_air > 0:
            return total_fuel / self.m_dot_air
        return 0.0


@dataclass 
class FuelJetConfig:
    """Configuration for a fuel jet."""
    diameter: float       # Jet diameter (m)
    discharge_coef: float = DISCHARGE_COEF_FUEL_JET
    
    @property
    def area(self) -> float:
        return math.pi * (self.diameter / 2.0) ** 2


class CarburetorModel:
    """Physical carburetor model with venturi fuel suction.
    
    Models a typical slide-valve or butterfly carburetor with:
    - Venturi for air velocity increase and pressure drop
    - Main jet for wide-open throttle fuel delivery
    - Idle circuit for low-throttle fuel delivery
    - Needle valve for mid-range fuel mixture adjustment
    """
    
    def __init__(
        self,
        venturi_diameter: float = DEFAULT_VENTURI_DIAMETER,
        throttle_bore: float = DEFAULT_THROTTLE_BORE,
        main_jet_diameter: float = DEFAULT_MAIN_JET_DIAMETER,
        idle_jet_diameter: float = DEFAULT_IDLE_JET_DIAMETER,
        float_bowl_pressure: float = P_ATM,  # Fuel bowl is at atmospheric pressure
    ):
        """Initialize carburetor model.
        
        Args:
            venturi_diameter: Venturi throat diameter (m)
            throttle_bore: Throttle body bore diameter (m)
            main_jet_diameter: Main jet diameter (m)
            idle_jet_diameter: Idle jet diameter (m)
            float_bowl_pressure: Fuel bowl pressure (Pa, typically atmospheric)
        """
        self.venturi_diameter = venturi_diameter
        self.throttle_bore = throttle_bore
        self.float_bowl_pressure = float_bowl_pressure
        
        # Jet configurations
        self.main_jet = FuelJetConfig(diameter=main_jet_diameter)
        self.idle_jet = FuelJetConfig(diameter=idle_jet_diameter)
        
        # Needle position (0 = rich, 1 = lean)
        self.needle_position = 0.5
        
        # State
        self.state = CarburetorState(
            p_venturi=P_ATM,
            T_venturi=T_ATM,
            v_air=0.0,
            m_dot_air=0.0,
            m_dot_fuel_main=0.0,
            m_dot_fuel_idle=0.0,
            throttle_angle=0.0,
            choke_position=0.0,
        )
        
        # Fuel droplet ensemble
        self.droplet_ensemble = DropletEnsemble()
        
        # Temperature for fuel
        self.fuel_temperature = T_ATM
    
    def calculate_venturi_flow(
        self,
        p_upstream: float,
        T_upstream: float,
        throttle_position: float,
    ) -> tuple[float, float, float]:
        """Calculate air flow through venturi using compressible flow equations.
        
        Uses isentropic flow relations with discharge coefficient.
        
        Args:
            p_upstream: Upstream pressure (Pa, typically atmospheric)
            T_upstream: Upstream temperature (K)
            throttle_position: Throttle position (0-1, 0=closed, 1=open)
            
        Returns:
            Tuple of (m_dot_air, p_venturi, v_venturi)
        """
        # Venturi area
        venturi_area = math.pi * (self.venturi_diameter / 2.0) ** 2
        
        # Density upstream
        rho_upstream = p_upstream / (AIR_R * T_upstream)
        
        # Use simplified Bernoulli for carburetor flow
        # Throttle limits the flow, venturi creates pressure drop for fuel suction
        
        # First calculate flow limited by throttle
        m_dot_throttle = self._calculate_throttle_flow(
            p_upstream, T_upstream, rho_upstream, throttle_position
        )
        
        # Now calculate venturi pressure drop using Bernoulli
        # v_venturi = m_dot / (rho * A_venturi)
        # p_upstream - p_venturi = 0.5 * rho * v_venturi^2
        
        if venturi_area > 0 and m_dot_throttle > 0:
            v_venturi = m_dot_throttle / (rho_upstream * venturi_area * DISCHARGE_COEF_VENTURI)
            v_venturi = min(v_venturi, 150.0)  # Cap at 150 m/s (subsonic limit)
            
            # Pressure drop from Bernoulli (incompressible)
            dp_venturi = 0.5 * rho_upstream * v_venturi ** 2
            p_venturi = max(P_ATM * 0.6, p_upstream - dp_venturi)
            
            # Recalculate mass flow with actual venturi pressure
            # (This accounts for the extra pressure drop)
            rho_venturi = p_venturi / (AIR_R * T_upstream)
            m_dot = rho_venturi * v_venturi * venturi_area * DISCHARGE_COEF_VENTURI
            m_dot = min(m_dot, m_dot_throttle)
        else:
            m_dot = 0.0
            v_venturi = 0.0
            p_venturi = p_upstream
        
        return m_dot, p_venturi, v_venturi
    
    def _throttle_effective_area(self, throttle_position: float) -> float:
        """Calculate effective flow area through throttle.
        
        Args:
            throttle_position: 0-1, 0=closed, 1=open
            
        Returns:
            Effective area (m²)
        """
        # Full bore area
        full_area = math.pi * (self.throttle_bore / 2.0) ** 2
        
        # At low throttle openings, effective area is small
        # At throttle = 0, small leakage area
        # At throttle = 1, full area
        
        # Empirical: area increases non-linearly with throttle
        if throttle_position < 0.05:
            # Idle region: small gap around throttle plate
            leakage_area = full_area * 0.02
            return leakage_area + full_area * 0.3 * (throttle_position / 0.05)
        else:
            # Main region
            effective_fraction = 0.15 + 0.85 * throttle_position ** 1.5
            return full_area * effective_fraction
    
    def _calculate_throttle_flow(
        self,
        p_upstream: float,
        T_upstream: float,
        rho_upstream: float,
        throttle_position: float,
    ) -> float:
        """Calculate mass flow limited by throttle.
        
        Uses orifice flow equation.
        
        Args:
            p_upstream: Upstream pressure (Pa)
            T_upstream: Upstream temperature (K)
            rho_upstream: Upstream density (kg/m³)
            throttle_position: Throttle position (0-1)
            
        Returns:
            Mass flow rate (kg/s)
        """
        effective_area = self._throttle_effective_area(throttle_position)
        
        # Assume downstream is at some pressure (simplified)
        # In reality, downstream is crankcase pressure which varies
        p_downstream = P_ATM * 0.85  # Approximate suction
        
        if p_downstream >= p_upstream:
            return 0.0
        
        # Pressure ratio
        pressure_ratio = p_downstream / p_upstream
        
        # Choked flow check
        critical_ratio = (2.0 / (AIR_GAMMA + 1.0)) ** (AIR_GAMMA / (AIR_GAMMA - 1.0))
        
        if pressure_ratio <= critical_ratio:
            # Choked flow
            m_dot = (effective_area * p_upstream / math.sqrt(T_upstream)) * math.sqrt(
                AIR_GAMMA / AIR_R * (2.0 / (AIR_GAMMA + 1.0)) ** ((AIR_GAMMA + 1.0) / (AIR_GAMMA - 1.0))
            )
        else:
            # Subsonic flow
            m_dot = (effective_area * p_upstream / math.sqrt(T_upstream)) * math.sqrt(
                2.0 / AIR_R * (AIR_GAMMA / (AIR_GAMMA - 1.0)) *
                (pressure_ratio ** (2.0 / AIR_GAMMA) - pressure_ratio ** ((AIR_GAMMA + 1.0) / AIR_GAMMA))
            )
        
        return m_dot * DISCHARGE_COEF_THROTTLE
    
    def calculate_fuel_flow(
        self,
        p_venturi: float,
        m_dot_air: float,
        v_air: float,
        throttle_position: float,
    ) -> tuple[float, float, float]:
        """Calculate fuel flow through main and idle jets.
        
        Args:
            p_venturi: Venturi pressure (Pa)
            m_dot_air: Air mass flow (kg/s)
            v_air: Air velocity in venturi (m/s)
            throttle_position: Throttle position (0-1)
            
        Returns:
            Tuple of (m_dot_fuel_main, m_dot_fuel_idle, SMD)
        """
        # Pressure difference for fuel suction
        # Fuel bowl is at atmospheric, venturi is at lower pressure
        dp_fuel = self.float_bowl_pressure - p_venturi
        
        # Main jet flow (Torricelli's law: v = sqrt(2 * dp / ρ))
        if dp_fuel > 100.0:  # Minimum 100 Pa for fuel flow
            v_fuel_main = math.sqrt(2.0 * dp_fuel / FUEL_DENSITY)
            
            # Needle valve effect: needle position increases effective area
            # Needle position 0 (low/rich) = smaller effective area = less fuel? No...
            # Actually: needle position 0 (clip at top) = needle in further = smaller area = leaner
            # Needle position 1 (clip at bottom) = needle out more = larger area = richer
            needle_area_factor = 0.4 + 0.6 * (1.0 - self.needle_position)
            effective_main_area = self.main_jet.area * needle_area_factor
            
            m_dot_fuel_main = (effective_main_area * v_fuel_main * FUEL_DENSITY * 
                              self.main_jet.discharge_coef)
        else:
            m_dot_fuel_main = 0.0
        
        # Idle circuit flow
        # Idle circuit activates at low throttle openings
        if throttle_position < 0.25:
            idle_circuit_fraction = 1.0 - (throttle_position / 0.25)
            
            # Idle circuit uses air bleed for emulsion
            # Simplified: idle fuel flow proportional to idle fraction
            if dp_fuel > 50.0:
                v_fuel_idle = math.sqrt(2.0 * dp_fuel * 0.5 / FUEL_DENSITY)  # 0.5 factor for air bleed
                m_dot_fuel_idle = (self.idle_jet.area * v_fuel_idle * FUEL_DENSITY * 
                                  self.idle_jet.discharge_coef * idle_circuit_fraction)
            else:
                m_dot_fuel_idle = 0.0
        else:
            m_dot_fuel_idle = 0.0
        
        # Calculate Sauter Mean Diameter for atomization
        # Higher air velocity → better atomization (smaller droplets)
        smd = calculate_sauter_mean_diameter(v_air, dp_fuel, is_injection=False)
        
        return m_dot_fuel_main, m_dot_fuel_idle, smd
    
    def update(
        self,
        dt: float,
        p_upstream: float,
        T_upstream: float,
        throttle_position: float,
        choke_position: float = 0.0,
    ) -> CarburetorState:
        """Update carburetor state for one timestep.
        
        Calculates air and fuel flow, generates fuel droplets.
        
        Args:
            dt: Timestep (s)
            p_upstream: Upstream pressure (Pa)
            T_upstream: Upstream temperature (K)
            throttle_position: Throttle position (0-1)
            choke_position: Choke enrichment (0-1, 0=off, 1=full choke)
            
        Returns:
            Updated CarburetorState
        """
        # Calculate air flow through venturi
        m_dot_air, p_venturi, v_air = self.calculate_venturi_flow(
            p_upstream, T_upstream, throttle_position
        )
        
        # Temperature at venturi (adiabatic cooling)
        T_venturi = T_upstream * (p_venturi / p_upstream) ** ((AIR_GAMMA - 1.0) / AIR_GAMMA)
        
        # Calculate fuel flow
        m_dot_fuel_main, m_dot_fuel_idle, smd = self.calculate_fuel_flow(
            p_venturi, m_dot_air, v_air, throttle_position
        )
        
        # Apply choke enrichment
        if choke_position > 0:
            # Choke richens mixture by 10-40% depending on position
            enrichment = 1.0 + 0.4 * choke_position
            m_dot_fuel_main *= enrichment
            m_dot_fuel_idle *= enrichment
        
        # Update state
        self.state = CarburetorState(
            p_venturi=p_venturi,
            T_venturi=T_venturi,
            v_air=v_air,
            m_dot_air=m_dot_air,
            m_dot_fuel_main=m_dot_fuel_main,
            m_dot_fuel_idle=m_dot_fuel_idle,
            throttle_angle=throttle_position * 90.0,
            choke_position=choke_position,
        )
        
        # Generate fuel droplets from total fuel flow
        total_fuel = m_dot_fuel_main + m_dot_fuel_idle
        if total_fuel > 0:
            self.droplet_ensemble.add_droplets(
                total_mass=total_fuel * dt,
                mean_diameter=smd,
                T_fuel=self.fuel_temperature,
                velocity=v_air * 0.1  # Initial slip velocity
            )
        
        return self.state
    
    def update_droplets(
        self,
        dt: float,
        p_gas: float,
        T_gas: float,
        v_gas: float,
        wall_position: float = None,
    ) -> tuple[float, float, float]:
        """Update fuel droplet evaporation and movement.
        
        Args:
            dt: Timestep (s)
            p_gas: Gas pressure (Pa)
            T_gas: Gas temperature (K)
            v_gas: Gas velocity (m/s)
            wall_position: Optional wall position for impingement
            
        Returns:
            Tuple of (vaporized_mass, wall_film_mass, remaining_liquid_mass)
        """
        return self.droplet_ensemble.update_all(
            dt, p_gas, T_gas, v_gas, wall_position
        )
    
    def get_droplet_statistics(self) -> dict:
        """Get fuel droplet ensemble statistics."""
        return self.droplet_ensemble.get_statistics()
    
    def set_needle_position(self, position: float) -> None:
        """Set needle valve position (0=rich, 1=lean).
        
        Args:
            position: Needle position 0-1
        """
        self.needle_position = clamp01(position)
    
    def set_fuel_temperature(self, temperature: float) -> None:
        """Set fuel temperature (affects vapor pressure and evaporation).
        
        Args:
            temperature: Fuel temperature (K)
        """
        self.fuel_temperature = temperature
