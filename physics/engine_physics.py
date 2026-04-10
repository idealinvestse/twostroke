"""Main engine physics class - refactored modular design.

Integrates kinematics, thermodynamics, flows, and combustion
for a complete 2-stroke engine simulation.
"""

import math
from dataclasses import dataclass

from physics.constants import (
    R_GAS,
    P_ATM,
    T_ATM,
    C_V,
    C_P,
    MIN_PRESSURE,
    MIN_CRANKCASE_PRESSURE,
    MAX_CYLINDER_PRESSURE,
    MAX_CRANKCASE_PRESSURE,
    EPSILON_MASS,
    EPSILON_VOLUME,
    FUEL_LHV,
    STOICH_AFR,
    T_WALL_CYLINDER,
    T_WALL_CRANKCASE,
    HEAT_TRANSFER_COEF,
    RPM_EMA_ALPHA,
    TORQUE_EMA_ALPHA,
    POWER_EMA_ALPHA,
    MECHANICAL_EFFICIENCY,
    MAX_INTAKE_AREA_M2,
    BORE_M,
    HALF_STROKE_M,
    CON_ROD_M,
    PISTON_AREA_M2,
    CLEARANCE_VOLUME_M3,
    CRANKCASE_VOLUME_M3,
    EXHAUST_PORT_OPEN_M,
    TRANSFER_PORT_OPEN_M,
    EXHAUST_PORT_WIDTH_M,
    TRANSFER_PORT_WIDTH_M,
)
from physics.utils import clamp
from physics.kinematics import SliderCrankKinematics
from physics.thermodynamics import Thermodynamics
from physics.flows import FlowCalculator, ReedValveState, ExhaustPipeState
from physics.combustion import CombustionModel, CombustionState


@dataclass
class EngineSnapshot:
    """Snapshot of engine state for rendering/UI."""
    x: float
    p_cyl: float
    p_cr: float
    p_exh_pipe: float
    a_exh: float
    a_tr: float
    a_in: float
    rpm: float
    torque: float
    power_kw: float
    dm_exh: float
    dm_tr: float
    dm_in: float
    dm_air_in: float
    dm_fuel_in: float
    dm_air_tr: float
    dm_fuel_tr: float
    dm_burned_tr: float
    dm_air_exh: float
    dm_fuel_exh: float
    dm_burned_exh: float
    volumetric_efficiency: float
    trapping_efficiency: float


