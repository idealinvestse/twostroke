"""Mass flow calculations for engine ports and valves.

Handles intake (reed valve), transfer, and exhaust flows,
including the tuned exhaust pipe resonance model.
"""

import math
from dataclasses import dataclass

from physics.constants import (
    P_ATM,
    T_ATM,
    MAX_INTAKE_AREA_M2,
    DISCHARGE_COEF_EXHAUST,
    DISCHARGE_COEF_TRANSFER,
    DISCHARGE_COEF_INTAKE_MAIN,
    DISCHARGE_COEF_INTAKE_IDLE,
    REED_STIFFNESS,
    REED_DAMPING,
    REED_PRESSURE_COEF,
    PIPE_RESONANCE_FREQ_HZ,
    PIPE_Q_FACTOR,
    PIPE_AMPLITUDE_DECAY,
    PIPE_MAX_SUCTION_PA,
    PIPE_MAX_PRESSURE_PA,
)
from physics.thermodynamics import Thermodynamics
from physics.utils import clamp, gaussian_falloff


@dataclass
class PortAreas:
    """Flow areas for engine ports."""
    exhaust: float     # m²
    transfer: float    # m²
    intake: float      # m²
    intake_main: float # m²
    intake_idle: float # m²


@dataclass
class IntakeConditions:
    """Calculated intake system state."""
    throttle_factor: float
    idle_circuit: float
    pressure: float    # Pa
    area_main: float   # m²
    area_idle: float   # m²


@dataclass
class ReedValveState:
    """Reed valve dynamics state."""
    opening: float     # 0-1
    velocity: float    # opening rate


@dataclass
class ExhaustPipeState:
    """Tuned exhaust pipe resonance state."""
    pressure: float    # Pa
    phase: float       # radians
    amplitude: float   # Pa


