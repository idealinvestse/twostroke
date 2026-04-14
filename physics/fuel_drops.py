"""Fuel droplet model for realistic fuel-air mixing.

Implements fuel droplet physics including:
- Droplet size distribution (log-normal or Rosin-Rammler)
- Aerodynamic drag and slip velocity
- Evaporation using Spalding model
- Wall impingement and fuel film formation

Based on:
- Spalding droplet evaporation model
- Heywood's IC Engine Fundamentals (Chapter 10)
- SAE papers on fuel spray characterization
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple
from physics.constants import T_ATM, R_GAS
from physics.utils import clamp

# Fuel properties for gasoline
FUEL_DENSITY = 750.0  # kg/m³ at 20°C
FUEL_VAPOR_PRESSURE = 7000.0  # Pa at 20°C (typical for gasoline)
FUEL_SURFACE_TENSION = 0.026  # N/m at 20°C
FUEL_LATENT_HEAT = 380_000.0  # J/kg
FUEL_MOLAR_MASS = 0.114  # kg/mol (iso-octane C8H18)
FUEL_BOLING_POINT = 398.0  # K (125°C)
FUEL_SPECIFIC_HEAT_LIQUID = 2200.0  # J/(kg·K)

# Air properties
AIR_VISCOSITY = 1.8e-5  # Pa·s at 20°C
AIR_THERMAL_CONDUCTIVITY = 0.026  # W/(m·K)
AIR_DIFFUSIVITY = 2.5e-5  # m²/s (mass diffusivity of fuel vapor in air)

# Typical droplet sizes for different fuel delivery methods
SAUTER_MEAN_CARBURETOR = 100e-6  # 100 μm for typical carburetor
SAUTER_MEAN_INJECTION = 40e-6    # 40 μm for fuel injection
DROPLET_SPREAD_FACTOR = 2.5       # Standard deviation for log-normal distribution


@dataclass
class FuelDrop:
    """Single fuel droplet state."""
    mass: float           # kg
    diameter: float       # m
    velocity: float       # m/s, slip velocity relative to gas
    position: float       # m, axial position in intake/crankcase
    temperature: float    # K
    vapor_fraction: float # 0-1, fraction vaporized (1.0 = fully vapor)
    
    def __post_init__(self):
        if self.vapor_fraction >= 1.0:
            self.mass = 0.0
            self.vapor_fraction = 1.0
    
    @property
    def radius(self) -> float:
        return self.diameter / 2.0
    
    @property
    def surface_area(self) -> float:
        return math.pi * self.diameter * self.diameter
    
    @property
    def is_vaporized(self) -> bool:
        return self.vapor_fraction >= 0.999
    
    @property
    def is_liquid(self) -> bool:
        return not self.is_vaporized and self.mass > 1e-12
    
    @property
    def remaining_liquid_mass(self) -> float:
        return self.mass * (1.0 - self.vapor_fraction)
    
    def calculate_evaporation_rate(self, p_gas: float, T_gas: float, v_gas: float) -> float:
        """Calculate evaporation rate using Spalding model.
        
        Returns kg/s of fuel evaporating.
        
        Args:
            p_gas: Gas pressure (Pa)
            T_gas: Gas temperature (K)
            v_gas: Gas velocity relative to droplet (m/s)
        """
        if self.is_vaporized or self.remaining_liquid_mass < 1e-12:
            return 0.0
        
        # Fuel temperature (limited by boiling point)
        T_fuel = min(self.temperature, FUEL_BOLING_POINT)
        
        # Saturation vapor pressure at fuel surface (Antoine equation approximation)
        # log10(P) = A - B/(C + T), simplified here
        T_celsius = T_fuel - 273.15
        if T_celsius > 0:
            P_sat = 10 ** (6.9 - 1349.0 / (217.0 + T_celsius)) * 133.322  # Convert mmHg to Pa
        else:
            P_sat = FUEL_VAPOR_PRESSURE * (T_fuel / T_ATM)
        
        P_sat = clamp(P_sat, 1.0, p_gas * 0.95)  # Cannot exceed total pressure
        
        # Mass fraction of fuel vapor at surface (Clausius-Clapeyron)
        Y_s = (P_sat * FUEL_MOLAR_MASS) / (p_gas * 0.02897)  # 0.02897 = air molar mass
        Y_s = clamp(Y_s, 0.0, 1.0)
        
        # Far-field vapor fraction (assume 0 for fresh intake air)
        Y_inf = 0.0
        
        # Spalding mass transfer number
        if Y_s >= 1.0 - 1e-9:
            B_m = 1000.0  # Very high evaporation
        else:
            B_m = (Y_s - Y_inf) / (1.0 - Y_s)
        B_m = max(0.01, B_m)  # Ensure some evaporation even at low temps
        
        # Gas properties at film temperature
        T_film = 0.5 * (T_fuel + T_gas)
        
        # Schmidt number (ν/D)
        rho_gas = p_gas / (R_GAS * T_film)
        nu = AIR_VISCOSITY / rho_gas
        Sc = nu / AIR_DIFFUSIVITY
        
        # Reynolds number based on slip velocity
        Re = rho_gas * abs(v_gas) * self.diameter / AIR_VISCOSITY
        Re = max(0.1, Re)  # Minimum Reynolds number
        
        # Nusselt number for mass transfer (Sherwood number analogy)
        # Nu_m = 2 + 0.6 * Re^0.5 * Sc^0.33
        Sh = 2.0 + 0.6 * (Re ** 0.5) * (Sc ** (1.0/3.0))
        
        # Evaporation rate: m_dot = π * d * ρ_g * D * Sh * ln(1 + B_m)
        # Using Spalding's formula
        m_dot = math.pi * self.diameter * AIR_DIFFUSIVITY * rho_gas * Sh * math.log(1.0 + B_m)
        
        # Limit by remaining liquid mass
        max_evap = self.remaining_liquid_mass / 0.001  # At least 1ms to fully evaporate
        
        return clamp(m_dot, 0.0, max_evap)
    
    def update(self, dt: float, p_gas: float, T_gas: float, v_gas: float) -> float:
        """Update droplet state over timestep.
        
        Returns mass of fuel vaporized this step (kg).
        
        Args:
            dt: Timestep (s)
            p_gas: Gas pressure (Pa)
            T_gas: Gas temperature (K)
            v_gas: Gas velocity relative to droplet (m/s)
        """
        if self.is_vaporized:
            return 0.0
        
        # Calculate evaporation rate
        m_dot = self.calculate_evaporation_rate(p_gas, T_gas, v_gas)
        
        # Evaporated mass this step
        dm_evap = m_dot * dt
        dm_evap = min(dm_evap, self.remaining_liquid_mass)
        
        if dm_evap > 0:
            # Update vapor fraction
            new_vapor_mass = self.mass * self.vapor_fraction + dm_evap
            self.vapor_fraction = new_vapor_mass / self.mass
            
            # Droplet cooling from evaporation
            cooling = dm_evap * FUEL_LATENT_HEAT / (self.mass * FUEL_SPECIFIC_HEAT_LIQUID)
            self.temperature -= cooling
            
            # Heat transfer from gas to droplet
            # Simplified: droplet approaches gas temperature
            temp_rate = 0.1 / max(dt, 1e-6)  # Time constant ~0.1s
            dT = (T_gas - self.temperature) * temp_rate * dt
            self.temperature += dT
        
        return dm_evap
    
    def check_wall_impingement(self, wall_position: float) -> bool:
        """Check if droplet has hit a wall.
        
        Args:
            wall_position: Position of wall (m)
            
        Returns:
            True if droplet has hit wall
        """
        # Simplified: droplets with position >= wall_position hit wall
        return self.position >= wall_position and not self.is_vaporized


@dataclass
class DropletEnsemble:
    """Collection of fuel droplets."""
    droplets: List[FuelDrop] = field(default_factory=list)
    
    def add_droplets(self, total_mass: float, mean_diameter: float, 
                     T_fuel: float, velocity: float = 0.0) -> None:
        """Generate droplet population from log-normal distribution.
        
        Args:
            total_mass: Total fuel mass to distribute (kg)
            mean_diameter: Sauter mean diameter (m)
            T_fuel: Initial fuel temperature (K)
            velocity: Initial slip velocity (m/s)
        """
        if total_mass <= 0:
            return
        
        # Number of droplets: target ~100-1000 for performance
        # Calculate typical droplet mass
        typical_volume = (math.pi / 6.0) * (mean_diameter ** 3)
        typical_mass = typical_volume * FUEL_DENSITY
        
        n_droplets = max(50, min(500, int(total_mass / typical_mass)))

        # Log-normal distribution parameters
        # ln(d) ~ N(μ, σ²) where σ = ln(spread_factor)
        sigma_ln = math.log(DROPLET_SPREAD_FACTOR)
        mu_ln = math.log(mean_diameter) - 0.5 * sigma_ln * sigma_ln
        
        for _ in range(n_droplets):
            # Sample from log-normal
            u = random.gauss(0.0, 1.0)
            d_sample = math.exp(mu_ln + sigma_ln * u)
            
            # Clamp to realistic range
            d_sample = clamp(d_sample, 5e-6, 500e-6)  # 5-500 μm
            
            # Adjust mass to maintain total
            volume = (math.pi / 6.0) * (d_sample ** 3)
            mass = volume * FUEL_DENSITY
            
            # Position: start at 0 (intake/carburetor)
            position = 0.0
            
            droplet = FuelDrop(
                mass=mass,
                diameter=d_sample,
                velocity=velocity,
                position=position,
                temperature=T_fuel,
                vapor_fraction=0.0
            )
            self.droplets.append(droplet)
    
    def update_all(self, dt: float, p_gas: float, T_gas: float, v_gas: float,
                   wall_position: float = None) -> Tuple[float, float, float]:
        """Update all droplets and return mass balance.
        
        Returns tuple of (vaporized_mass, wall_film_mass, remaining_liquid_mass).
        
        Args:
            dt: Timestep (s)
            p_gas: Gas pressure (Pa)
            T_gas: Gas temperature (K)
            v_gas: Gas velocity (m/s)
            wall_position: Optional wall position for impingement (m)
        """
        vaporized_total = 0.0
        wall_film_total = 0.0
        
        remaining_droplets = []
        
        for drop in self.droplets:
            if drop.is_vaporized:
                continue
            
            # Update droplet (evaporation) first
            dm_vap = drop.update(dt, p_gas, T_gas, v_gas - drop.velocity)
            vaporized_total += dm_vap
            
            # Move droplet with gas flow
            # Slip velocity relaxes toward gas velocity
            slip_relaxation = 0.5  # Time constant for velocity matching
            drop.velocity += (v_gas - drop.velocity) * slip_relaxation * dt
            drop.position += (v_gas - drop.velocity) * dt
            
            # Check wall impingement AFTER moving
            if wall_position is not None and drop.check_wall_impingement(wall_position):
                # Large droplets (>50μm) contribute to wall film
                # Small droplets bounce or evaporate on contact
                if drop.diameter > 50e-6:
                    wall_film_total += drop.remaining_liquid_mass
                else:
                    # Small droplets partially evaporate on hot wall
                    evap_on_wall = drop.remaining_liquid_mass * 0.5
                    vaporized_total += evap_on_wall
                    wall_film_total += drop.remaining_liquid_mass - evap_on_wall
                continue
            
            if not drop.is_vaporized:
                remaining_droplets.append(drop)
        
        self.droplets = remaining_droplets
        
        remaining_liquid = sum(d.remaining_liquid_mass for d in self.droplets)
        
        return vaporized_total, wall_film_total, remaining_liquid
    
    def get_statistics(self) -> dict:
        """Get droplet ensemble statistics."""
        if not self.droplets:
            return {
                'count': 0,
                'mean_diameter': 0.0,
                'total_liquid_mass': 0.0,
                'vaporized_fraction': 1.0
            }
        
        liquid_droplets = [d for d in self.droplets if not d.is_vaporized]
        
        if not liquid_droplets:
            return {
                'count': 0,
                'mean_diameter': 0.0,
                'total_liquid_mass': 0.0,
                'vaporized_fraction': 1.0
            }
        
        total_mass = sum(d.mass for d in self.droplets)
        total_vaporized = sum(d.mass * d.vapor_fraction for d in self.droplets)
        total_liquid = sum(d.remaining_liquid_mass for d in liquid_droplets)
        
        # Sauter mean diameter: d32 = Σ(d³) / Σ(d²)
        sum_d3 = sum(d.diameter ** 3 for d in liquid_droplets)
        sum_d2 = sum(d.diameter ** 2 for d in liquid_droplets)
        d32 = sum_d3 / max(sum_d2, 1e-18)
        
        return {
            'count': len(liquid_droplets),
            'mean_diameter': d32,
            'total_liquid_mass': total_liquid,
            'vaporized_fraction': total_vaporized / max(total_mass, 1e-18)
        }


def calculate_sauter_mean_diameter(air_velocity: float, fuel_pressure: float,
                                   is_injection: bool = False) -> float:
    """Calculate expected Sauter Mean Diameter (SMD) for given conditions.
    
    Uses empirical correlations based on:
    - For carburetor: function of air velocity and fuel pressure drop
    - For injection: function of injection pressure
    
    Args:
        air_velocity: Air velocity at fuel entry point (m/s)
        fuel_pressure: Fuel pressure relative to ambient (Pa)
        is_injection: True for fuel injection, False for carburetor
        
    Returns:
        Sauter Mean Diameter in meters
    """
    if is_injection:
        # Injection: SMD decreases with higher injection pressure
        # Typical: 200 bar injection → ~20 μm
        #          50 bar injection → ~35 μm
        #          5 bar injection → ~60 μm
        dp_bar = max(fuel_pressure / 1e5, 0.5)  # Convert to bar, minimum 0.5 bar
        # Scale so at 50 bar we get ~35μm
        smd_um = 50.0 * (20.0 / dp_bar) ** 0.35
    else:
        # Carburetor: SMD depends on air velocity and fuel pressure
        # Higher air velocity → better atomization (smaller droplets)
        # Higher fuel pressure → slightly smaller droplets
        
        # Base SMD for typical carburetor conditions
        base_smd = 120.0  # μm
        
        # Air velocity effect: 30-80 m/s typical in carburetor venturi
        v_eff = clamp(air_velocity, 10.0, 150.0)
        velocity_factor = (50.0 / v_eff) ** 0.5
        
        # Fuel pressure effect: 5-50 kPa typical
        dp_kpa = fuel_pressure / 1000.0
        pressure_factor = 1.0 - 0.1 * clamp(dp_kpa / 30.0, 0.0, 1.0)
        
        smd_um = base_smd * velocity_factor * pressure_factor
    
    # Clamp to realistic range
    smd_um = clamp(smd_um, 10.0, 300.0)
    
    return smd_um * 1e-6  # Convert to meters
