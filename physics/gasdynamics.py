"""Quasi-1D gasdynamics for engine pipes (intake and exhaust).

Implements finite-volume method for compressible flow in pipes,
capturing pressure wave propagation and resonance effects.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from physics.constants import (
    R_GAS,
    GAMMA,
    P_ATM,
    T_ATM,
    EPSILON_MASS,
)
from physics.utils import clamp


@dataclass
class PipeSegment:
    """State of a single pipe segment/cell in finite-volume discretization.
    
    Represents compressible gas state with conservation variables.
    """
    # Geometry
    dx: float           # Segment length (m)
    area: float         # Cross-sectional area (m²) - can vary for conical sections
    
    # Conservative variables
    mass: float         # Mass in segment (kg)
    momentum: float     # Mass * velocity (kg·m/s)
    energy: float       # Total energy (J)
    
    # Derived primitive variables (reconstructed from conservative)
    density: float = field(init=False)
    velocity: float = field(init=False)
    pressure: float = field(init=False)
    temperature: float = field(init=False)
    
    def __post_init__(self):
        self._update_primitive_vars()
    
    def _update_primitive_vars(self) -> None:
        """Reconstruct primitive variables from conservative variables."""
        volume = self.dx * self.area
        self.density = self.mass / max(volume, 1e-12)
        
        # Clamp velocity to prevent numerical instability
        max_velocity = 500.0  # m/s, reasonable limit for engine pipes
        if self.mass > EPSILON_MASS:
            self.velocity = self.momentum / self.mass
            self.velocity = clamp(self.velocity, -max_velocity, max_velocity)
        else:
            self.velocity = 0.0
        
        # Internal energy per unit mass
        if self.mass > EPSILON_MASS:
            kinetic = 0.5 * self.velocity**2
            e_internal = self.energy / self.mass - kinetic
            e_internal = max(e_internal, 1e4)  # Minimum internal energy (~100 kJ/kg)
        else:
            e_internal = 1e5  # Default ~100 kJ/kg
        
        # Ideal gas: e = cv * T, p = rho * R * T
        cv = R_GAS / (GAMMA - 1.0)
        self.temperature = e_internal / cv
        self.pressure = self.density * R_GAS * self.temperature
        
        # Clamp to physical limits for engine pipes
        # Max pressure ~3 bar (typical peak in expansion chamber)
        self.pressure = clamp(self.pressure, 1e4, 500000.0)
        self.temperature = clamp(self.temperature, 200.0, 1500.0)
    
    def set_primitive(self, density: float, velocity: float, pressure: float) -> None:
        """Set state via primitive variables, update conservative variables."""
        volume = self.dx * self.area
        self.mass = density * volume
        self.momentum = self.mass * velocity
        
        cv = R_GAS / (GAMMA - 1.0)
        temperature = pressure / (density * R_GAS)
        e_internal = cv * temperature
        kinetic = 0.5 * velocity**2
        self.energy = self.mass * (e_internal + kinetic)
        
        self._update_primitive_vars()


@dataclass
class PipeBoundary:
    """Boundary condition for pipe end."""
    # Type: 'cylinder', 'atmosphere', 'junction', 'closed'
    boundary_type: str = 'atmosphere'
    
    # For cylinder connection
    cylinder_pressure: float = P_ATM
    cylinder_temperature: float = T_ATM
    port_area: float = 0.0  # m², current open area
    
    # For atmosphere
    ambient_pressure: float = P_ATM
    ambient_temperature: float = T_ATM
    
    # Computed flux at boundary (set by solver)
    mass_flux: float = 0.0      # kg/s, positive = into pipe
    momentum_flux: float = 0.0  # kg·m/s²
    energy_flux: float = 0.0    # J/s


class Quasi1DPipe:
    """Quasi-1D finite-volume pipe model for compressible flow.
    
    Discretizes pipe into segments and solves 1D Euler equations
    with source terms for area variation. Captures pressure waves,
    shock formation (simplified), and resonance effects.
    
    Suitable for expansion chambers and intake runners in 2-stroke engines.
    """
    
    def __init__(
        self,
        length: float,
        diameter: float,
        num_segments: int = 7,
        initial_pressure: float = P_ATM,
        initial_temperature: float = T_ATM,
        is_conical: bool = False,
        end_diameter: Optional[float] = None,
    ):
        """Initialize pipe with uniform properties.
        
        Args:
            length: Total pipe length (m)
            diameter: Starting diameter (m), or constant if not conical
            num_segments: Number of finite-volume cells
            initial_pressure: Initial pressure (Pa)
            initial_temperature: Initial temperature (K)
            is_conical: If True, diameter varies linearly from start to end
            end_diameter: Diameter at pipe end (m), only used if is_conical
        """
        self.length = length
        self.num_segments = num_segments
        self.dx = length / num_segments
        self.is_conical = is_conical
        
        # Create segments with varying area if conical
        self.segments: List[PipeSegment] = []
        
        for i in range(num_segments):
            if is_conical and end_diameter is not None:
                # Linear area variation
                t = i / (num_segments - 1) if num_segments > 1 else 0
                d = diameter * (1 - t) + end_diameter * t
                area = math.pi * (d / 2) ** 2
            else:
                area = math.pi * (diameter / 2) ** 2
            
            seg = PipeSegment(
                dx=self.dx,
                area=area,
                mass=0.0,
                momentum=0.0,
                energy=0.0,
            )
            
            # Set initial conditions
            density = initial_pressure / (R_GAS * initial_temperature)
            seg.set_primitive(density, 0.0, initial_pressure)
            
            self.segments.append(seg)
        
        # Boundaries
        self.left_boundary = PipeBoundary('atmosphere')
        self.right_boundary = PipeBoundary('atmosphere')
        
        # Time stepping control
        self.cfl_target = 0.5  # Conservative CFL for stability
        self.max_dt_suggest = 5e-5  # Suggested max dt for stability (50 microseconds)
    
    def set_left_boundary_cylinder(self, pressure: float, temperature: float, port_area: float) -> None:
        """Connect left end to cylinder port."""
        self.left_boundary.boundary_type = 'cylinder'
        self.left_boundary.cylinder_pressure = pressure
        self.left_boundary.cylinder_temperature = temperature
        self.left_boundary.port_area = port_area
    
    def set_right_boundary_atmosphere(self, pressure: float = P_ATM, temperature: float = T_ATM) -> None:
        """Connect right end to atmosphere."""
        self.right_boundary.boundary_type = 'atmosphere'
        self.right_boundary.ambient_pressure = pressure
        self.right_boundary.ambient_temperature = temperature
    
    def set_left_boundary_atmosphere(self, pressure: float = P_ATM, temperature: float = T_ATM) -> None:
        """Connect left end to atmosphere."""
        self.left_boundary.boundary_type = 'atmosphere'
        self.left_boundary.ambient_pressure = pressure
        self.left_boundary.ambient_temperature = temperature
    
    def _calculate_flux(self, left: PipeSegment, right: PipeSegment) -> Tuple[float, float, float]:
        """Calculate flux between two segments using Rusanov (local Lax-Friedrichs) scheme.
        
        Returns:
            (mass_flux, momentum_flux, energy_flux) - positive = from left to right
        """
        # Average state for wave speed estimation
        rho_avg = 0.5 * (left.density + right.density)
        u_avg = 0.5 * (left.velocity + right.velocity)
        p_avg = 0.5 * (left.pressure + right.pressure)
        
        # Speed of sound
        a_avg = math.sqrt(GAMMA * p_avg / max(rho_avg, 1e-6))
        
        # Maximum wave speed
        max_wave_speed = max(abs(u_avg) + a_avg, 1e-6)
        
        # Physical fluxes (F = [rho*u, rho*u² + p, u*(E+p)])
        # Left flux
        E_left = left.energy / max(left.mass, EPSILON_MASS)  # Specific total energy
        F_mass_left = left.density * left.velocity
        F_mom_left = left.density * left.velocity**2 + left.pressure
        F_energy_left = left.velocity * (left.density * E_left + left.pressure)
        
        # Right flux
        E_right = right.energy / max(right.mass, EPSILON_MASS)
        F_mass_right = right.density * right.velocity
        F_mom_right = right.density * right.velocity**2 + right.pressure
        F_energy_right = right.velocity * (right.density * E_right + right.pressure)
        
        # Rusanov flux: average minus dissipation
        mass_flux = 0.5 * (F_mass_left + F_mass_right) - 0.5 * max_wave_speed * (right.density - left.density)
        momentum_flux = 0.5 * (F_mom_left + F_mom_right) - 0.5 * max_wave_speed * (right.density * right.velocity - left.density * left.velocity)
        energy_flux = 0.5 * (F_energy_left + F_energy_right) - 0.5 * max_wave_speed * (right.density * E_right - left.density * E_left)
        
        # Scale by face area (use average of adjacent segments)
        face_area = 0.5 * (left.area + right.area)
        mass_flux *= face_area
        momentum_flux *= face_area
        energy_flux *= face_area
        
        return mass_flux, momentum_flux, energy_flux
    
    def _apply_boundary_flux(self, boundary: PipeBoundary, segment: PipeSegment, is_left: bool) -> Tuple[float, float, float]:
        """Calculate flux at pipe boundary."""
        if boundary.boundary_type == 'atmosphere':
            return self._atmosphere_boundary_flux(boundary, segment, is_left)
        elif boundary.boundary_type == 'cylinder':
            return self._cylinder_boundary_flux(boundary, segment, is_left)
        else:
            # Closed boundary
            return 0.0, 0.0, 0.0
    
    def _atmosphere_boundary_flux(self, boundary: PipeBoundary, segment: PipeSegment, is_left: bool) -> Tuple[float, float, float]:
        """Atmosphere boundary using characteristic boundary conditions."""
        p_atm = boundary.ambient_pressure
        T_atm = boundary.ambient_temperature
        rho_atm = p_atm / (R_GAS * T_atm)
        
        # Create ghost state outside pipe
        # Extrapolate with pressure relaxation toward atmosphere
        p_ghost = 0.5 * (segment.pressure + p_atm)
        rho_ghost = rho_atm * (p_ghost / p_atm)  # Isentropic relation approximation
        u_ghost = -segment.velocity  # Reflection
        
        ghost = PipeSegment(
            dx=segment.dx,
            area=segment.area,
            mass=0.0,
            momentum=0.0,
            energy=0.0,
        )
        ghost.set_primitive(rho_ghost, u_ghost, p_ghost)
        
        if is_left:
            return self._calculate_flux(ghost, segment)
        else:
            return self._calculate_flux(segment, ghost)
    
    def _cylinder_boundary_flux(self, boundary: PipeBoundary, segment: PipeSegment, is_left: bool) -> Tuple[float, float, float]:
        """Cylinder port boundary with variable open area."""
        p_cyl = boundary.cylinder_pressure
        T_cyl = boundary.cylinder_temperature
        A_port = boundary.port_area
        
        # Port is closed
        if A_port < 1e-9:
            return 0.0, 0.0, 0.0
        
        # Determine flow direction based on pressure difference
        dp = p_cyl - segment.pressure
        
        # Use orifice flow model scaled by port area
        # This couples the 1D pipe to the lumped cylinder model
        rho_cyl = p_cyl / (R_GAS * T_cyl)
        
        # Simplified compressible orifice flow
        if dp > 0:  # Flow from cylinder to pipe
            rho_up = rho_cyl
            u_up = 0.0  # Stagnation in cylinder
            p_up = p_cyl
        else:  # Flow from pipe to cylinder
            rho_up = segment.density
            u_up = segment.velocity
            p_up = segment.pressure
        
        # Isentropic flow function
        gamma = GAMMA
        pr_crit = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))
        
        p_down = min(p_cyl, segment.pressure) if dp > 0 else max(p_cyl, segment.pressure)
        pr = p_down / max(p_up, 1e-6)
        pr = clamp(pr, pr_crit, 1.0)
        
        # Mass flow rate through port
        term = (pr ** (2.0 / gamma)) - (pr ** ((gamma + 1.0) / gamma))
        psi = math.sqrt(abs(2.0 * gamma / (gamma - 1.0) * max(0.0, term)))
        
        # Velocity magnitude
        c_up = math.sqrt(gamma * p_up / max(rho_up, 1e-6))
        u_magnitude = c_up * psi
        
        # Mass flux
        mass_flux = rho_up * u_magnitude * A_port
        
        if dp < 0:  # Outflow from pipe
            mass_flux = -mass_flux
            u_boundary = segment.velocity
            p_boundary = segment.pressure
            rho_boundary = segment.density
        else:  # Inflow to pipe
            u_boundary = 0.0  # Stagnation
            p_boundary = p_cyl
            rho_boundary = rho_cyl
        
        # Momentum and energy flux
        # Include pressure work term at boundary
        momentum_flux = mass_flux * u_boundary + p_boundary * A_port
        
        # Total enthalpy
        cv = R_GAS / (gamma - 1.0)
        cp = cv + R_GAS
        h_total = cp * T_cyl if dp > 0 else (cv * segment.temperature + segment.pressure / segment.density + 0.5 * segment.velocity**2)
        energy_flux = mass_flux * h_total
        
        # Scale fluxes by direction
        if is_left:
            # Positive flux = into pipe
            return mass_flux, momentum_flux, energy_flux
        else:
            # For right boundary, positive flux is out of pipe
            return -mass_flux, -momentum_flux, -energy_flux
    
    def step(self, dt: float) -> float:
        """Advance simulation by one timestep.
        
        Args:
            dt: Timestep (s)
            
        Returns:
            Actual timestep used (may be limited by CFL)
        """
        # Calculate CFL-based timestep limit
        max_wave_speed = 0.0
        for seg in self.segments:
            a = math.sqrt(GAMMA * seg.pressure / max(seg.density, 1e-6))
            max_wave_speed = max(max_wave_speed, abs(seg.velocity) + a)
        
        if max_wave_speed > 1e-6:
            dt_cfl = self.cfl_target * self.dx / max_wave_speed
            dt = min(dt, dt_cfl, self.max_dt_suggest)
        
        # Compute fluxes at all interfaces
        fluxes: List[Tuple[float, float, float]] = []
        
        # Left boundary flux
        fluxes.append(self._apply_boundary_flux(self.left_boundary, self.segments[0], True))
        
        # Internal fluxes
        for i in range(len(self.segments) - 1):
            fluxes.append(self._calculate_flux(self.segments[i], self.segments[i + 1]))
        
        # Right boundary flux
        fluxes.append(self._apply_boundary_flux(self.right_boundary, self.segments[-1], False))
        
        # Update conserved variables
        for i, seg in enumerate(self.segments):
            # Flux in from left, out to right
            mass_in, mom_in, energy_in = fluxes[i]
            mass_out, mom_out, energy_out = fluxes[i + 1]
            
            # Volume
            volume = seg.dx * seg.area
            
            # Update
            seg.mass += (mass_in - mass_out) * dt
            seg.momentum += (mom_in - mom_out) * dt
            seg.energy += (energy_in - energy_out) * dt
            
            # Ensure positive mass
            seg.mass = max(seg.mass, 1e-9)
            
            # Reconstruct primitives
            seg._update_primitive_vars()
        
        return dt
    
    def get_pressure_at_position(self, x: float) -> float:
        """Get pressure at specific position in pipe (0 = left, length = right)."""
        if not self.segments:
            return P_ATM
        
        # Find segment
        x_clamped = clamp(x, 0.0, self.length)
        idx = int(x_clamped / self.dx)
        idx = min(idx, len(self.segments) - 1)
        
        return self.segments[idx].pressure
    
    def get_average_pressure(self) -> float:
        """Get mass-flow-weighted average pressure."""
        if not self.segments:
            return P_ATM
        
        total_mass = sum(seg.mass for seg in self.segments)
        if total_mass < 1e-9:
            return P_ATM
        
        weighted_pressure = sum(seg.mass * seg.pressure for seg in self.segments)
        return weighted_pressure / total_mass
    
    def get_port_pressure(self, is_left: bool) -> float:
        """Get pressure at pipe end (for coupling to cylinder/intake)."""
        if not self.segments:
            return P_ATM
        
        if is_left:
            return self.segments[0].pressure
        else:
            return self.segments[-1].pressure
    
    def get_port_temperature(self, is_left: bool) -> float:
        """Get temperature at pipe end."""
        if not self.segments:
            return T_ATM
        
        if is_left:
            return self.segments[0].temperature
        else:
            return self.segments[-1].temperature
    
    def get_mass_flow_at_port(self, is_left: bool) -> float:
        """Get mass flow rate at pipe end (positive = into pipe)."""
        if is_left:
            return self.left_boundary.mass_flux
        else:
            return -self.right_boundary.mass_flux  # Flip sign for consistency


class ExpansionChamberPipe(Quasi1DPipe):
    """Specialized pipe for 2-stroke expansion chamber.
    
    Includes divergent (diffuser), parallel belly, and convergent (baffle) sections.
    Provides optimal pressure wave tuning for specific RPM ranges.
    """
    
    def __init__(
        self,
        header_length: float,       # m, straight section from exhaust port
        header_diameter: float,      # m
        diffuser_length: float,     # m
        diffuser_start_dia: float,  # m
        diffuser_end_dia: float,    # m
        belly_length: float,        # m
        belly_diameter: float,       # m (constant)
        baffle_length: float,        # m
        baffle_start_dia: float,    # m
        baffle_end_dia: float,      # m (stinger)
        num_segments: int = 10,
    ):
        """Create expansion chamber with varying diameter sections."""
        total_length = (header_length + diffuser_length + belly_length + baffle_length)
        
        # Initialize with uniform properties, then customize
        super().__init__(
            length=total_length,
            diameter=header_diameter,
            num_segments=num_segments,
            is_conical=False,
        )
        
        # Redefine segments with varying areas
        self.segments = []
        
        segments_per_section = max(2, num_segments // 4)
        
        # Helper to create segments
        def create_segment_section(length: float, d_start: float, d_end: float, n_segs: int):
            segs = []
            dx = length / n_segs
            for i in range(n_segs):
                t = i / (n_segs - 1) if n_segs > 1 else 0
                d = d_start * (1 - t) + d_end * t
                area = math.pi * (d / 2) ** 2
                
                seg = PipeSegment(dx=dx, area=area, mass=0.0, momentum=0.0, energy=0.0)
                rho = P_ATM / (R_GAS * T_ATM)
                seg.set_primitive(rho, 0.0, P_ATM)
                segs.append(seg)
            return segs
        
        # Create sections
        self.segments.extend(create_segment_section(header_length, header_diameter, header_diameter, segments_per_section))
        self.segments.extend(create_segment_section(diffuser_length, diffuser_start_dia, diffuser_end_dia, segments_per_section))
        self.segments.extend(create_segment_section(belly_length, belly_diameter, belly_diameter, segments_per_section))
        self.segments.extend(create_segment_section(baffle_length, baffle_start_dia, baffle_end_dia, segments_per_section))
        
        self.num_segments = len(self.segments)
        self.dx = total_length / self.num_segments
        
        # Store section info for reference
        self.header_length = header_length
        self.diffuser_length = diffuser_length
        self.belly_length = belly_length
        self.baffle_length = baffle_length
    
    def get_reflection_location(self, wave_position: float) -> float:
        """Get where a pressure wave reflects based on area changes.
        
        Args:
            wave_position: Normalized position 0-1 along pipe
            
        Returns:
            Position of nearest area discontinuity (reflection point)
        """
        # Section boundaries
        boundaries = [
            0,
            self.header_length / self.length,
            (self.header_length + self.diffuser_length) / self.length,
            (self.header_length + self.diffuser_length + self.belly_length) / self.length,
            1.0,
        ]
        
        # Find nearest boundary
        closest = min(boundaries, key=lambda b: abs(b - wave_position))
        return closest


class IntakeRunnerPipe(Quasi1DPipe):
    """Specialized pipe for intake system (reed valve to crankcase).
    
    Models pressure wave tuning effects on intake charging efficiency,
    including Helmholtz resonance and inertial ram effects.
    """
    
    def __init__(
        self,
        length: float,           # m, runner length
        diameter: float,         # m, runner diameter
        num_segments: int = 5,
        has_helmholtz_box: bool = False,
        box_volume: float = 0.0,  # m³, optional damping box
    ):
        """Create intake runner pipe."""
        super().__init__(length, diameter, num_segments)
        
        self.has_helmholtz_box = has_helmholtz_box
        self.box_volume = box_volume
        
        # Helmholtz frequency
        if has_helmholtz_box and box_volume > 0:
            runner_area = math.pi * (diameter / 2) ** 2
            self.helmholtz_freq = self._calculate_helmholtz_freq(runner_area, length, box_volume)
        else:
            self.helmholtz_freq = 0.0
    
    @staticmethod
    def _calculate_helmholtz_freq(area: float, length: float, volume: float) -> float:
        """Calculate Helmholtz resonance frequency.
        
        f = (c / 2π) * √(A / (L * V))
        """
        c = math.sqrt(GAMMA * R_GAS * T_ATM)  # Speed of sound
        return (c / (2 * math.pi)) * math.sqrt(area / (length * volume))
    
    def get_pressure_at_reed_valve(self) -> float:
        """Get pressure at intake/reed valve end (left boundary)."""
        return self.get_port_pressure(is_left=True)
    
    def set_crankcase_connection(self, crankcase_pressure: float, crankcase_temp: float, port_area: float) -> None:
        """Connect right end to crankcase."""
        self.set_right_boundary_cylinder(crankcase_pressure, crankcase_temp, port_area)
    
    def set_right_boundary_cylinder(self, pressure: float, temperature: float, port_area: float) -> None:
        """Connect right end to crankcase (cylinder-like boundary)."""
        self.right_boundary.boundary_type = 'cylinder'
        self.right_boundary.cylinder_pressure = pressure
        self.right_boundary.cylinder_temperature = temperature
        self.right_boundary.port_area = port_area
