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
    MAX_PIPE_AMPLITUDE,
)
from physics.thermodynamics import Thermodynamics
from physics.utils import clamp, gaussian_falloff
from enum import Enum


class ScavengingModel(Enum):
    """Scavenging model types for 2-stroke engines.

    - PERFECT_DISPLACEMENT: No mixing, fresh charge completely displaces residuals
    - PERFECT_MIXING: Fresh charge mixes instantly with cylinder contents
    - COMBINED: Realistic model with partial mixing and short-circuiting
    """
    PERFECT_DISPLACEMENT = "perfect_displacement"
    PERFECT_MIXING = "perfect_mixing"
    COMBINED = "combined"


@dataclass
class ScavengingState:
    """State of scavenging process in cylinder."""
    # Charge composition
    fresh_charge_mass: float       # Fresh air+fuel in cylinder (kg)
    residual_mass: float           # Burned residual gas (kg)
    total_mass: float              # Total cylinder mass (kg)

    # Efficiency metrics
    charge_purity: float           # Fraction of fresh charge (0-1)
    scavenging_efficiency: float   # Fraction of residuals displaced (0-1)
    trapping_efficiency: float     # Fraction of fresh charge retained (0-1)
    short_circuit_loss: float      # Fresh charge lost directly to exhaust (kg)

    # Delivery ratio
    delivery_ratio: float          # Delivered fresh charge / displacement volume fill


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
        
        # Cap amplitude to physical limits (~0.8 bar peak)
        amplitude = min(amplitude, MAX_PIPE_AMPLITUDE)
        
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