class FlowCalculator:
    """Calculate mass flows through engine ports."""
    
    def __init__(self) -> None:
        self.A_in_max = MAX_INTAKE_AREA_M2
    
    def calculate_port_areas(
        self,
        x: float,
        x_exh: float,
        w_exh: float,
        x_tr: float,
        w_tr: float,
    ) -> PortAreas:
        """Calculate open port areas based on piston position.
        
        Args:
            x: Piston position from TDC (m)
            x_exh: Exhaust port opening position (m from TDC)
            w_exh: Exhaust port width (m)
            x_tr: Transfer port opening position (m from TDC)
            w_tr: Transfer port width (m)
            
        Returns:
            PortAreas with calculated flow areas
        """
        a_exh = max(0.0, x - x_exh) * w_exh
        a_tr = max(0.0, x - x_tr) * w_tr
        
        return PortAreas(
            exhaust=a_exh,
            transfer=a_tr,
            intake=0.0,  # Set later based on reed valve
            intake_main=0.0,
            intake_idle=0.0,
        )
    
    def calculate_intake_conditions(
        self,
        p_cr: float,
        throttle: float,
        idle_fuel_trim: float,
    ) -> IntakeConditions:
        """Calculate intake system conditions.
        
        Models main throttle and idle circuit.
        
        Args:
            p_cr: Crankcase pressure (Pa)
            throttle: Throttle position (0-1)
            idle_fuel_trim: Idle mixture adjustment (0.4-2.0)
            
        Returns:
            IntakeConditions with flow areas and pressure
        """
        # Throttle flow curve (exponent gives non-linear response)
        throttle_factor = 0.04 + 0.96 * (throttle ** 1.35)
        
        # Idle circuit strength (active only at low throttle)
        idle_circuit = max(0.0, min(1.0, (0.32 - throttle) / 0.32))
        
        # Intake pressure model
        p_intake = min(P_ATM, 
            P_ATM * (0.35 + 0.65 * throttle_factor) 
            + P_ATM * 0.04 * idle_circuit * idle_fuel_trim
        )
        
        if p_intake <= p_cr:
            # No flow possible
            return IntakeConditions(
                throttle_factor=throttle_factor,
                idle_circuit=idle_circuit,
                pressure=p_intake,
                area_main=0.0,
                area_idle=0.0,
            )
        
        # Calculate flow areas
        a_main = self.A_in_max * throttle_factor
        a_idle = self.A_in_max * 0.09 * idle_circuit * (0.35 + 0.65 * idle_fuel_trim)
        
        return IntakeConditions(
            throttle_factor=throttle_factor,
            idle_circuit=idle_circuit,
            pressure=p_intake,
            area_main=a_main,
            area_idle=a_idle,
        )
    
    def update_reed_valve(
        self,
        reed: ReedValveState,
        p_intake: float,
        p_cr: float,
        dt: float,
    ) -> ReedValveState:
        """Update reed valve dynamics.
        
        Simple spring-mass-damper model.
        
        Args:
            reed: Current reed valve state
            p_intake: Intake pressure (Pa)
            p_cr: Crankcase pressure (Pa)
            dt: Timestep (s)
            
        Returns:
            Updated ReedValveState
        """
        pressure_diff = p_intake - p_cr
        
        # Spring-mass-damper dynamics
        force = (
            pressure_diff * REED_PRESSURE_COEF
            - reed.opening * REED_STIFFNESS
            - reed.velocity * REED_DAMPING
        )
        
        velocity = reed.velocity + force * dt
        opening = reed.opening + velocity * dt
        
        # Hard limits
        if opening < 0.0:
            opening = 0.0
            velocity = 0.0
        elif opening > 1.0:
            opening = 1.0
            velocity = 0.0
        
        return ReedValveState(opening=opening, velocity=velocity)
    
    def calculate_exhaust_flow(
        self,
        p_cyl: float,
        T_cyl: float,
        a_exh: float,
        pipe: ExhaustPipeState,
    ) -> float:
        """Calculate exhaust mass flow.
        
        Positive = outflow, negative = backflow from pipe.
        
        Args:
            p_cyl: Cylinder pressure (Pa)
            T_cyl: Cylinder temperature (K)
            a_exh: Exhaust port area (m²)
            pipe: Exhaust pipe state
            
        Returns:
            Mass flow rate (kg/s)
        """
        if p_cyl > pipe.pressure:
            # Outflow to pipe
            return Thermodynamics.mass_flow(
                DISCHARGE_COEF_EXHAUST, a_exh, p_cyl, T_cyl, pipe.pressure
            )
        else:
            # Backflow from pipe
            return -Thermodynamics.mass_flow(
                DISCHARGE_COEF_EXHAUST, a_exh, pipe.pressure, T_cyl * 0.9, p_cyl
            )
    
    def update_exhaust_pipe(
        self,
        pipe: ExhaustPipeState,
        dm_exh: float,
        a_exh: float,
        omega: float,
        dt: float,
    ) -> ExhaustPipeState:
        """Update tuned exhaust pipe resonance.
        
        Models pressure wave reflection and resonance.
        
        Args:
            pipe: Current pipe state
            dm_exh: Mass flow rate (kg/s)
            a_exh: Exhaust port area (m²)
            omega: Engine angular velocity (rad/s)
            dt: Timestep (s)
            
        Returns:
            Updated ExhaustPipeState
        """
        # Update phase
        phase = pipe.phase + omega * dt * 2.0  # Double frequency
        phase %= 2.0 * math.pi
        
        # Calculate suction effect
        suction = math.sin(phase) * pipe.amplitude
        
        # Decay when exhaust port closed
        amplitude = pipe.amplitude
        if a_exh < 1e-6:
            amplitude *= math.exp(-PIPE_AMPLITUDE_DECAY * dt)
        
        # Add energy from exhaust flow
        current_hz = omega / (2 * math.pi)
        hz_diff = abs(current_hz - PIPE_RESONANCE_FREQ_HZ)
        
        f_res = max(PIPE_RESONANCE_FREQ_HZ, 1e-6)
        q = max(PIPE_Q_FACTOR, 1e-6)
        
        # Gaussian resonance curve
        resonance = gaussian_falloff(hz_diff, f_res / q)
        
        # Add energy from mass flow
        amplitude += dm_exh * dt * 60000.0 * resonance
        
        # Clamp to realistic bounds
        suction = clamp(suction, -PIPE_MAX_SUCTION_PA, PIPE_MAX_PRESSURE_PA)
        pressure = P_ATM - suction
        
        return ExhaustPipeState(
            pressure=pressure,
            phase=phase,
            amplitude=amplitude,
        )
    
    def calculate_transfer_flow(
        self,
        p_cr: float,
        T_cr: float,
        p_cyl: float,
        a_tr: float,
    ) -> float:
        """Calculate transfer port mass flow.
        
        Args:
            p_cr: Crankcase pressure (Pa)
            T_cr: Crankcase temperature (K)
            p_cyl: Cylinder pressure (Pa)
            a_tr: Transfer port area (m²)
            
        Returns:
            Mass flow rate (kg/s), positive = crankcase to cylinder
        """
        if p_cr > p_cyl:
            return Thermodynamics.mass_flow(
                DISCHARGE_COEF_TRANSFER, a_tr, p_cr, T_cr, p_cyl
            )
        return 0.0
    
    def calculate_intake_flow(
        self,
        intake: IntakeConditions,
        p_cr: float,
        reed_opening: float,
    ) -> tuple[float, float]:
        """Calculate intake mass flow.
        
        Args:
            intake: Intake conditions
            p_cr: Crankcase pressure (Pa)
            reed_opening: Reed valve opening (0-1)
            
        Returns:
            (air_mass_flow, fuel_mass_flow) in kg/s
        """
        if intake.pressure <= p_cr:
            return 0.0, 0.0
        
        # Calculate air flows
        dm_air_main = Thermodynamics.mass_flow(
            DISCHARGE_COEF_INTAKE_MAIN,
            intake.area_main * reed_opening,
            intake.pressure,
            T_ATM,
            p_cr,
        )
        dm_air_idle = Thermodynamics.mass_flow(
            DISCHARGE_COEF_INTAKE_IDLE,
            intake.area_idle * reed_opening,
            P_ATM,
            T_ATM,
            p_cr,
        )
        
        return dm_air_main, dm_air_idle
