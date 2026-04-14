"""Cylinder class for modular engine physics.
Encapsulates state and logic for a single cylinder.
"""

import math
from dataclasses import dataclass
from physics.constants import (
    R_GAS, P_ATM, T_ATM,
    MIN_PRESSURE, MAX_CYLINDER_PRESSURE,
    EPSILON_VOLUME,
    T_WALL_CYLINDER,
    FUEL_LHV, STOICH_AFR,
    BORE_M,
)
from physics.utils import clamp, clamp01
from physics.combustion import CombustionModel, AdvancedCombustionModel

@dataclass
class CylinderState:
    """Current state of a cylinder for reporting."""
    p_cyl: float
    T_cyl: float
    m_air: float
    m_fuel: float
    m_burned: float
    x: float
    burn_fraction: float
    combustion_active: bool
    spark_active: bool

class Cylinder:
    """A single engine cylinder unit."""
    
    def __init__(self, cylinder_id: int, crank_offset: float = 0.0):
        self.id = cylinder_id
        self.crank_offset = crank_offset  # rad
        
        # State variables
        self.m_air = 0.0
        self.m_fuel = 0.0
        self.m_burned = 0.0
        self.T_cyl = T_ATM
        self.fuel_film = 0.0
        self.p_cyl = P_ATM
        
        # Combustion state
        self.combustion_active = False
        self.burn_fraction = 0.0
        self.theta_ign = 0.0
        self.lambda_value = 1.0
        self.spark_active = False
        self.combustion_state = None  # Store CombustionState between calls
        
        # Initialize
        self._initialize_masses()

    def _initialize_masses(self) -> None:
        """Initial cylinder state."""
        # Assume some residual gas at start
        # This is a simplification; ideally depends on initial volume
        m_initial = 1e-4 # Placeholder, will be corrected on first step
        self.m_burned = m_initial * 0.12
        self.m_air = m_initial - self.m_burned
        self.m_fuel = 0.0

    def calculate_pressure(self, volume: float) -> float:
        """Calculate and update cylinder pressure."""
        m_total = self.m_air + self.m_fuel + self.m_burned
        v_clamped = max(volume, EPSILON_VOLUME)
        self.p_cyl = (m_total * R_GAS * self.T_cyl) / v_clamped
        self.p_cyl = clamp(self.p_cyl, MIN_PRESSURE, MAX_CYLINDER_PRESSURE)
        return self.p_cyl

    def update_combustion(self, theta: float, x: float, dt: float, 
                          ignition_angle_deg: float, ignition_enabled: bool, 
                          fuel_cutoff: bool, throttle_factor: float, omega: float = 90.0,
                          advanced_combustion_model = None,
                          residual_fraction: float = 0.0,
                          charge_purity: float = 0.0,
                          charge_temperature: float = 293.15) -> float:
        """Update combustion state and return heat released (J).
        
        Args:
            advanced_combustion_model: Optional AdvancedCombustionModel for residual-sensitive combustion
            residual_fraction: Residual gas fraction (0-1)
            charge_purity: Charge purity from scavenging (0-1)
            charge_temperature: Initial charge temperature (K)
        """
        theta_eff = (theta + self.crank_offset) % (2 * math.pi)
        theta_deg = math.degrees(theta_eff) % 360.0
        fresh_mass = self.m_air + self.m_fuel
        
        # Check for ignition
        can_ignite = CombustionModel.can_ignite(
            theta_deg=theta_deg,
            ignition_angle_deg=ignition_angle_deg,
            combustion_active=self.combustion_active,
            x=x,
            fresh_mass=fresh_mass,
            ignition_enabled=ignition_enabled,
            fuel_cutoff=fuel_cutoff,
        )
        
        if can_ignite:
            self.combustion_active = True
            self.spark_active = True
            
            # Use advanced combustion model if provided
            if advanced_combustion_model is not None:
                # Calculate lambda
                actual_fuel_air_ratio = self.m_fuel / max(1e-9, self.m_air)
                lambda_value = (1.0 / max(1e-9, actual_fuel_air_ratio)) / STOICH_AFR
                
                # Calculate efficiency with residual sensitivity
                efficiency = advanced_combustion_model.calculate_combustion_efficiency(
                    lambda_value=lambda_value,
                    residual_fraction=residual_fraction,
                    charge_purity=charge_purity,
                    ignition_angle_deg=ignition_angle_deg,
                )
                
                # Calculate burn duration with temperature effects
                turbulence = 0.65 + 0.70 * throttle_factor + 0.25 * clamp01(abs(omega) / 260.0)
                turbulence = max(0.1, turbulence)
                duration_deg = 55.0 / turbulence
                
                # Lambda affects burn duration
                if lambda_value < 0.85:
                    duration_deg *= 1.10
                elif lambda_value > 1.10:
                    duration_deg *= 1.25
                
                # Temperature affects burn duration
                temp_factor = 1.0 + 0.001 * max(0.0, charge_temperature - T_ATM)
                duration_deg /= temp_factor
                
                duration = math.radians(max(18.0, min(65.0, duration_deg)))
                
                # Fuel that actually burns
                available_fuel = min(self.m_fuel, self.m_air / STOICH_AFR)
                combustible_fuel = available_fuel * min(1.0, 0.70 + 0.30 * efficiency)
                
                # Use advanced combustion state
                from physics.combustion import CombustionState
                self.combustion_state = CombustionState(
                    active=True,
                    burn_fraction=0.0,
                    theta_ign=theta_eff,
                    duration=duration,
                    efficiency=efficiency,
                    lambda_value=lambda_value,
                    available_fuel=combustible_fuel,
                    residual_fraction=residual_fraction,
                    charge_temperature=charge_temperature,
                )
            else:
                # Legacy model
                self.combustion_state = CombustionModel.start_combustion(
                    theta=theta_eff,
                    m_fuel_cyl=self.m_fuel,
                    m_air_cyl=self.m_air,
                    throttle_factor=throttle_factor,
                    ignition_angle_deg=ignition_angle_deg,
                    omega=omega,
                )
            
            self.burn_fraction = self.combustion_state.burn_fraction
            self.theta_ign = self.combustion_state.theta_ign
            self.lambda_value = self.combustion_state.lambda_value
            self.combustion_active = self.combustion_state.active
        else:
            self.spark_active = False
            
        heat_released = 0.0
        if self.combustion_active and self.combustion_state is not None:
            # Use advanced model with variable Wiebe parameters if available
            if advanced_combustion_model is not None and hasattr(self.combustion_state, 'residual_fraction'):
                # Calculate variable Wiebe parameters based on current conditions
                a1, m1, a2, m2, alpha = advanced_combustion_model.calculate_wiebe_parameters(
                    lambda_value=self.combustion_state.lambda_value,
                    residual_fraction=self.combustion_state.residual_fraction,
                    charge_temp=self.combustion_state.charge_temperature,
                    charge_purity=charge_purity,
                )
                
                # Calculate progress with variable parameters
                dtheta = (theta_eff - self.combustion_state.theta_ign) % (2 * math.pi)
                
                if dtheta >= self.combustion_state.duration:
                    # Combustion complete
                    from physics.combustion import CombustionState
                    self.combustion_state = CombustionState(
                        active=False,
                        burn_fraction=1.0,
                        theta_ign=self.combustion_state.theta_ign,
                        duration=self.combustion_state.duration,
                        efficiency=self.combustion_state.efficiency,
                        lambda_value=self.combustion_state.lambda_value,
                        available_fuel=0.0,
                        residual_fraction=self.combustion_state.residual_fraction,
                        charge_temperature=self.combustion_state.charge_temperature,
                    )
                else:
                    # Two-phase Wiebe with variable parameters
                    phase = min(1.0, dtheta / max(self.combustion_state.duration, 1e-6))
                    x_b1 = 1.0 - math.exp(-a1 * (phase ** m1))
                    x_b2 = 1.0 - math.exp(-a2 * (phase ** m2))
                    new_fraction = alpha * x_b1 + (1.0 - alpha) * x_b2
                    delta_fraction = max(0.0, new_fraction - self.combustion_state.burn_fraction)
                    
                    # Calculate fuel burned
                    fuel_burned = min(
                        self.combustion_state.available_fuel * delta_fraction,
                        self.m_fuel
                    )
                    
                    # Calculate air consumed
                    air_consumed = fuel_burned * STOICH_AFR
                    if air_consumed > self.m_air:
                        air_consumed = self.m_air
                        fuel_burned = air_consumed / STOICH_AFR
                    
                    # Calculate heat release
                    heat_released = fuel_burned * FUEL_LHV
                    
                    # Update state
                    self.combustion_state.burn_fraction = new_fraction
                    
                    # Update masses
                    self.m_fuel -= fuel_burned
                    self.m_air -= air_consumed
                    self.m_burned += fuel_burned + air_consumed
            else:
                # Legacy model
                self.combustion_state, heat_released = CombustionModel.update_combustion(
                    combustion=self.combustion_state,
                    theta=theta_eff,
                    m_fuel_cyl=self.m_fuel,
                    m_air_cyl=self.m_air,
                    dt=dt,
                )
                
                if heat_released > 0:
                    fuel_burned = heat_released / FUEL_LHV
                    air_consumed = fuel_burned * STOICH_AFR
                    
                    if air_consumed > self.m_air:
                        air_consumed = self.m_air
                        fuel_burned = air_consumed / STOICH_AFR
                        heat_released = fuel_burned * FUEL_LHV
                    
                    self.m_fuel -= fuel_burned
                    self.m_air -= air_consumed
                    self.m_burned += fuel_burned + air_consumed
            
            self.combustion_active = self.combustion_state.active
            self.burn_fraction = self.combustion_state.burn_fraction
            
            # Reset burn_fraction when combustion completes for next cycle
            if not self.combustion_state.active:
                self.burn_fraction = 0.0
            
            if heat_released > 0:
                fuel_burned = heat_released / FUEL_LHV
                air_consumed = fuel_burned * STOICH_AFR
                
                if air_consumed > self.m_air:
                    air_consumed = self.m_air
                    fuel_burned = air_consumed / STOICH_AFR
                    heat_released = fuel_burned * FUEL_LHV
                
                self.m_fuel -= fuel_burned
                self.m_air -= air_consumed
                self.m_burned += fuel_burned + air_consumed
                
        return heat_released

    def apply_cooling(self, dt: float, p_cyl: float = P_ATM,
                       v_piston: float = 0.0, combustion_active: bool = False) -> None:
        """Apply Woschni convective heat transfer to cylinder walls.
        
        Uses the Woschni correlation:
        h = 3.26 * B^(-0.2) * p^(0.8) * T^(-0.55) * w^(0.8)
        
        where w (gas velocity) depends on the phase:
        - Gas exchange: w = 6*(1 + 0.5*|v_piston|/v_bar)
        - Compression: w = 2.28 + 0.308*v_piston/v_bar
        - Combustion/expansion: w = 2.28 + 0.308*v_piston/v_bar + f*(p-p_m)/(p_m)
        
        Args:
            dt: Timestep (s)
            p_cyl: Cylinder pressure (Pa)
            v_piston: Piston velocity (m/s)
            combustion_active: Whether combustion is active
        """
        B = BORE_M  # Bore diameter (m)
        T = max(T_ATM, self.T_cyl)
        p = max(P_ATM, p_cyl)
        
        # Mean piston speed reference (typical 50cc at 8000 RPM)
        v_bar = 8.0  # m/s reference speed
        
        # Gas velocity term depends on engine phase
        if combustion_active:
            # Combustion/expansion phase: includes pressure-rise driven velocity
            w = 2.28 + 0.308 * abs(v_piston) / v_bar + 3.0 * 0.003 * v_bar
        else:
            # Gas exchange / compression phase
            w = 6.0 * (1.0 + 0.5 * abs(v_piston) / v_bar)
        
        w = max(w, 0.1)  # Minimum gas velocity
        
        # Woschni heat transfer coefficient (scaled for small 50cc engine)
        # Original Woschni is for automotive-scale; small engines have higher
        # surface-to-volume ratio but lower absolute heat transfer
        h_woschni = 3.26 * (B ** (-0.2)) * (p ** 0.8) * (T ** (-0.55)) * (w ** 0.8)
        h_woschni *= 0.15  # Scale factor for 50cc 2-stroke (reduced from automotive)
        
        # Heat transfer area: cylinder head + piston crown (bore area only)
        # For small 2-stroke, liner area is partially covered by ports
        A_heat = math.pi * B * B / 4.0 * 2.0  # Head + piston crown
        
        # Heat loss (positive = heat leaving gas)
        dQ_cool = h_woschni * A_heat * (T - T_WALL_CYLINDER) * dt
        
        # Convert to temperature change
        m_total = max(1e-9, self.m_air + self.m_fuel + self.m_burned)
        from physics.thermodynamics import gas_properties
        burn_frac = self.m_burned / m_total
        gas = gas_properties(self.T_cyl, burn_frac)
        dT_cool = dQ_cool / (m_total * gas.c_v)
        self.T_cyl -= dT_cool
    
    def add_transfer_with_fuel_film(self, transferred_air: float, transferred_fuel: float, 
                                    transferred_burned: float, throttle_factor: float) -> None:
        """Add transferred charge with cylinder fuel film capture.
        
        Args:
            transferred_air: Air mass transferred (kg)
            transferred_fuel: Fuel mass transferred (kg)
            transferred_burned: Burned gas mass transferred (kg)
            throttle_factor: Throttle position factor (0-1)
        """
        self.m_air += transferred_air
        self.m_burned += transferred_burned
        
        # Capture portion of fuel as cylinder fuel film (wet fuel)
        cylinder_wet_fraction = max(0.05, 0.25 - 0.005 * max(0.0, self.T_cyl - T_ATM))
        cylinder_film_added = transferred_fuel * cylinder_wet_fraction
        self.fuel_film += cylinder_film_added
        self.m_fuel += transferred_fuel - cylinder_film_added
    
    def evaporate_cylinder_fuel_film(self, dt: float, fuel_cutoff: bool) -> float:
        """Evaporate cylinder fuel film and return evaporated mass.
        
        Args:
            dt: Timestep (s)
            fuel_cutoff: Whether fuel is cut off
            
        Returns:
            Evaporated fuel mass (kg)
        """
        cylinder_evap_rate = 5.0 + 0.04 * max(0.0, self.T_cyl - T_ATM)
        evaporated = min(self.fuel_film, self.fuel_film * cylinder_evap_rate * dt)
        self.fuel_film -= evaporated
        if not fuel_cutoff:
            self.m_fuel += evaporated
        return evaporated

    def get_state(self, x: float) -> CylinderState:
        """Get current state snapshot."""
        return CylinderState(
            p_cyl=self.p_cyl,
            T_cyl=self.T_cyl,
            m_air=self.m_air,
            m_fuel=self.m_fuel,
            m_burned=self.m_burned,
            x=x,
            burn_fraction=self.burn_fraction,
            combustion_active=self.combustion_active,
            spark_active=self.spark_active
        )