class ScavengingCalculator:
    """Calculate scavenging efficiency and charge composition.

    Implements multiple scavenging models for 2-stroke engines:
    - Perfect displacement: Fresh charge pushes residuals out without mixing
    - Perfect mixing: Instantaneous mixing of fresh charge with cylinder contents
    - Combined: Realistic model with displacement and mixing phases
    """

    def __init__(
        self,
        model: ScavengingModel = ScavengingModel.COMBINED,
        short_circuit_fraction: float = 0.15,
        displacement_efficiency: float = 0.7,
    ) -> None:
        """
        Args:
            model: Scavenging model type
            short_circuit_fraction: Fraction of transfer flow lost directly to exhaust (0-1)
            displacement_efficiency: Effectiveness of displacement phase (0-1)
        """
        self.model = model
        self.short_circuit_fraction = clamp(short_circuit_fraction, 0.0, 1.0)
        self.displacement_efficiency = clamp(displacement_efficiency, 0.0, 1.0)

    def calculate_scavenging(
        self,
        m_fresh_delivered: float,  # Fresh charge delivered via transfer (kg)
        m_residual_initial: float,  # Initial residual mass in cylinder (kg)
        m_fresh_initial: float = 0.0,  # Initial fresh charge in cylinder (kg)
        displacement_ratio: float | None = None,  # m_delivered / m_cylinder_contents
    ) -> ScavengingState:
        """Calculate scavenging state based on model.

        Args:
            m_fresh_delivered: Mass of fresh charge delivered via transfer ports (kg)
            m_residual_initial: Initial residual burned gas mass in cylinder (kg)
            m_fresh_initial: Initial fresh charge mass in cylinder (kg)
            displacement_ratio: Delivered mass / total cylinder mass (optional)

        Returns:
            ScavengingState with composition and efficiency metrics
        """
        m_total_initial = m_fresh_initial + m_residual_initial

        if displacement_ratio is None:
            displacement_ratio = m_fresh_delivered / max(m_total_initial, 1e-9)

        if self.model == ScavengingModel.PERFECT_DISPLACEMENT:
            return self._perfect_displacement(
                m_fresh_delivered, m_residual_initial, m_fresh_initial, displacement_ratio
            )
        elif self.model == ScavengingModel.PERFECT_MIXING:
            return self._perfect_mixing(
                m_fresh_delivered, m_residual_initial, m_fresh_initial, displacement_ratio
            )
        else:  # COMBINED
            return self._combined_model(
                m_fresh_delivered, m_residual_initial, m_fresh_initial, displacement_ratio
            )

    def _perfect_displacement(
        self,
        m_fresh_delivered: float,
        m_residual_initial: float,
        m_fresh_initial: float,
        lambda_scav: float,  # Delivery ratio
    ) -> ScavengingState:
        """Perfect displacement scavenging model.

        Fresh charge completely displaces residuals without mixing.
        Ideal case with no short-circuiting losses.
        """
        # In perfect displacement, fresh charge pushes out residuals
        # until either fresh charge is depleted or cylinder is full of fresh charge
        m_residual_final = max(0.0, m_residual_initial - m_fresh_delivered)
        m_fresh_final = m_fresh_initial + m_fresh_delivered

        # Total mass (may exceed initial if we don't account for exhaust outflow)
        # Assume cylinder volume limits total mass via pressure equilibration
        m_total_final = m_fresh_final + m_residual_final

        # Scavenging efficiency = fraction of residuals displaced
        scav_eff = 1.0 - (m_residual_final / max(m_residual_initial, 1e-9))

        # Trapping efficiency = 1.0 (no short-circuiting in perfect displacement)
        trap_eff = 1.0

        # Short circuit loss = 0
        short_circuit = 0.0

        return ScavengingState(
            fresh_charge_mass=m_fresh_final,
            residual_mass=m_residual_final,
            total_mass=m_total_final,
            charge_purity=m_fresh_final / max(m_total_final, 1e-9),
            scavenging_efficiency=scav_eff,
            trapping_efficiency=trap_eff,
            short_circuit_loss=short_circuit,
            delivery_ratio=lambda_scav,
        )

    def _perfect_mixing(
        self,
        m_fresh_delivered: float,
        m_residual_initial: float,
        m_fresh_initial: float,
        lambda_scav: float,
    ) -> ScavengingState:
        """Perfect mixing scavenging model.

        Fresh charge mixes instantaneously and uniformly with cylinder contents.
        Residuals are expelled proportionally to their concentration.
        """
        m_total_initial = m_fresh_initial + m_residual_initial

        # With perfect mixing and expulsion, final purity follows:
        # Purity = 1 - exp(-delivery_ratio) for initially pure residuals
        # More generally: purity_final = purity_initial + (1 - purity_initial) * (1 - exp(-lambda_scav))
        # But we need to account for mass balance

        # Simplified approach: Assume some mass must leave to make room
        # If delivery ratio < 1: total mass stays ~constant, mix replaces some exhaust
        # If delivery ratio > 1: excess fresh charge also expelled

        # For perfect mixing, final purity = (fresh_initial + fresh_delivered) / (total + excess expelled)
        # But the actual expelled gas has the mixture composition

        # Use mixing chamber approach:
        # m_residual_final = m_residual_initial * exp(-lambda_scav)
        m_residual_final = m_residual_initial * math.exp(-lambda_scav)

        # Fresh charge remaining = all delivered minus what was expelled with mixture
        # Fraction of fresh in mixture at end = 1 - (residuals/total)
        m_total_final = m_total_initial  # Assume constant volume/pressure

        # Fresh mass balance: initial + delivered - expelled*fresh_fraction
        # This requires iterative solution; use approximation:
        m_fresh_final = m_fresh_initial + m_fresh_delivered * math.exp(-lambda_scav)

        # Short-circuit loss = delivered - retained
        m_retained = m_fresh_final - m_fresh_initial
        short_circuit = max(0.0, m_fresh_delivered - m_retained)

        scav_eff = 1.0 - (m_residual_final / max(m_residual_initial, 1e-9))
        trap_eff = m_retained / max(m_fresh_delivered, 1e-9)

        return ScavengingState(
            fresh_charge_mass=m_fresh_final,
            residual_mass=m_residual_final,
            total_mass=m_total_final,
            charge_purity=m_fresh_final / max(m_total_final, 1e-9),
            scavenging_efficiency=scav_eff,
            trapping_efficiency=trap_eff,
            short_circuit_loss=short_circuit,
            delivery_ratio=lambda_scav,
        )

    def _combined_model(
        self,
        m_fresh_delivered: float,
        m_residual_initial: float,
        m_fresh_initial: float,
        lambda_scav: float,
    ) -> ScavengingState:
        """Combined scavenging model with displacement and mixing phases.

        More realistic model accounting for:
        - Initial displacement phase (fresh charge pushes residuals)
        - Short-circuiting (some fresh charge escapes directly)
        - Mixing phase (at higher delivery ratios)
        """
        m_total_initial = m_fresh_initial + m_residual_initial

        # Short-circuit loss: some fresh charge goes directly to exhaust
        short_circuit = m_fresh_delivered * self.short_circuit_fraction
        m_fresh_effective = m_fresh_delivered - short_circuit

        # Displacement phase
        # Effective fresh charge displaces residuals
        m_residual_displaced = m_fresh_effective * self.displacement_efficiency
        m_residual_after_disp = max(0.0, m_residual_initial - m_residual_displaced)

        # Remaining effective fresh charge mixes with cylinder contents
        m_fresh_for_mixing = m_fresh_effective - m_residual_displaced

        if m_fresh_for_mixing > 0 and m_residual_after_disp > 0:
            # Mixing with remaining residuals
            mixing_ratio = m_fresh_for_mixing / max(m_total_initial, 1e-9)
            m_residual_final = m_residual_after_disp * math.exp(-mixing_ratio)
        else:
            m_residual_final = m_residual_after_disp

        # Fresh charge balance
        m_fresh_final = m_fresh_initial + m_fresh_effective - m_residual_displaced
        m_fresh_final = max(m_fresh_final, 0.0)

        m_total_final = m_fresh_final + m_residual_final

        scav_eff = 1.0 - (m_residual_final / max(m_residual_initial, 1e-9))
        trap_eff = (m_fresh_final - m_fresh_initial) / max(m_fresh_delivered, 1e-9)

        return ScavengingState(
            fresh_charge_mass=m_fresh_final,
            residual_mass=m_residual_final,
            total_mass=m_total_final,
            charge_purity=m_fresh_final / max(m_total_final, 1e-9),
            scavenging_efficiency=scav_eff,
            trapping_efficiency=clamp(trap_eff, 0.0, 1.0),
            short_circuit_loss=short_circuit,
            delivery_ratio=lambda_scav,
        )

    def calculate_charge_efficiency(
        self,
        m_fresh_in_cylinder: float,
        m_displacement_volume_fill: float,
        rho_atm: float,
    ) -> dict[str, float]:
        """Calculate charge-related efficiency metrics.

        Args:
            m_fresh_in_cylinder: Mass of fresh charge retained in cylinder (kg)
            m_displacement_volume_fill: Mass to fill displacement volume at atm (kg)
            rho_atm: Atmospheric density (kg/m³)

        Returns:
            Dictionary with efficiency metrics
        """
        # Volumetric efficiency: actual fresh charge / ideal fill
        vol_eff = m_fresh_in_cylinder / max(m_displacement_volume_fill, 1e-9)

        # Charge efficiency: ratio of fresh charge to total trapped mass
        # This would need total trapped mass as input

        return {
            "volumetric_efficiency": vol_eff,
            "relative_charge_efficiency": vol_eff,  # Same as VE for fresh charge
        }
