"""Main engine physics class - refactored modular design.

Integrates kinematics, thermodynamics, flows, and combustion
for a complete 2-stroke engine simulation.
"""

import math
from dataclasses import dataclass
from typing import Optional

from physics.constants import (
    R_GAS,
    P_ATM,
    T_ATM,
    C_P,
    MIN_PRESSURE,
    MAX_CYLINDER_PRESSURE,
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
    DISPLACEMENT_M3,
    EXHAUST_PORT_OPEN_M,
    TRANSFER_PORT_OPEN_M,
    EXHAUST_PORT_WIDTH_M,
    TRANSFER_PORT_WIDTH_M,
    PIPE_RESONANCE_FREQ_HZ,
    # Expansion chamber geometry
    EXHAUST_HEADER_LENGTH_M,
    EXHAUST_HEADER_DIAMETER_M,
    EXHAUST_DIFFUSER_LENGTH_M,
    EXHAUST_DIFFUSER_START_DIA_M,
    EXHAUST_DIFFUSER_END_DIA_M,
    EXHAUST_BELLY_LENGTH_M,
    EXHAUST_BELLY_DIAMETER_M,
    EXHAUST_BAFFLE_LENGTH_M,
    EXHAUST_BAFFLE_START_DIA_M,
    EXHAUST_BAFFLE_END_DIA_M,
    INTAKE_RUNNER_LENGTH_M,
    INTAKE_RUNNER_DIAMETER_M,
    PIPE_NUM_SEGMENTS,
)
from physics.utils import clamp
from physics.kinematics import SliderCrankKinematics
from physics.thermodynamics import Thermodynamics, gas_properties, EnhancedThermodynamics
from physics.flows import FlowCalculator, ReedValveState, ExhaustPipeState, ScavengingCalculator, ScavengingModel
from physics.scavenging import AdvancedScavengingModel, ScavengingZones, ScavengingMetrics
from physics.combustion import AdvancedCombustionModel
from physics.carburetor import CarburetorModel
from physics.gasdynamics import Quasi1DPipe, ExpansionChamberPipe, IntakeRunnerPipe, PipeSegment
from physics.friction import FrictionModel, FrictionBreakdown


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
    
    # Friction breakdown
    friction_breakdown: Optional[FrictionBreakdown] = None



