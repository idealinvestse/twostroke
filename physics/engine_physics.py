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
    MAX_CRANKCASE_PRESSURE,
    EPSILON_MASS,
    EPSILON_VOLUME,
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


from physics.cylinder import Cylinder, CylinderState

@dataclass
class EngineSnapshot:
    """Snapshot of engine state for rendering/UI."""
    # Global state
    theta: float
    rpm: float
    torque: float
    power_kw: float
    
    # Primary cylinder state (for backwards compatibility)
    x: float
    p_cyl: float
    T_cyl: float
    burn_fraction: float
    combustion_active: bool
    spark_active: bool
    
    # Crankcase/Flow state
    p_cr: float
    p_exh_pipe: float
    a_exh: float
    a_tr: float
    a_in: float
    reed_opening: float
    
    # Mass flow rates (primary cylinder)
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
    
    # Efficiency metrics
    volumetric_efficiency: float
    trapping_efficiency: float
    
    # Multi-cylinder data
    cylinders: list[CylinderState]



class EnginePhysics:
    """2-stroke engine physics simulation.
    
    Refactored modular design with clear separation of concerns:
    - Kinematics: Slider-crank mechanism
    - Thermodynamics: Pressure, temperature, energy
    - Flows: Mass transfer through ports
    - Combustion: Ignition and flame propagation
    """
    
    def __init__(self, num_cylinders: int = 1) -> None:
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
        
        # Cylinders
        self.num_cylinders = num_cylinders
        self.cylinders = []
        for i in range(num_cylinders):
            # Equal firing intervals (e.g. 180 deg for twin)
            offset = i * (2 * math.pi / num_cylinders)
            self.cylinders.append(Cylinder(i, offset))
        
        # Mechanical properties
        self.I_engine = 0.008 * num_cylinders  # Scale inertia with cylinders
        self.friction = 0.65 * num_cylinders   # Scale friction
        
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
        
        # Simulation state - start at 18° to match old physics timing
        self.theta = math.radians(18.0)
        self.omega = 90.0  # rad/s
        self.sim_time = 0.0
        
        # Reed valve state
        self.reed_opening = 0.0
        self.reed_velocity = 0.0
        
        # Crankcase state
        self.m_air_cr = 0.0
        self.m_fuel_cr = 0.0
        self.m_residual_cr = 0.0
        self.T_cr = T_ATM
        self.fuel_film_cr = 0.0
        
        # Initialize with atmospheric conditions
        self._initialize_masses()
        
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
        
        # Last computed mass flow rates (primary cylinder)
        self.last_dm_exh = 0.0
        self.last_dm_tr = 0.0
        self.last_dm_in = 0.0
        self.last_dm_air_in = 0.0
        self.last_dm_fuel_in = 0.0
        self.last_dm_air_tr = 0.0
        self.last_dm_fuel_tr = 0.0
        self.last_dm_burned_tr = 0.0
        self.last_dm_air_exh = 0.0
        self.last_dm_fuel_exh = 0.0
        self.last_dm_burned_exh = 0.0
        
        # Subsystem calculators
        self._kinematics = SliderCrankKinematics()
        self._flow_calc = FlowCalculator()
        self._thermo = Thermodynamics()
        
        # For debug
        self.last_d_q_comb = 0.0
    
    @property
    def T_cyl(self) -> float:
        return self.cylinders[0].T_cyl
    
    @property
    def lambda_value(self) -> float:
        return self.cylinders[0].lambda_value
    
    @property
    def burn_fraction(self) -> float:
        return self.cylinders[0].burn_fraction
    
    @property
    def combustion_active(self) -> bool:
        return self.cylinders[0].combustion_active
    
    @property
    def spark_active(self) -> bool:
        return self.cylinders[0].spark_active
    
    def _initialize_masses(self) -> None:
        """Initialize gas masses from atmospheric conditions."""
        # Crankcase: fresh mixture
        m_cr_atm = self.V_cr_min * P_ATM / (R_GAS * T_ATM)
        target_fa = self._target_fuel_air_ratio()
        self.m_fuel_cr = m_cr_atm * target_fa / (1.0 + target_fa)
        self.m_air_cr = m_cr_atm - self.m_fuel_cr
        self.m_residual_cr = 0.0
        
        # Initial fuel film in crankcase
        self.fuel_film_cr = self.m_fuel_cr * 0.35
        self.m_fuel_cr -= self.fuel_film_cr
        
        # Cylinders: mostly air with some residual burned gas
        # We assume they all start near TDC for initialization
        for cyl in self.cylinders:
            m_cyl_atm = self.V_c * P_ATM / (R_GAS * T_ATM)
            cyl.m_burned = m_cyl_atm * 0.12
            cyl.m_air = m_cyl_atm - cyl.m_burned
            cyl.m_fuel = 0.0
    
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
            self.T_cr,
            self.m_air_cr, self.m_fuel_cr, self.m_residual_cr,
        ]
        
        for value in critical_values:
            if not math.isfinite(value):
                return False
        
        # Check cylinders
        for cyl in self.cylinders:
            cyl_values = [
                cyl.T_cyl,
                cyl.m_air, cyl.m_fuel, cyl.m_burned,
                cyl.burn_fraction, cyl.lambda_value
            ]
            if any(not math.isfinite(v) for v in cyl_values):
                return False
            if any(m < -1e-9 for m in [cyl.m_air, cyl.m_fuel, cyl.m_burned]):
                return False
            if not (T_ATM <= cyl.T_cyl <= 5000.0):
                return False

        # Check non-negative masses in crankcase
        masses = [
            self.m_air_cr, self.m_fuel_cr, self.m_residual_cr,
            self.fuel_film_cr,
        ]
        if any(m < -1e-9 for m in masses):
            return False
        
        # Check temperature bounds
        if not (T_ATM <= self.T_cr <= 1000.0):
            return False
        
        return self.omega >= 0
    
    def _calculate_crankcase_pressure(self, v_cr: float) -> float:
        """Calculate crankcase pressure."""
        m_cr = self.m_air_cr + self.m_fuel_cr + self.m_residual_cr
        v_cr = max(v_cr, EPSILON_VOLUME)
        p_cr = m_cr * R_GAS * self.T_cr / v_cr
        p_cr = clamp(p_cr, MIN_CRANKCASE_PRESSURE, MAX_CRANKCASE_PRESSURE)
        return p_cr
    
    def step(self, dt: float, starter_active: bool = False) -> EngineSnapshot:
        """Execute one physics timestep with multi-cylinder support."""
        if dt > 0.01:
            dt = 0.01
        
        self.sim_time += dt
        throttle_factor = self._throttle_flow_factor()
        
        # 1. Calculate total crankcase volume and get kinematics for all cylinders
        total_v_cr = self.V_cr_min
        cyl_data = []
        
        for cyl in self.cylinders:
            theta_cyl = (self.theta + cyl.crank_offset) % (2 * math.pi)
            kin = self._kinematics.calculate(theta_cyl)
            total_v_cr += self.A_p * (2 * self.R - kin.x)
            cyl_data.append({'kin': kin, 'theta': theta_cyl, 'cyl': cyl})
        
        # 2. Shared Crankcase Pressure
        p_cr = self._calculate_crankcase_pressure(total_v_cr)
        
        # 3. Intake Flow (shared crankcase)
        intake_cond = self._flow_calc.calculate_intake_conditions(
            p_cr, self.throttle, self.idle_fuel_trim
        )
        reed = ReedValveState(self.reed_opening, self.reed_velocity)
        reed = self._flow_calc.update_reed_valve(reed, intake_cond.pressure, p_cr, dt)
        self.reed_opening = reed.opening
        self.reed_velocity = reed.velocity
        
        dm_air_main, dm_air_idle = self._flow_calc.calculate_intake_flow(
            intake_cond, p_cr, self.reed_opening
        )
        dm_air_in = dm_air_main + dm_air_idle
        
        dm_fuel_in = 0.0
        if not self.fuel_cutoff:
            target_fa = self._target_fuel_air_ratio()
            intake_signal = clamp((intake_cond.pressure - p_cr) / P_ATM, 0.0, 1.4)
            main_fuel_signal = 0.95 + 0.15 * math.sqrt(intake_signal + 1e-9)
            idle_fuel_signal = (0.82 + 0.45 * self.idle_fuel_trim) * (0.35 + 0.65 * intake_cond.idle_circuit)
            
            raw_fuel_main = dm_air_main * target_fa * main_fuel_signal
            raw_fuel_idle = dm_air_idle * target_fa * idle_fuel_signal
            wet_fraction = max(0.15, 0.50 - 0.30 * throttle_factor)
            dm_fuel_in = (raw_fuel_main + raw_fuel_idle) * (1.0 - wet_fraction)
            
            film_added = (raw_fuel_main + raw_fuel_idle) * wet_fraction * dt
            self.fuel_film_cr += film_added
            evaporated = min(self.fuel_film_cr, self.fuel_film_cr * 0.2 * dt)
            self.fuel_film_cr -= evaporated
            dm_fuel_in += evaporated / max(dt, 1e-6)
            
            self.m_air_cr += dm_air_in * dt
            self.m_fuel_cr += dm_fuel_in * dt
        
        # 4. Per-cylinder updates
        total_torque = 0.0
        total_dm_out_cr = 0.0
        primary_cyl_state = None
        all_cyl_states = []
        
        for i, data in enumerate(cyl_data):
            cyl = data['cyl']
            kin = data['kin']
            theta_cyl = data['theta']
            
            # Cylinder pressure
            p_cyl = cyl.calculate_pressure(kin.v_cyl)
            
            # Port areas
            ports = self._flow_calc.calculate_port_areas(
                kin.x, self.x_exh, self.w_exh, self.x_tr, self.w_tr
            )
            
            # Exhaust flow
            pipe = ExhaustPipeState(self.p_pipe, self.pipe_phase, self.pipe_amplitude)
            dm_exh = self._flow_calc.calculate_exhaust_flow(p_cyl, cyl.T_cyl, ports.exhaust, pipe)
            pipe = self._flow_calc.update_exhaust_pipe(pipe, dm_exh, ports.exhaust, self.omega, dt)
            self.p_pipe = pipe.pressure
            self.pipe_phase = pipe.phase
            self.pipe_amplitude = pipe.amplitude
            
            # Transfer flow
            dm_tr = self._flow_calc.calculate_transfer_flow(p_cr, self.T_cr, p_cyl, ports.transfer)
            dm_air_tr = 0.0
            dm_fuel_tr = 0.0
            dm_burned_tr = 0.0
            
            if dm_tr > 0:
                transfer_mass = min(dm_tr * dt, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr)
                crankcase_total = max(EPSILON_MASS, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr)
                
                cr_fa_ratio = self.m_fuel_cr / max(1e-9, self.m_air_cr)
                if cr_fa_ratio > 0.3:
                    transfer_mass *= 0.1
                
                transferred_air = transfer_mass * self.m_air_cr / crankcase_total
                transferred_fuel = transfer_mass * self.m_fuel_cr / crankcase_total
                transferred_burned = transfer_mass * self.m_residual_cr / crankcase_total
                
                dm_air_tr = transferred_air / max(dt, 1e-6)
                dm_fuel_tr = transferred_fuel / max(dt, 1e-6)
                dm_burned_tr = transferred_burned / max(dt, 1e-6)
                
                self.m_air_cr -= transferred_air
                self.m_fuel_cr -= transferred_fuel
                self.m_residual_cr -= transferred_burned
                total_dm_out_cr += (transferred_air + transferred_fuel + transferred_burned) / dt
                
                cyl.add_transfer_with_fuel_film(transferred_air, transferred_fuel, transferred_burned, throttle_factor)
            
            # Exhaust mass update
            dm_air_exh = 0.0
            dm_fuel_exh = 0.0
            dm_burned_exh = 0.0
            if dm_exh >= 0:
                exhaust_mass = min(dm_exh * dt, cyl.m_air + cyl.m_fuel + cyl.m_burned)
                cyl_total = max(EPSILON_MASS, cyl.m_air + cyl.m_fuel + cyl.m_burned)
                
                exhausted_air = exhaust_mass * (cyl.m_air / cyl_total)
                exhausted_fuel = exhaust_mass * (cyl.m_fuel / cyl_total)
                exhausted_burned = exhaust_mass * (cyl.m_burned / cyl_total)
                
                dm_air_exh = exhausted_air / max(dt, 1e-6)
                dm_fuel_exh = exhausted_fuel / max(dt, 1e-6)
                dm_burned_exh = exhausted_burned / max(dt, 1e-6)
                
                cyl.m_air -= exhausted_air
                cyl.m_fuel -= exhausted_fuel
                cyl.m_burned -= exhausted_burned
            else:
                # Backflow from exhaust pipe
                backflow_mass = -dm_exh * dt if not self.fuel_cutoff else 0.0
                if backflow_mass > 0:
                    # Assume backflow is mostly burned gas at lower temperature
                    cyl.m_burned += backflow_mass
            
            # Minimum mass guard (prevent cylinder from going below minimum pressure)
            cyl_total = cyl.m_air + cyl.m_fuel + cyl.m_burned
            min_cyl_mass = MIN_PRESSURE * kin.v_cyl / (R_GAS * max(T_ATM, cyl.T_cyl))
            if cyl_total < min_cyl_mass and not self.fuel_cutoff:
                target_fa = self._target_fuel_air_ratio()
                mass_deficit = min_cyl_mass - cyl_total
                air_add = mass_deficit / (1.0 + target_fa)
                fuel_add = mass_deficit - air_add
                cyl.m_air += air_add
                cyl.m_fuel += fuel_add
            
            # Cylinder fuel film evaporation
            cyl.evaporate_cylinder_fuel_film(dt, self.fuel_cutoff)
            
            # Combustion
            heat = cyl.update_combustion(self.theta, kin.x, dt, 
                self.ignition_angle_deg, self.ignition_enabled, 
                self.fuel_cutoff, throttle_factor, self.omega)
            
            # Energy balance
            d_v_cyl = self.A_p * kin.dx_dtheta * self.omega * dt
            dm_in_cyl = (transferred_air + transferred_fuel + transferred_burned) if dm_tr > 0 else 0.0
            
            h_in = self.T_cr * C_P * dm_in_cyl
            d_q = heat + h_in - p_cyl * d_v_cyl
            m_avg = max(EPSILON_MASS, cyl.m_air + cyl.m_fuel + cyl.m_burned)
            cyl.T_cyl = max(T_ATM, cyl.T_cyl + d_q / (m_avg * C_V))
            
            # Cooling
            cyl.apply_cooling(dt)
            cyl.T_cyl = clamp(cyl.T_cyl, T_ATM, 3000.0)
            
            # Torque contribution
            total_torque += (p_cyl - P_ATM) * self.A_p * kin.dx_dtheta
            
            # Track primary cylinder (first one) for snapshot compatibility
            if i == 0:
                primary_cyl_state = cyl.get_state(kin.x)
                primary_ports = ports
                self.last_dm_exh = dm_exh
                self.last_dm_tr = dm_tr
                self.last_dm_in = dm_air_in + dm_fuel_in
                self.last_dm_air_in = dm_air_in
                self.last_dm_fuel_in = dm_fuel_in
                self.last_dm_air_tr = dm_air_tr
                self.last_dm_fuel_tr = dm_fuel_tr
                self.last_dm_burned_tr = dm_burned_tr
                self.last_dm_air_exh = dm_air_exh
                self.last_dm_fuel_exh = dm_fuel_exh
                self.last_dm_burned_exh = dm_burned_exh
            
            all_cyl_states.append(cyl.get_state(kin.x))
        
        # 5. Crankcase energy balance
        sum_d_v_cyl = sum(self.A_p * d['kin'].dx_dtheta * self.omega * dt for d in cyl_data)
        d_v_cr = -sum_d_v_cyl
        
        dm_in_total = dm_air_in + dm_fuel_in
        
        h_in_cr = T_ATM * dm_in_total * dt * C_P
        h_out_cr = self.T_cr * C_P * total_dm_out_cr * dt
        d_q_cr = h_in_cr - h_out_cr - p_cr * d_v_cr
        m_avg_cr = max(EPSILON_MASS, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr)
        self.T_cr = max(T_ATM, self.T_cr + d_q_cr / (m_avg_cr * C_V))
        self.T_cr -= (self.T_cr - T_WALL_CRANKCASE) * HEAT_TRANSFER_COEF * 0.03 * dt
        self.T_cr = clamp(self.T_cr, T_ATM, 500.0)
        
        # Minimum crankcase mass guard
        cr_total = self.m_air_cr + self.m_fuel_cr + self.m_residual_cr
        min_cr_mass = MIN_CRANKCASE_PRESSURE * total_v_cr / (R_GAS * max(T_ATM, self.T_cr))
        if cr_total < min_cr_mass and not self.fuel_cutoff:
            target_fa = self._target_fuel_air_ratio()
            mass_deficit = min_cr_mass - cr_total
            air_add = mass_deficit / (1.0 + target_fa)
            fuel_add = mass_deficit - air_add
            self.m_air_cr += air_add
            self.m_fuel_cr += fuel_add
        
        # 6. Update engine rotation
        f_cr_torque = sum((p_cr - P_ATM) * self.A_p * d['kin'].dx_dtheta for d in cyl_data)
        net_torque = total_torque - f_cr_torque
        
        self.cycle_work += net_torque * self.omega * dt
        
        starter_torque = self.starter_torque if (starter_active and self.omega < 100.0) else 0.0
        pumping_drag = self.omega * 0.008 + 0.000008 * self.omega * self.omega + (1.0 - self.throttle) * 2.0
        extra_brake = 8.0 if self.fuel_cutoff and not starter_active else 0.0
        
        final_torque = net_torque + starter_torque - self.friction - pumping_drag - extra_brake
        self.omega += (final_torque / max(self.I_engine, 1e-6)) * dt
        
        if self.omega < 40.0 and self.ignition_enabled and not self.fuel_cutoff:
            self.omega += (self.idle_omega_target - self.omega) * 3.5 * dt
            self.theta = (self.theta + math.radians(6.0) * dt * 60.0) % (2 * math.pi)
        
        self.omega = clamp(self.omega, 0.0, 1400.0)
        self.theta = (self.theta + self.omega * dt) % (2 * math.pi)
        
        # 7. Cycle tracking
        rpm = self.omega * 30 / math.pi
        self.rpm_ema = self.rpm_ema * (1 - RPM_EMA_ALPHA) + rpm * RPM_EMA_ALPHA
        
        if self.theta < self.last_theta_cross:
            self.last_cycle_torque = self.cycle_work / (2 * math.pi) - self.friction - pumping_drag
            self.torque_ema = self.torque_ema * (1 - TORQUE_EMA_ALPHA) + self.last_cycle_torque * TORQUE_EMA_ALPHA
            power_kw = max(0.0, (self.torque_ema * self.omega) / 1000.0 * MECHANICAL_EFFICIENCY)
            self.power_ema = self.power_ema * (1 - POWER_EMA_ALPHA) + power_kw * POWER_EMA_ALPHA
            
            ideal_air = (self.V_d * P_ATM) / (R_GAS * T_ATM) * self.num_cylinders
            self.volumetric_efficiency = self.cycle_air_tr / max(ideal_air, 1e-9)
            self.cycle_work = 0.0
            self.cycle_air_tr = 0.0
        
        self.last_theta_cross = self.theta
        
        if not self.validate_state():
            raise RuntimeError("Physics state validation failed")
        
        # 8. Create snapshot with new multi-cylinder format
        return EngineSnapshot(
            theta=self.theta,
            rpm=self.rpm_ema,
            torque=self.torque_ema,
            power_kw=self.power_ema,
            x=primary_cyl_state.x,
            p_cyl=primary_cyl_state.p_cyl,
            T_cyl=primary_cyl_state.T_cyl,
            burn_fraction=primary_cyl_state.burn_fraction,
            combustion_active=primary_cyl_state.combustion_active,
            spark_active=primary_cyl_state.spark_active,
            p_cr=p_cr,
            p_exh_pipe=self.p_pipe,
            a_exh=primary_ports.exhaust,
            a_tr=primary_ports.transfer,
            a_in=(intake_cond.area_main + intake_cond.area_idle) * self.reed_opening,
            reed_opening=self.reed_opening,
            dm_exh=self.last_dm_exh,
            dm_tr=self.last_dm_tr,
            dm_in=self.last_dm_in,
            dm_air_in=self.last_dm_air_in,
            dm_fuel_in=self.last_dm_fuel_in,
            dm_air_tr=self.last_dm_air_tr,
            dm_fuel_tr=self.last_dm_fuel_tr,
            dm_burned_tr=self.last_dm_burned_tr,
            dm_air_exh=self.last_dm_air_exh,
            dm_fuel_exh=self.last_dm_fuel_exh,
            dm_burned_exh=self.last_dm_burned_exh,
            volumetric_efficiency=self.volumetric_efficiency,
            trapping_efficiency=self.trapping_efficiency,
            cylinders=all_cyl_states
        )
    
    def snapshot(self) -> EngineSnapshot:
        """Return current state snapshot without advancing simulation."""
        # Calculate total crankcase volume
        total_v_cr = self.V_cr_min
        all_cyl_states = []
        primary_cyl_state = None
        primary_ports = None
        
        for i, cyl in enumerate(self.cylinders):
            theta_cyl = (self.theta + cyl.crank_offset) % (2 * math.pi)
            kin = self._kinematics.calculate(theta_cyl)
            total_v_cr += self.A_p * (2 * self.R - kin.x)
            
            cyl_state = cyl.get_state(kin.x)
            all_cyl_states.append(cyl_state)
            
            if i == 0:
                primary_cyl_state = cyl_state
                primary_ports = self._flow_calc.calculate_port_areas(
                    kin.x, self.x_exh, self.w_exh, self.x_tr, self.w_tr
                )
        
        p_cr = self._calculate_crankcase_pressure(total_v_cr)
        
        intake_cond = self._flow_calc.calculate_intake_conditions(
            p_cr, self.throttle, self.idle_fuel_trim
        )
        
        return EngineSnapshot(
            theta=self.theta,
            rpm=self.rpm_ema,
            torque=self.torque_ema,
            power_kw=self.power_ema,
            x=primary_cyl_state.x,
            p_cyl=primary_cyl_state.p_cyl,
            T_cyl=primary_cyl_state.T_cyl,
            burn_fraction=primary_cyl_state.burn_fraction,
            combustion_active=primary_cyl_state.combustion_active,
            spark_active=primary_cyl_state.spark_active,
            p_cr=p_cr,
            p_exh_pipe=self.p_pipe,
            a_exh=primary_ports.exhaust,
            a_tr=primary_ports.transfer,
            a_in=(intake_cond.area_main + intake_cond.area_idle) * self.reed_opening,
            reed_opening=self.reed_opening,
            dm_exh=self.last_dm_exh,
            dm_tr=self.last_dm_tr,
            dm_in=self.last_dm_in,
            dm_air_in=self.last_dm_air_in,
            dm_fuel_in=self.last_dm_fuel_in,
            dm_air_tr=self.last_dm_air_tr,
            dm_fuel_tr=self.last_dm_fuel_tr,
            dm_burned_tr=self.last_dm_burned_tr,
            dm_air_exh=self.last_dm_air_exh,
            dm_fuel_exh=self.last_dm_fuel_exh,
            dm_burned_exh=self.last_dm_burned_exh,
            volumetric_efficiency=self.volumetric_efficiency,
            trapping_efficiency=self.trapping_efficiency,
            cylinders=all_cyl_states
        )