class EnginePhysics:
    """2-stroke engine physics simulation.
    
    Refactored modular design with clear separation of concerns:
    - Kinematics: Slider-crank mechanism
    - Thermodynamics: Pressure, temperature, energy
    - Flows: Mass transfer through ports
    - Combustion: Ignition and flame propagation
    """
    
    def __init__(self) -> None:
        # Engine geometry (more realistic 50cc specs)
        self.B = BORE_M
        self.R = HALF_STROKE_M
        self.L = CON_ROD_M
        self.A_p = PISTON_AREA_M2
        self.V_d = self.A_p * 2 * self.R
        self.V_c = CLEARANCE_VOLUME_M3
        self.V_cr_min = CRANKCASE_VOLUME_M3
        
        # Port geometry
        self.x_exh = EXHAUST_PORT_OPEN_M
        self.x_tr = TRANSFER_PORT_OPEN_M
        self.w_exh = EXHAUST_PORT_WIDTH_M
        self.w_tr = TRANSFER_PORT_WIDTH_M
        self.A_in_max = MAX_INTAKE_AREA_M2
        
        # Mechanical properties
        self.I_engine = 0.008  # kg·m², rotational inertia
        self.friction = 0.65   # N·m, friction torque
        
        # Control inputs
        self.throttle = 1.0
        self.fuel_ratio = 0.068
        self.idle_fuel_trim = 1.0
        self.ignition_angle_deg = 340.0
        self.ignition_enabled = True
        self.fuel_cutoff = False
        
        # Starter motor
        self.starter_duration = 0.8  # s
        self.starter_torque = 4.0     # N·m
        self.idle_omega_target = 115.0  # rad/s (~1100 RPM)
        
        # Simulation state
        self.theta = math.radians(18.0)
        self.omega = 90.0  # rad/s
        self.sim_time = 0.0
        
        # Reed valve state
        self.reed_opening = 0.0
        self.reed_velocity = 0.0
        
        # Cylinder state
        self.m_air_cyl = 0.0
        self.m_fuel_cyl = 0.0
        self.m_burned_cyl = 0.0
        self.T_cyl = T_ATM
        self.fuel_film_cyl = 0.0
        
        # Crankcase state
        self.m_air_cr = 0.0
        self.m_fuel_cr = 0.0
        self.m_residual_cr = 0.0
        self.T_cr = T_ATM
        self.fuel_film_cr = 0.0
        
        # Initialize with atmospheric conditions
        self._initialize_masses()
        
        # Combustion state
        self.combustion_active = False
        self.burn_fraction = 0.0
        self.theta_ign = 0.0
        self.lambda_value = 1.0
        self.spark_active = False
        
        # Cycle tracking
        self.cycle_air_in = 0.0
        self.cycle_air_tr = 0.0
        self.cycle_air_exh = 0.0
        self.volumetric_efficiency = 0.0
        self.trapping_efficiency = 0.0
        self.last_theta_cross = 0.0
        self.cycle_work = 0.0
        
        # Output smoothing (EMA)
        self.rpm_ema = 0.0
        self.torque_ema = 0.0
        self.power_ema = 0.0
        self.last_cycle_torque = 0.0
        
        # Exhaust pipe state
        self.p_pipe = MIN_PRESSURE
        self.pipe_phase = 0.0
        self.pipe_amplitude = 0.0
        
        # Subsystem calculators
        self._kinematics = SliderCrankKinematics()
        self._flow_calc = FlowCalculator()
        self._thermo = Thermodynamics()
        
        # For debug
        self.last_d_q_comb = 0.0
    
    def _initialize_masses(self) -> None:
        """Initialize gas masses from atmospheric conditions."""
        # Cylinder: mostly air with some residual burned gas
        m_cyl_atm = self.V_c * P_ATM / (R_GAS * T_ATM)
        self.m_burned_cyl = m_cyl_atm * 0.12
        self.m_fuel_cyl = 0.0
        self.m_air_cyl = m_cyl_atm - self.m_burned_cyl
        
        # Crankcase: fresh mixture
        m_cr_atm = self.V_cr_min * P_ATM / (R_GAS * T_ATM)
        target_fa = self._target_fuel_air_ratio()
        self.m_fuel_cr = m_cr_atm * target_fa / (1.0 + target_fa)
        self.m_air_cr = m_cr_atm - self.m_fuel_cr
        self.m_residual_cr = 0.0
        
        # Initial fuel film in crankcase
        self.fuel_film_cr = self.m_fuel_cr * 0.35
        self.m_fuel_cr -= self.fuel_film_cr
    
    def _target_fuel_air_ratio(self) -> float:
        """Calculate target fuel-air ratio from fuel ratio setting."""
        return self.fuel_ratio / max(1e-6, 1.0 - self.fuel_ratio)
    
    def _throttle_flow_factor(self) -> float:
        """Calculate throttle flow factor."""
        return 0.04 + 0.96 * (self.throttle ** 1.35)
    
    def _idle_circuit_strength(self) -> float:
        """Calculate idle circuit strength."""
        return max(0.0, min(1.0, (0.32 - self.throttle) / 0.32))
    
    def validate_state(self) -> bool:
        """Check for NaN or infinity values in critical state variables."""
        critical_values = [
            self.theta, self.omega, self.sim_time,
            self.T_cyl, self.T_cr,
            self.m_air_cyl, self.m_fuel_cyl, self.m_burned_cyl,
            self.m_air_cr, self.m_fuel_cr, self.m_residual_cr,
            self.lambda_value, self.burn_fraction,
        ]
        
        for value in critical_values:
            if not math.isfinite(value):
                return False
        
        # Check non-negative masses
        masses = [
            self.m_air_cyl, self.m_fuel_cyl, self.m_burned_cyl,
            self.m_air_cr, self.m_fuel_cr, self.m_residual_cr,
            self.fuel_film_cyl, self.fuel_film_cr,
        ]
        if any(m < -1e-9 for m in masses):
            return False
        
        # Check temperature bounds
        if not (T_ATM <= self.T_cyl <= 5000.0):
            return False
        if not (T_ATM <= self.T_cr <= 1000.0):
            return False
        
        return self.omega >= 0
    
    def _calculate_pressures(self, v_cyl: float, v_cr: float) -> tuple[float, float]:
        """Calculate cylinder and crankcase pressures."""
        m_cyl = self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl
        m_cr = self.m_air_cr + self.m_fuel_cr + self.m_residual_cr
        
        v_cyl = max(v_cyl, EPSILON_VOLUME)
        v_cr = max(v_cr, EPSILON_VOLUME)
        
        p_cyl = m_cyl * R_GAS * self.T_cyl / v_cyl
        p_cr = m_cr * R_GAS * self.T_cr / v_cr
        
        p_cyl = clamp(p_cyl, MIN_PRESSURE, MAX_CYLINDER_PRESSURE)
        p_cr = clamp(p_cr, MIN_CRANKCASE_PRESSURE, MAX_CRANKCASE_PRESSURE)
        
        return p_cyl, p_cr
    
    def _update_combustion(self, theta: float, x: float, dt: float) -> float:
        """Update combustion state and return heat released."""
        theta_deg = math.degrees(theta) % 360.0
        fresh_mass = self.m_air_cyl + self.m_fuel_cyl
        
        # Check for ignition
        can_ignite = CombustionModel.can_ignite(
            theta_deg=theta_deg,
            ignition_angle_deg=self.ignition_angle_deg,
            combustion_active=self.combustion_active,
            x=x,
            fresh_mass=fresh_mass,
            ignition_enabled=self.ignition_enabled,
            fuel_cutoff=self.fuel_cutoff,
        )
        
        if can_ignite:
            self.combustion_active = True
            self.spark_active = True
            
            combustion = CombustionModel.start_combustion(
                theta=theta,
                m_fuel_cyl=self.m_fuel_cyl,
                m_air_cyl=self.m_air_cyl,
                throttle_factor=self._throttle_flow_factor(),
                ignition_angle_deg=self.ignition_angle_deg,
            )
            
            self.burn_fraction = combustion.burn_fraction
            self.theta_ign = combustion.theta_ign
            self.lambda_value = combustion.lambda_value
            
            # IMPORTANT: Set combustion_active = True when combustion starts!
            if combustion.active:
                self.combustion_active = True
            else:
                self.combustion_active = False
                self.lambda_value = clamp(combustion.lambda_value, 0.5, 2.5)
        else:
            self.spark_active = False
        
        # Update active combustion
        heat_released = 0.0
        if self.combustion_active:
            combustion = CombustionState(
                active=True,
                burn_fraction=self.burn_fraction,
                theta_ign=self.theta_ign,
                duration=0.0,  # Will be calculated
                efficiency=0.0,
                lambda_value=self.lambda_value,
                available_fuel=0.0,
            )
            
            combustion, heat_released = CombustionModel.update_combustion(
                combustion=combustion,
                theta=theta,
                m_fuel_cyl=self.m_fuel_cyl,
                m_air_cyl=self.m_air_cyl,
                dt=dt,
            )
            
            self.combustion_active = combustion.active
            self.burn_fraction = combustion.burn_fraction
            
            if heat_released > 0:
                # Consume fuel and air
                fuel_burned = heat_released / FUEL_LHV
                air_consumed = fuel_burned * STOICH_AFR
                
                if air_consumed > self.m_air_cyl:
                    air_consumed = self.m_air_cyl
                    fuel_burned = air_consumed / STOICH_AFR
                
                self.m_fuel_cyl -= fuel_burned
                self.m_air_cyl -= air_consumed
                self.m_burned_cyl += fuel_burned + air_consumed
        
        return heat_released
    
    def step(self, dt: float, starter_active: bool = False) -> EngineSnapshot:
        """Execute one physics timestep.
        
        This is the main simulation method that coordinates all subsystems.
        """
        if dt > 0.01:
            dt = 0.01
        
        self.sim_time += dt
        
        # 1. Calculate kinematics
        kinematic = self._kinematics.calculate(self.theta)
        x, v_cyl, v_cr, dx_dtheta = (
            kinematic.x,
            kinematic.v_cyl,
            kinematic.v_cr,
            kinematic.dx_dtheta,
        )
        
        # 2. Calculate pressures
        p_cyl, p_cr = self._calculate_pressures(v_cyl, v_cr)
        
        # 3. Calculate port areas
        ports = self._flow_calc.calculate_port_areas(
            x, self.x_exh, self.w_exh, self.x_tr, self.w_tr
        )
        
        # 4. Update reed valve
        intake_cond = self._flow_calc.calculate_intake_conditions(
            p_cr, self.throttle, self.idle_fuel_trim
        )
        
        reed = ReedValveState(self.reed_opening, self.reed_velocity)
        reed = self._flow_calc.update_reed_valve(
            reed, intake_cond.pressure, p_cr, dt
        )
        self.reed_opening = reed.opening
        self.reed_velocity = reed.velocity
        
        # 5. Update exhaust pipe
        pipe = ExhaustPipeState(self.p_pipe, self.pipe_phase, self.pipe_amplitude)
        dm_exh = self._flow_calc.calculate_exhaust_flow(p_cyl, self.T_cyl, ports.exhaust, pipe)
        pipe = self._flow_calc.update_exhaust_pipe(pipe, dm_exh, ports.exhaust, self.omega, dt)
        self.p_pipe = pipe.pressure
        self.pipe_phase = pipe.phase
        self.pipe_amplitude = pipe.amplitude
        
        # 6. Calculate mass flows
        dm_air_main, dm_air_idle = self._flow_calc.calculate_intake_flow(
            intake_cond, p_cr, self.reed_opening
        )
        dm_air_in = dm_air_main + dm_air_idle
        
        # Fuel injection
        dm_fuel_in = 0.0
        if not self.fuel_cutoff:
            target_fa = self._target_fuel_air_ratio()
            intake_signal = clamp((intake_cond.pressure - p_cr) / P_ATM, 0.0, 1.4)
            
            # main_fuel_signal should be ~1.0 to match target AFR exactly
            # Reduced from 0.85 + 0.5*sqrt() which was over-fueling
            main_fuel_signal = 0.95 + 0.15 * math.sqrt(intake_signal + 1e-9)
            idle_fuel_signal = (0.82 + 0.45 * self.idle_fuel_trim) * (
                0.35 + 0.65 * intake_cond.idle_circuit
            )
            
            raw_fuel_main = dm_air_main * target_fa * main_fuel_signal
            raw_fuel_idle = dm_air_idle * target_fa * idle_fuel_signal
            
            # Simplified fuel injection - no fuel film in crankcase for 50cc engine
            # Fuel film was causing over-rich transfer when crankcase air was depleted
            throttle_factor = self._throttle_flow_factor()
            wet_fraction = max(0.15, 0.50 - 0.30 * throttle_factor)
            
            # Add all fuel directly to crankcase (no film model for small engine)
            dm_fuel_in = (raw_fuel_main + raw_fuel_idle) * (1.0 - wet_fraction)
            
            # Keep minimal film that doesn't evaporate aggressively
            film_added = (raw_fuel_main + raw_fuel_idle) * wet_fraction * dt
            self.fuel_film_cr += film_added
            # Very slow evaporation to prevent sudden enrichment
            evaporated = min(self.fuel_film_cr, self.fuel_film_cr * 0.2 * dt)
            self.fuel_film_cr -= evaporated
            dm_fuel_in += evaporated / max(dt, 1e-6)
            
            # Add to crankcase
            self.m_air_cr += dm_air_in * dt
            self.m_fuel_cr += dm_fuel_in * dt
        
        # Transfer flow
        dm_tr = self._flow_calc.calculate_transfer_flow(p_cr, self.T_cr, p_cyl, ports.transfer)
        dm_air_tr = 0.0
        dm_fuel_tr = 0.0
        dm_burned_tr = 0.0
        
        if dm_tr > 0 and not self.fuel_cutoff:
            transfer_mass = min(dm_tr * dt, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr)
            crankcase_total = max(EPSILON_MASS, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr)
            
            # Check if crankcase mixture is reasonable before transfer
            # Prevent over-rich transfer when air is depleted but fuel remains
            cr_fa_ratio = self.m_fuel_cr / max(1e-9, self.m_air_cr)
            if cr_fa_ratio > 0.3:  # Max fuel-air ratio ~0.3 (lambda ~0.23, very rich)
                # Limit transfer to prevent over-rich cylinder mixture
                transfer_mass *= 0.1  # Reduce transfer significantly
            
            transferred_air = transfer_mass * self.m_air_cr / crankcase_total
            transferred_fuel = transfer_mass * self.m_fuel_cr / crankcase_total
            transferred_residual = transfer_mass * self.m_residual_cr / crankcase_total
            
            dm_air_tr = transferred_air / max(dt, 1e-6)
            dm_fuel_tr = transferred_fuel / max(dt, 1e-6)
            dm_burned_tr = transferred_residual / max(dt, 1e-6)
            
            self.m_air_cr -= transferred_air
            self.m_fuel_cr -= transferred_fuel
            self.m_residual_cr -= transferred_residual
            
            # Cylinder fuel film
            cyl_wet_fraction = max(0.05, 0.25 - 0.005 * max(0.0, self.T_cyl - T_ATM))
            cyl_film_added = transferred_fuel * cyl_wet_fraction
            self.fuel_film_cyl += cyl_film_added
            self.m_fuel_cyl += transferred_fuel - cyl_film_added
            self.m_air_cyl += transferred_air
            self.m_burned_cyl += transferred_residual
        
        # Cylinder fuel film evaporation
        cyl_evap_rate = 5.0 + 0.04 * max(0.0, self.T_cyl - T_ATM)
        cyl_evaporated = min(self.fuel_film_cyl, self.fuel_film_cyl * cyl_evap_rate * dt)
        self.fuel_film_cyl -= cyl_evaporated
        if not self.fuel_cutoff:
            self.m_fuel_cyl += cyl_evaporated
        
        # Exhaust flow composition
        dm_air_exh = 0.0
        dm_fuel_exh = 0.0
        dm_burned_exh = 0.0
        
        if dm_exh >= 0:
            exhaust_mass = min(dm_exh * dt, self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl)
            throttle_factor = self._throttle_flow_factor()
            
            # Proportional exhaust - maintains air-fuel ratio in cylinder
            # This prevents enrichment of remaining mixture
            cyl_total = max(EPSILON_MASS, self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl)
            
            exhausted_burned = exhaust_mass * (self.m_burned_cyl / cyl_total)
            exhausted_fuel = exhaust_mass * (self.m_fuel_cyl / cyl_total)
            exhausted_air = exhaust_mass * (self.m_air_cyl / cyl_total)
            
            # Clamp to available amounts
            exhausted_burned = min(exhausted_burned, self.m_burned_cyl)
            exhausted_fuel = min(exhausted_fuel, self.m_fuel_cyl)
            exhausted_air = min(exhausted_air, self.m_air_cyl)
            
            dm_air_exh = exhausted_air / max(dt, 1e-6)
            dm_fuel_exh = exhausted_fuel / max(dt, 1e-6)
            dm_burned_exh = exhausted_burned / max(dt, 1e-6)
            
            self.m_air_cyl -= exhausted_air
            self.m_fuel_cyl -= exhausted_fuel
            self.m_burned_cyl -= exhausted_burned
        
        # 7. Apply combustion
        heat_released = self._update_combustion(self.theta, x, dt)
        self.last_d_q_comb = heat_released
        
        # 8. Energy balance for temperatures
        d_v_cyl = self.A_p * dx_dtheta * self.omega * dt
        d_v_cr = -d_v_cyl
        
        # Crankcase energy balance
        dm_in_total = dm_air_in + dm_fuel_in
        dm_out_cr = dm_air_tr + dm_fuel_tr + dm_burned_tr
        dm_net_cr = (dm_in_total - dm_out_cr) * dt
        
        h_in_cr = T_ATM * dm_in_total * dt * C_P
        h_out_cr = self.T_cr * C_P * dm_out_cr * dt
        d_q_cr = h_in_cr - h_out_cr - p_cr * d_v_cr
        m_cv_dT_cr = d_q_cr + self.T_cr * C_V * dm_net_cr
        
        m_avg_cr = max(EPSILON_MASS, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr - dm_net_cr * 0.5)
        self.T_cr = max(T_ATM, self.T_cr + m_cv_dT_cr / (m_avg_cr * C_V))
        
        # Cylinder energy balance
        dm_in_cyl = (dm_air_tr + dm_fuel_tr + dm_burned_tr) * dt
        if dm_exh >= 0:
            dm_out_cyl = (dm_air_exh + dm_fuel_exh + dm_burned_exh) * dt
            dm_backflow = 0.0
        else:
            dm_out_cyl = 0.0
            dm_backflow = -dm_exh * dt
        
        dm_net_cyl = dm_in_cyl - dm_out_cyl + dm_backflow
        
        h_in_cyl = self.T_cr * C_P * (dm_air_tr + dm_fuel_tr + dm_burned_tr) * dt
        h_out_cyl = self.T_cyl * C_P * dm_out_cyl
        h_backflow = self.T_cyl * 0.9 * C_P * dm_backflow
        
        d_q_cyl = heat_released + h_in_cyl + h_backflow - h_out_cyl - p_cyl * d_v_cyl
        m_cv_dT_cyl = d_q_cyl + self.T_cyl * C_V * dm_net_cyl
        
        m_avg_cyl = max(EPSILON_MASS, self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl - dm_net_cyl * 0.5)
        self.T_cyl = max(T_ATM, self.T_cyl + m_cv_dT_cyl / (m_avg_cyl * C_V))
        
        # Cooling
        self.T_cyl -= (self.T_cyl - T_WALL_CYLINDER) * HEAT_TRANSFER_COEF * 0.1 * dt
        self.T_cr -= (self.T_cr - T_WALL_CRANKCASE) * HEAT_TRANSFER_COEF * 0.03 * dt
        
        # Clamp temperatures
        self.T_cyl = clamp(self.T_cyl, T_ATM, 3000.0)
        self.T_cr = clamp(self.T_cr, T_ATM, 500.0)
        
        # 9. Calculate torque and update rotation
        f_gas = (p_cyl - P_ATM) * self.A_p
        f_cr = (p_cr - P_ATM) * self.A_p
        torque = (f_gas - f_cr) * dx_dtheta
        
        step_dtheta = self.omega * dt
        self.cycle_work += torque * step_dtheta
        
        # Starter torque
        starter_torque = self.starter_torque if (starter_active and self.omega < 100.0) else 0.0
        
        # Friction and pumping
        pumping_drag = self.omega * 0.008 + 0.000008 * self.omega * self.omega + (1.0 - self.throttle) * 2.0
        extra_brake = 8.0 if self.fuel_cutoff and not starter_active else 0.0
        
        net_torque = torque + starter_torque - self.friction - pumping_drag - extra_brake
        
        inertia = max(self.I_engine, 1e-6)
        self.omega += (net_torque / inertia) * dt
        
        # Idle stabilization
        if self.omega < 40.0 and self.ignition_enabled and not self.fuel_cutoff:
            self.omega += (self.idle_omega_target - self.omega) * 3.5 * dt
            self.theta = (self.theta + math.radians(6.0) * dt * 60.0) % (2 * math.pi)
        
        self.omega = clamp(self.omega, 0.0, 1400.0)
        self.theta = (self.theta + self.omega * dt) % (2 * math.pi)
        
        # 10. Update cycle tracking and EMA
        rpm = self.omega * 30 / math.pi
        self.rpm_ema = self.rpm_ema * (1 - RPM_EMA_ALPHA) + rpm * RPM_EMA_ALPHA
        
        if self.theta < self.last_theta_cross:
            # Completed a cycle
            self.last_cycle_torque = self.cycle_work / (2 * math.pi) - self.friction - pumping_drag
            self.torque_ema = self.torque_ema * (1 - TORQUE_EMA_ALPHA) + self.last_cycle_torque * TORQUE_EMA_ALPHA
            
            power_kw = max(0.0, (self.torque_ema * self.omega) / 1000.0 * MECHANICAL_EFFICIENCY)
            self.power_ema = self.power_ema * (1 - POWER_EMA_ALPHA) + power_kw * POWER_EMA_ALPHA
            
            # VE and TE calculation
            ideal_air = (self.V_d * P_ATM) / (R_GAS * T_ATM)
            self.volumetric_efficiency = self.cycle_air_tr / max(ideal_air, 1e-9)
            fresh_lost = max(0.0, self.cycle_air_exh * 0.25)
            self.trapping_efficiency = max(0.0, self.cycle_air_tr - fresh_lost) / max(self.cycle_air_tr, 1e-9)
            
            self.cycle_work = 0.0
            self.cycle_air_in = 0.0
            self.cycle_air_tr = 0.0
            self.cycle_air_exh = 0.0
        
        self.cycle_air_in += max(0.0, dm_air_in) * dt
        self.cycle_air_tr += max(0.0, dm_air_tr) * dt
        self.cycle_air_exh += max(0.0, dm_air_exh) * dt
        self.last_theta_cross = self.theta
        
        # Validate
        if not self.validate_state():
            raise RuntimeError("Physics state validation failed")
        
        # 11. Create snapshot
        return EngineSnapshot(
            x=x,
            p_cyl=p_cyl,
            p_cr=p_cr,
            p_exh_pipe=self.p_pipe,
            a_exh=ports.exhaust,
            a_tr=ports.transfer,
            a_in=(intake_cond.area_main + intake_cond.area_idle) * self.reed_opening,
            rpm=self.rpm_ema,
            torque=self.torque_ema,
            power_kw=self.power_ema,
            dm_exh=dm_exh,
            dm_tr=dm_tr,
            dm_in=dm_air_in + dm_fuel_in,
            dm_air_in=dm_air_in,
            dm_fuel_in=dm_fuel_in,
            dm_air_tr=dm_air_tr,
            dm_fuel_tr=dm_fuel_tr,
            dm_burned_tr=dm_burned_tr,
            dm_air_exh=dm_air_exh,
            dm_fuel_exh=dm_fuel_exh,
            dm_burned_exh=dm_burned_exh,
            volumetric_efficiency=self.volumetric_efficiency,
            trapping_efficiency=self.trapping_efficiency,
        )
    
    def snapshot(self) -> EngineSnapshot:
        """Return current state snapshot without advancing simulation."""
        kinematic = self._kinematics.calculate(self.theta)
        p_cyl, p_cr = self._calculate_pressures(kinematic.v_cyl, kinematic.v_cr)
        ports = self._flow_calc.calculate_port_areas(
            kinematic.x, self.x_exh, self.w_exh, self.x_tr, self.w_tr
        )
        intake_cond = self._flow_calc.calculate_intake_conditions(
            p_cr, self.throttle, self.idle_fuel_trim
        )
        
        return EngineSnapshot(
            x=kinematic.x,
            p_cyl=p_cyl,
            p_cr=p_cr,
            p_exh_pipe=self.p_pipe,
            a_exh=ports.exhaust,
            a_tr=ports.transfer,
            a_in=(intake_cond.area_main + intake_cond.area_idle) * self.reed_opening,
            rpm=self.rpm_ema,
            torque=self.torque_ema,
            power_kw=self.power_ema,
            dm_exh=0.0,
            dm_tr=0.0,
            dm_in=0.0,
            dm_air_in=0.0,
            dm_fuel_in=0.0,
            dm_air_tr=0.0,
            dm_fuel_tr=0.0,
            dm_burned_tr=0.0,
            dm_air_exh=0.0,
            dm_fuel_exh=0.0,
            dm_burned_exh=0.0,
            volumetric_efficiency=self.volumetric_efficiency,
            trapping_efficiency=self.trapping_efficiency,
        )