class EnginePhysics:
    """2-stroke engine physics simulation.
    
    Refactored modular design with clear separation of concerns:
    - Kinematics: Slider-crank mechanism
    - Thermodynamics: Pressure, temperature, energy
    - Flows: Mass transfer through ports
    - Combustion: Ignition and flame propagation
    """
    
    def __init__(self, num_cylinders: int = 1) -> None:
        if num_cylinders < 1:
            raise ValueError("EnginePhysics requires at least one cylinder")

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
        
        # Exhaust pipe state (legacy - used when use_quasi_1d_pipes is False)
        self.p_pipe = MIN_PRESSURE
        self.pipe_phase = 0.0
        self.pipe_amplitude = 0.0
        
        # Quasi-1D pipe state references (for backward compatibility in snapshot)
        self._exhaust_pipe_pressure = P_ATM
        self._intake_pipe_pressure = P_ATM
        
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
        self._friction_model = FrictionModel(
            piston_mass=0.15, bore=BORE_M, stroke=2*HALF_STROKE_M, con_rod_length=CON_ROD_M
        )
        self._friction_scaling = 0.15  # Scale FrictionModel to match original behavior
        self._scavenging_calc = ScavengingCalculator(
            model=ScavengingModel.COMBINED,
            short_circuit_fraction=0.15,
            displacement_efficiency=0.7
        )
        
        # === NEW: Advanced Multi-Zone Scavenging Model ===
        # Feature flag: use True for advanced model, False for legacy
        self.use_advanced_scavenging = True
        
        # Advanced scavenging with RPM and geometry dependence
        self._advanced_scavenging = AdvancedScavengingModel(
            bore=BORE_M,
            stroke=2*HALF_STROKE_M,
            displacement=DISPLACEMENT_M3,
        )
        
        # === NEW: Advanced Residual-Sensitive Combustion ===
        # Feature flag: use True for advanced model, False for legacy
        self.use_advanced_combustion = True
        
        # Advanced combustion with residual sensitivity and variable Wiebe parameters
        self._advanced_combustion = AdvancedCombustionModel()
        
        # Track combustion state from advanced scavenging
        self.residual_fraction = 0.0
        self.charge_purity = 0.0
        self.charge_temperature = T_ATM
        
        # === NEW: Enhanced Thermodynamics and Heat Transfer ===
        # Feature flag: use True for enhanced model, False for legacy
        self.use_enhanced_thermodynamics = True
        
        # Enhanced thermodynamics with wall temperature dynamics and variable cp/cv
        self._enhanced_thermo = EnhancedThermodynamics(
            bore=BORE_M,
            stroke=2*HALF_STROKE_M,
        )
        
        # === NEW: Quasi-1D Gasdynamic Pipe Models ===
        # Feature flag: use True for new gasdynamics, False for legacy
        self.use_quasi_1d_pipes = True
        
        # Expansion chamber with realistic geometry
        self.exhaust_pipe = ExpansionChamberPipe(
            header_length=EXHAUST_HEADER_LENGTH_M,
            header_diameter=EXHAUST_HEADER_DIAMETER_M,
            diffuser_length=EXHAUST_DIFFUSER_LENGTH_M,
            diffuser_start_dia=EXHAUST_DIFFUSER_START_DIA_M,
            diffuser_end_dia=EXHAUST_DIFFUSER_END_DIA_M,
            belly_length=EXHAUST_BELLY_LENGTH_M,
            belly_diameter=EXHAUST_BELLY_DIAMETER_M,
            baffle_length=EXHAUST_BAFFLE_LENGTH_M,
            baffle_start_dia=EXHAUST_BAFFLE_START_DIA_M,
            baffle_end_dia=EXHAUST_BAFFLE_END_DIA_M,
            num_segments=PIPE_NUM_SEGMENTS,
        )
        
        # Intake runner for pressure wave tuning
        self.intake_pipe = IntakeRunnerPipe(
            length=INTAKE_RUNNER_LENGTH_M,
            diameter=INTAKE_RUNNER_DIAMETER_M,
            num_segments=max(3, PIPE_NUM_SEGMENTS - 2),  # Fewer cells for intake
        )
        
        # Friction state
        self._friction_breakdown = None  # type: FrictionBreakdown | None
        
        # === NEW: Physical Carburetor Model ===
        # Feature flag: use True for physical carburetor with droplet evaporation
        self.use_physical_carburetor = True
        
        # Physical carburetor with venturi and fuel droplets
        self._carburetor = CarburetorModel()
        
        # Initialize subsystems (sub_steps, etc.)
        self._initialize_subsystems()
        
        # === TRIMMING-PARAMETRAR ===
        # Dessa kan justeras för att simulera olika trimningsalternativ
        
        # Motor-geometri
        self.stroke_multiplier = 1.0  # 0.8-1.2, ändrar slagläge
        self.bore_multiplier = 1.0    # 0.9-1.15, ändrar borr-diameter
        self.compression_ratio = 7.5  # 6.0-10.0, kompressionsförhållande
        self.rod_length = CON_ROD_M    # 0.08-0.12, plejlstångslängd
        
        # Scavenging & portar
        self.transfer_port_height = TRANSFER_PORT_OPEN_M  # 0.025-0.045
        self.exhaust_port_height = EXHAUST_PORT_OPEN_M    # 0.018-0.035
        self.exhaust_port_width = EXHAUST_PORT_WIDTH_M    # 0.030-0.050
        self.transfer_port_width = TRANSFER_PORT_WIDTH_M  # 0.025-0.045
        self.port_overlap = 0.0       # -5 till +10 grader
        
        # Avgassystem (expansion chamber)
        self.pipe_resonance_freq = PIPE_RESONANCE_FREQ_HZ  # 80-200 Hz
        self.pipe_length = 1.0        # 0.5-1.5, relativ pip-längd
        self.pipe_q_factor = 2.5      # 1.5-4.0, Q-faktor
        
        # Tändning & förbränning
        self.burn_duration_factor = 1.0   # 0.7-1.4, förbränningstid
        self.combustion_efficiency = 1.0  # 0.7-1.0, förbränningsverkningsgrad
        self.spark_duration = 0.002       # 0.001-0.005, gnistlängd
        self.ignition_advance_range = 18.0 # 10-30 grader
        
        # Bränsle & insug
        self.fuel_evap_rate_cr = 1.0    # 0.5-2.0, vevhus-förångning
        self.fuel_evap_rate_cyl = 1.0   # 0.5-2.0, cylinder-förångning
        self.reed_stiffness = 1200.0    # 800-2000, vevhusventil-styvhet
        # idle_circuit_strength is calculated dynamically by _idle_circuit_strength() method
        
        # Mekaniskt
        self.inertia_multiplier = 1.0   # 0.6-1.5, tröghet
        self.friction_factor = 1.0      # 0.7-1.3, friktionsfaktor
        self.mechanical_efficiency = 0.85  # 0.75-0.92
        self.con_rod_mass = 0.12  # kg, connecting rod mass for oscillating inertia
        
        # Apply trimming parameters to derived values
        self._apply_trimming_parameters()
        
    def _calculate_exhaust_flow_from_pipe(
        self, p_cyl: float, T_cyl: float, a_exh: float, p_pipe: float
    ) -> float:
        """Calculate exhaust mass flow using pipe pressure (simplified orifice model).
        
        This replaces the legacy pipe model with a direct calculation using
        the quasi-1D pipe pressure at the port.
        
        Args:
            p_cyl: Cylinder pressure (Pa)
            T_cyl: Cylinder temperature (K)
            a_exh: Exhaust port area (m²)
            p_pipe: Pipe pressure at port (Pa)
            
        Returns:
            Mass flow rate (kg/s), positive = outflow, negative = backflow
        """
        if a_exh < 1e-9:
            return 0.0
            
        # Discharge coefficient
        c_d = 0.7  # DISCHARGE_COEF_EXHAUST
        
        if p_cyl > p_pipe:
            # Outflow to pipe
            return Thermodynamics.mass_flow(c_d, a_exh, p_cyl, T_cyl, p_pipe)
        else:
            # Backflow from pipe (simplified - assume pipe gas is cooler)
            T_pipe = T_cyl * 0.9
            return -Thermodynamics.mass_flow(c_d, a_exh, p_pipe, T_pipe, p_cyl)

    def _initialize_subsystems(self) -> None:
        """Initialize subsystem parameters after main init."""
        # Sub-stepping for better angular resolution
        self.sub_steps = 4  # Number of sub-steps per timestep (1-8)
        
        # For debug
        self.last_d_q_comb = 0.0
    
    def _apply_trimming_parameters(self) -> None:
        """Apply trimming parameters to derived geometry and physics values."""
        # Apply geometry multipliers
        self.R = HALF_STROKE_M * self.stroke_multiplier  # Crank radius
        self.L = self.rod_length  # Connecting rod length
        self.B = BORE_M * self.bore_multiplier  # Bore diameter
        self.A_p = math.pi * (self.B / 2) ** 2  # Piston area
        self.V_d = self.A_p * 2 * self.R  # Displacement
        
        # Calculate clearance volume from compression ratio
        # CR = (V_d + V_c) / V_c => V_c = V_d / (CR - 1)
        if self.compression_ratio > 1.0:
            self.V_c = self.V_d / (self.compression_ratio - 1.0)
        else:
            self.V_c = CLEARANCE_VOLUME_M3
        
        # Apply port timing dimensions
        self.x_exh = self.exhaust_port_height
        self.x_tr = self.transfer_port_height
        self.w_exh = self.exhaust_port_width
        self.w_tr = self.transfer_port_width
        
        # Update kinematics calculator with modified geometry
        self._kinematics = SliderCrankKinematics()
        # Override kinematics geometry parameters
        self._kinematics.R = self.R
        self._kinematics.L = self.L
        self._kinematics.A_p = self.A_p
        self._kinematics.V_c = self.V_c
        
        # Apply inertia multiplier with connecting rod oscillating inertia
        # Base inertia from crankshaft, piston, and oscillating rod
        base_inertia = 0.008 * self.num_cylinders
        # Connecting rod equivalent inertia (approximation)
        # I_rod ≈ m_rod * R^2 * (0.5 + 0.5*(R/L)^2)
        lambda_ratio = self.R / max(self.L, 1e-9)
        rod_inertia = self.con_rod_mass * self.num_cylinders * (self.R ** 2) * (0.5 + 0.5 * lambda_ratio ** 2)
        self.I_engine = (base_inertia + rod_inertia) * self.inertia_multiplier
    
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
    
    def set_gasdynamic_model(self, use_quasi_1d: bool) -> None:
        """Toggle between legacy and quasi-1D gasdynamic models.
        
        Args:
            use_quasi_1d: True for quasi-1D finite-volume, False for legacy lumped model
        """
        self.use_quasi_1d_pipes = use_quasi_1d
        if use_quasi_1d:
            # Reset pipes to atmospheric conditions
            for seg in self.exhaust_pipe.segments:
                density = P_ATM / (R_GAS * T_ATM)
                seg.set_primitive(density, 0.0, P_ATM)
            for seg in self.intake_pipe.segments:
                density = P_ATM / (R_GAS * T_ATM)
                seg.set_primitive(density, 0.0, P_ATM)
    
    def get_exhaust_pipe_status(self) -> dict:
        """Get current status of exhaust pipe (quasi-1D model).
        
        Returns:
            Dictionary with pipe statistics
        """
        if not self.use_quasi_1d_pipes:
            return {
                'model': 'legacy',
                'pressure': self.p_pipe,
                'amplitude': self.pipe_amplitude,
            }
        
        pressures = [seg.pressure for seg in self.exhaust_pipe.segments]
        temps = [seg.temperature for seg in self.exhaust_pipe.segments]
        velocities = [seg.velocity for seg in self.exhaust_pipe.segments]
        
        return {
            'model': 'quasi-1d',
            'segments': self.exhaust_pipe.num_segments,
            'port_pressure': self.exhaust_pipe.get_port_pressure(is_left=True),
            'avg_pressure': sum(pressures) / len(pressures),
            'min_pressure': min(pressures),
            'max_pressure': max(pressures),
            'avg_temperature': sum(temps) / len(temps),
            'max_velocity': max(abs(v) for v in velocities),
        }
    
    def set_scavenging_model(self, use_advanced: bool) -> None:
        """Toggle between legacy and advanced scavenging models.
        
        Args:
            use_advanced: True for multi-zone RPM-dependent model, False for legacy
        """
        self.use_advanced_scavenging = use_advanced
    
    def get_scavenging_status(self) -> dict:
        """Get current scavenging model status.
        
        Returns:
            Dictionary with scavenging statistics
        """
        if not self.use_advanced_scavenging:
            return {
                'model': 'legacy',
                'trapping_efficiency': self.trapping_efficiency,
            }
        
        return {
            'model': 'advanced',
            'trapping_efficiency': self.trapping_efficiency,
            'optimal_rpm': self._advanced_scavenging.optimal_rpm,
            'base_scavenging_efficiency': self._advanced_scavenging.base_scavenging_efficiency,
        }
    
    def set_combustion_model(self, use_advanced: bool) -> None:
        """Toggle between legacy and advanced combustion models.
        
        Args:
            use_advanced: True for residual-sensitive model, False for legacy
        """
        self.use_advanced_combustion = use_advanced
    
    def get_combustion_status(self) -> dict:
        """Get current combustion model status.
        
        Returns:
            Dictionary with combustion statistics
        """
        if not self.use_advanced_combustion:
            return {
                'model': 'legacy',
                'residual_fraction': self.residual_fraction,
                'charge_purity': self.charge_purity,
            }
        
        return {
            'model': 'advanced',
            'residual_fraction': self.residual_fraction,
            'charge_purity': self.charge_purity,
            'charge_temperature': self.charge_temperature,
        }
    
    def set_thermodynamics_model(self, use_enhanced: bool) -> None:
        """Toggle between legacy and enhanced thermodynamics models.
        
        Args:
            use_enhanced: True for enhanced model with wall temperature dynamics, False for legacy
        """
        self.use_enhanced_thermodynamics = use_enhanced
    
    def get_thermodynamics_status(self) -> dict:
        """Get current thermodynamics model status.
        
        Returns:
            Dictionary with thermodynamics statistics
        """
        if not self.use_enhanced_thermodynamics:
            return {
                'model': 'legacy',
            }
        
        return {
            'model': 'enhanced',
            'cylinder_wall_temp': self._enhanced_thermo.t_wall_cylinder,
            'crankcase_wall_temp': self._enhanced_thermo.t_wall_crankcase,
        }
    
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
            self.p_pipe, self.pipe_phase, self.pipe_amplitude,
            self.rpm_ema, self.torque_ema, self.power_ema,
        ]
        
        for value in critical_values:
            if not math.isfinite(value):
                return False
        
        # Check cylinders
        for cyl in self.cylinders:
            cyl_values = [
                cyl.p_cyl,
                cyl.T_cyl,
                cyl.m_air, cyl.m_fuel, cyl.m_burned,
                cyl.burn_fraction, cyl.lambda_value
            ]
            if any(not math.isfinite(v) for v in cyl_values):
                return False
            if not (MIN_PRESSURE <= cyl.p_cyl <= MAX_CYLINDER_PRESSURE):
                return False
            if not (0.0 <= cyl.burn_fraction <= 1.0):
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
        
        # Check exhaust pipe pressure bounds
        if not (MIN_PRESSURE <= self.p_pipe <= 1000000.0):
            return False
        
        return self.omega >= 0
    
    def _calculate_crankcase_pressure(self, v_cr: float) -> float:
        """Calculate crankcase pressure."""
        m_cr = self.m_air_cr + self.m_fuel_cr + self.m_residual_cr
        v_cr = max(v_cr, EPSILON_VOLUME)
        p_cr = m_cr * R_GAS * self.T_cr / v_cr
        p_cr = clamp(p_cr, MIN_CRANKCASE_PRESSURE, MAX_CRANKCASE_PRESSURE)
        return p_cr
    
    def _step_core(self, dt: float, starter_active: bool = False) -> EngineSnapshot:
        """Execute one physics timestep with multi-cylinder support."""
        if not math.isfinite(dt) or dt <= 0.0:
            raise ValueError("dt must be a positive finite value")

        if dt > 0.01:
            dt = 0.01

        if not self.cylinders:
            raise RuntimeError("EnginePhysics has no cylinders to simulate")
        
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
        
        # === NEW: Update intake pipe if using quasi-1D model ===
        if self.use_quasi_1d_pipes:
            # Set intake pipe boundaries
            self.intake_pipe.set_left_boundary_atmosphere(P_ATM, T_ATM)
            self.intake_pipe.set_crankcase_connection(p_cr, self.T_cr, 0.0)  # Port area updated per-cylinder
            # Step intake pipe
            self.intake_pipe.step(dt)
            # Get pressure at reed valve for intake calculation
            intake_pipe_pressure = self.intake_pipe.get_pressure_at_reed_valve()
        else:
            intake_pipe_pressure = P_ATM
        
        intake_cond = self._flow_calc.calculate_intake_conditions(
            p_cr, self.throttle, self.idle_fuel_trim
        )
        # Override with pipe pressure if using quasi-1D
        if self.use_quasi_1d_pipes:
            intake_cond.pressure = intake_pipe_pressure
        
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
            # === NEW: Physical Carburetor Model ===
            if self.use_physical_carburetor:
                # Update carburetor with venturi physics
                carb_state = self._carburetor.update(
                    dt=dt,
                    p_upstream=P_ATM,
                    T_upstream=T_ATM,
                    throttle_position=self.throttle,
                    choke_position=0.0,  # Choke could be added as a control input
                )
                
                # Use carburetor air flow instead of simple calculation
                dm_air_in = carb_state.m_dot_air
                
                # Update fuel droplets in intake/crankcase
                # Wall position represents distance to crankcase (approximate)
                wall_position = 0.15  # m, typical intake runner length
                vaporized, wall_film, remaining = self._carburetor.update_droplets(
                    dt=dt,
                    p_gas=p_cr,
                    T_gas=self.T_cr,
                    v_gas=dm_air_in / (0.001 * 1.2),  # Approximate velocity
                    wall_position=wall_position,
                )
                
                # Add wall film to crankcase fuel film
                self.fuel_film_cr += wall_film
                
                # Evaporate existing fuel film
                film_evap_rate = 2.0 + 0.03 * max(0.0, self.T_cr - T_ATM)  # Temperature dependent
                film_evaporated = min(self.fuel_film_cr, self.fuel_film_cr * film_evap_rate * dt)
                self.fuel_film_cr -= film_evaporated
                
                # Total fuel entering crankcase: vaporized droplets + film evaporation
                dm_fuel_in = vaporized + film_evaporated
                
            else:
                # Legacy fuel calculation
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
        
        # === NEW: Setup exhaust pipe boundaries before cylinder loop ===
        if self.use_quasi_1d_pipes:
            self.exhaust_pipe.set_right_boundary_atmosphere(P_ATM, T_ATM)
            # Left boundary connected to cylinder, updated per-cylinder
        
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
            
            # Exhaust flow - legacy or quasi-1D
            if self.use_quasi_1d_pipes:
                # Update exhaust pipe boundary for this cylinder
                self.exhaust_pipe.set_left_boundary_cylinder(
                    p_cyl, cyl.T_cyl, ports.exhaust
                )
                # Get pressure at port from pipe
                p_exhaust = self.exhaust_pipe.get_port_pressure(is_left=True)
                # Calculate mass flow using pipe pressure
                dm_exh = self._calculate_exhaust_flow_from_pipe(
                    p_cyl, cyl.T_cyl, ports.exhaust, p_exhaust
                )
            else:
                # Legacy exhaust pipe model
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
            transferred_air = 0.0
            transferred_fuel = 0.0
            transferred_burned = 0.0
            
            if dm_tr > 0:
                transfer_mass = min(dm_tr * dt, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr)
                crankcase_total = max(EPSILON_MASS, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr)
                
                cr_fa_ratio = self.m_fuel_cr / max(1e-9, self.m_air_cr)
                if cr_fa_ratio > 0.3:
                    transfer_mass *= 0.1
                
                # === NEW: Use advanced multi-zone scavenging model ===
                if self.use_advanced_scavenging:
                    # Calculate RPM for scavenging model
                    rpm = self.omega * 30 / math.pi
                    
                    # Calculate port overlap in degrees
                    overlap_deg = 0.0
                    if ports.exhaust > 0 and ports.transfer > 0:
                        overlap_deg = self.port_overlap  # Use trimming parameter
                    
                    # Use advanced scavenging model
                    zones, metrics = self._advanced_scavenging.calculate_multi_zone_scavenging(
                        m_fresh_delivered=transfer_mass,
                        m_residual_initial=cyl.m_burned,
                        m_fresh_initial=cyl.m_air + cyl.m_fuel,
                        rpm=rpm,
                        exhaust_port_height=self.exhaust_port_height,
                        transfer_port_height=self.transfer_port_height,
                        port_overlap_deg=overlap_deg,
                        cylinder_volume=kin.v_cyl,
                    )
                    
                    # Apply multi-zone results
                    # Fresh charge from crankcase to cylinder
                    transferred_air = zones.fresh_direct * (self.m_air_cr / crankcase_total)
                    transferred_fuel = zones.fresh_direct * (self.m_fuel_cr / crankcase_total)
                    # Note: transferred_burned is NOT from crankcase, it's residuals being pushed out of cylinder
                    transferred_burned = 0.0  # Crankcase has no burned gas to transfer
                    
                    # Short-circuit loss from advanced model (fresh charge lost to exhaust)
                    short_circuit_loss = zones.short_circuit
                    
                    # Update cylinder masses based on zones
                    cyl.m_burned = zones.total_residual
                    cyl.m_air += zones.fresh_direct * (self.m_air_cr / crankcase_total)
                    cyl.m_fuel += zones.fresh_direct * (self.m_fuel_cr / crankcase_total)
                    
                    # Track combustion state variables for advanced combustion
                    self.residual_fraction = metrics.residual_fraction
                    self.charge_purity = metrics.fresh_fraction
                    self.charge_temperature = cyl.T_cyl
                    
                    # Update efficiency tracking
                    self.trapping_efficiency = metrics.trapping_efficiency
                else:
                    # Legacy short-circuit loss during port overlap
                    short_circuit_loss = 0.0
                    if ports.exhaust > 0 and ports.transfer > 0:
                        overlap_fraction = min(ports.exhaust, ports.transfer) / max(ports.exhaust, ports.transfer, 1e-9)
                        short_circuit_fraction = 0.15 + 0.10 * overlap_fraction
                        short_circuit_loss = transfer_mass * short_circuit_fraction
                        transfer_mass -= short_circuit_loss
                    
                    transferred_air = transfer_mass * self.m_air_cr / crankcase_total
                    transferred_fuel = transfer_mass * self.m_fuel_cr / crankcase_total
                    transferred_burned = transfer_mass * self.m_residual_cr / crankcase_total
                
                dm_air_tr = transferred_air / max(dt, 1e-6)
                dm_fuel_tr = transferred_fuel / max(dt, 1e-6)
                dm_burned_tr = transferred_burned / max(dt, 1e-6)
                
                # Account for short-circuit loss in crankcase mass balance
                self.m_air_cr -= transferred_air + (short_circuit_loss * self.m_air_cr / crankcase_total)
                self.m_fuel_cr -= transferred_fuel + (short_circuit_loss * self.m_fuel_cr / crankcase_total)
                self.m_residual_cr -= transferred_burned
                total_dm_out_cr += (transferred_air + transferred_fuel + transferred_burned + short_circuit_loss) / dt
                
                cyl.add_transfer_with_fuel_film(transferred_air, transferred_fuel, transferred_burned, throttle_factor)
            
            # Exhaust mass update
            dm_air_exh = 0.0
            dm_fuel_exh = 0.0
            dm_burned_exh = 0.0
            exhausted_air = 0.0
            exhausted_fuel = 0.0
            exhausted_burned = 0.0
            backflow_mass = 0.0
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
                    # Backflow is a mixture: mostly burned gas with some unburned charge
                    # Typical: 85% burned, 15% air/fuel (from short-circuiting in pipe)
                    cyl.m_burned += backflow_mass * 0.85
                    cyl.m_air += backflow_mass * 0.1275  # 15% * 0.85 air fraction
                    cyl.m_fuel += backflow_mass * 0.0225  # 15% * 0.15 fuel fraction
            
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
            if self.use_advanced_combustion:
                heat = cyl.update_combustion(self.theta, kin.x, dt, 
                    self.ignition_angle_deg, self.ignition_enabled, 
                    self.fuel_cutoff, throttle_factor, self.omega,
                    advanced_combustion_model=self._advanced_combustion,
                    residual_fraction=self.residual_fraction,
                    charge_purity=self.charge_purity,
                    charge_temperature=self.charge_temperature)
            else:
                heat = cyl.update_combustion(self.theta, kin.x, dt, 
                    self.ignition_angle_deg, self.ignition_enabled, 
                    self.fuel_cutoff, throttle_factor, self.omega)
            
            # Energy balance with mass-change internal energy correction
            # dU = dQ_comb + h_in*dm_in - p*dV + T*C_V*dm_net
            # where dm_net accounts for internal energy carried by mass change
            d_v_cyl = self.A_p * kin.dx_dtheta * self.omega * dt
            dm_in_cyl = (transferred_air + transferred_fuel + transferred_burned) if dm_tr > 0 else 0.0
            dm_out_cyl = (exhausted_air + exhausted_fuel + exhausted_burned) if dm_exh >= 0 else 0.0
            dm_backflow_cyl = backflow_mass if dm_exh < 0 and not self.fuel_cutoff else 0.0
            dm_net_cyl = dm_in_cyl - dm_out_cyl + dm_backflow_cyl
            
            # Temperature-dependent gas properties
            cyl_burn_frac = cyl.m_burned / max(EPSILON_MASS, cyl.m_air + cyl.m_fuel + cyl.m_burned)
            cyl_gas = gas_properties(cyl.T_cyl, cyl_burn_frac)
            cr_gas = gas_properties(self.T_cr, 0.0)  # Crankcase is mostly fresh charge
            
            h_in = self.T_cr * cr_gas.c_p * dm_in_cyl
            d_q = heat + h_in - p_cyl * d_v_cyl + cyl.T_cyl * cyl_gas.c_v * dm_net_cyl
            m_avg = max(EPSILON_MASS, cyl.m_air + cyl.m_fuel + cyl.m_burned)
            cyl.T_cyl = max(T_ATM, cyl.T_cyl + d_q / (m_avg * cyl_gas.c_v))
            
            # Cooling (Woschni heat transfer)
            v_piston = kin.dx_dtheta * self.omega  # Piston velocity (m/s)
            cyl.apply_cooling(dt, p_cyl, v_piston, cyl.combustion_active)
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
        
        # === NEW: Step exhaust pipe after all cylinder updates ===
        if self.use_quasi_1d_pipes:
            _ = self.exhaust_pipe.step(dt)  # Returns actual dt used, ignored here
            # Update legacy pipe state for backward compatibility in snapshot
            self._exhaust_pipe_pressure = self.exhaust_pipe.get_port_pressure(is_left=True)
            self.p_pipe = self._exhaust_pipe_pressure  # For legacy compatibility
        
        # 5. Crankcase energy balance
        sum_d_v_cyl = sum(self.A_p * d['kin'].dx_dtheta * self.omega * dt for d in cyl_data)
        d_v_cr = -sum_d_v_cyl
        
        dm_in_total = dm_air_in + dm_fuel_in
        dm_net_cr = (dm_in_total - total_dm_out_cr) * dt
        
        # Crankcase gas properties (mostly fresh charge)
        cr_gas = gas_properties(self.T_cr, 0.0)
        
        h_in_cr = T_ATM * C_P * dm_in_total * dt  # Intake at atmospheric conditions
        h_out_cr = self.T_cr * cr_gas.c_p * total_dm_out_cr * dt
        d_q_cr = h_in_cr - h_out_cr - p_cr * d_v_cr + self.T_cr * cr_gas.c_v * dm_net_cr
        m_avg_cr = max(EPSILON_MASS, self.m_air_cr + self.m_fuel_cr + self.m_residual_cr)
        self.T_cr = max(T_ATM, self.T_cr + d_q_cr / (m_avg_cr * cr_gas.c_v))
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
        
        # Compute friction using FrictionModel (simple model for backward compatibility)
        # Using get_simple_friction to maintain existing behavior while integrating the class
        friction_torque = self._friction_model.get_simple_friction(self.omega) * self.num_cylinders
        # Add throttle-dependent pumping loss (not in FrictionModel simple version)
        throttle_pump_loss = (1.0 - self.throttle) * 2.0 * self.num_cylinders
        friction_torque += throttle_pump_loss
        # Apply friction_factor tuning multiplier
        friction_torque *= self.friction_factor
        
        # Engine brake (fuel cutoff)
        extra_brake = 8.0 if self.fuel_cutoff and not starter_active else 0.0
        
        final_torque = net_torque + starter_torque - friction_torque - extra_brake
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
            self.last_cycle_torque = self.cycle_work / (2 * math.pi) - friction_torque
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
        
        if primary_cyl_state is None or primary_ports is None:
            raise RuntimeError("Primary cylinder state was not initialized")
        
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
            friction_breakdown=self._friction_breakdown,
            cylinders=all_cyl_states
        )
    
    def step(self, dt: float, starter_active: bool = False) -> EngineSnapshot:
        """Execute one physics timestep with sub-stepping for better angular resolution.
        
        Divides dt into multiple sub-steps to improve accuracy at high RPM.
        """
        if not math.isfinite(dt) or dt <= 0.0:
            raise ValueError("dt must be a positive finite value")
        
        # Cap max timestep
        if dt > 0.01:
            dt = 0.01
        
        # Divide into sub-steps
        sub_dt = dt / self.sub_steps
        
        # Run all sub-steps (only return snapshot from last one)
        snapshot = None
        for _ in range(self.sub_steps):
            snapshot = self._step_core(sub_dt, starter_active)
        
        return snapshot
    
    def snapshot(self) -> EngineSnapshot:
        """Return current state snapshot without advancing simulation."""
        if not self.cylinders:
            raise RuntimeError("EnginePhysics has no cylinders to snapshot")

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

        if primary_cyl_state is None or primary_ports is None:
            raise RuntimeError("Primary cylinder state was not initialized")
        
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
            friction_breakdown=self._friction_breakdown,
            cylinders=all_cyl_states
        )
