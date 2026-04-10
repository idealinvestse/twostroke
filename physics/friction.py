"""Comprehensive friction and mechanical losses model for 2-stroke engine.

Implements detailed friction calculations for:
- Piston rings (Stribeck curve: boundary, mixed, hydrodynamic lubrication)
- Piston skirt (Coulomb + viscous friction)
- Crank bearings (journal bearing hydrodynamics)
- Reed valve flow losses
- Pumping work from crankcase
"""

import math
from dataclasses import dataclass
from enum import Enum

from physics.constants import (
    P_ATM,
    MU_OIL_BOUNDARY,
    MU_OIL_HYDRODYNAMIC,
    PISTON_RING_TENSION,
    PISTON_SKIRT_AREA,
    CRANK_BEARING_DIAMETER,
    CRANK_BEARING_WIDTH,
    OIL_FILM_THICKNESS_HYDRO,
)


class LubricationRegime(Enum):
    """Lubrication regime for Stribeck curve friction."""
    BOUNDARY = "boundary"        # Metal-to-metal contact
    MIXED = "mixed"              # Partial lubrication
    HYDRODYNAMIC = "hydrodynamic"  # Full fluid film


@dataclass
class FrictionBreakdown:
    """Detailed friction breakdown by component."""
    # Ring friction
    ring_friction_N: float
    ring_friction_torque_Nm: float

    # Skirt friction
    skirt_friction_N: float
    skirt_friction_torque_Nm: float

    # Bearing friction
    main_bearing_friction_Nm: float
    rod_bearing_friction_Nm: float

    # Other losses
    pumping_torque_Nm: float
    accessory_torque_Nm: float
    seal_friction_Nm: float

    # Total
    total_friction_torque_Nm: float

    # For analysis
    dominant_source: str
    lubrication_regime: LubricationRegime


@dataclass
class BearingLoads:
    """Bearing load vectors from kinematics."""
    wrist_pin_load_x: float  # N
    wrist_pin_load_y: float  # N
    wrist_pin_load_mag: float  # N
    crank_pin_load_x: float  # N
    crank_pin_load_y: float  # N
    crank_pin_load_mag: float  # N


class FrictionModel:
    """Comprehensive friction model for 2-stroke engine.

    Uses physics-based calculations for each friction source with
    temperature and speed-dependent effects.
    """

    def __init__(
        self,
        piston_mass: float = 0.15,  # kg, typical for 50cc piston
        bore: float = 0.040,  # m
        stroke: float = 0.040,  # m
        con_rod_length: float = 0.081,  # m
    ) -> None:
        """
        Args:
            piston_mass: Mass of piston assembly (kg)
            bore: Cylinder bore (m)
            stroke: Piston stroke (m)
            con_rod_length: Connecting rod center-to-center length (m)
        """
        self.piston_mass = piston_mass
        self.bore = bore
        self.stroke = stroke
        self.R = stroke / 2  # Crank radius
        self.L = con_rod_length

        # Ring pack properties
        self.ring_tension = PISTON_RING_TENSION  # N per ring
        self.num_rings = 2  # Typical for 2-stroke
        self.ring_width = 0.001  # m (1mm)

        # Skirt properties
        self.skirt_area = PISTON_SKIRT_AREA  # m²
        self.skirt_length = 0.025  # m
        self.skirt_clearance = 0.00004  # m (40 micron)

        # Bearing properties
        self.main_bearing_diam = CRANK_BEARING_DIAMETER
        self.main_bearing_width = CRANK_BEARING_WIDTH
        self.rod_bearing_diam = 0.018  # m (18mm typical)
        self.rod_bearing_width = 0.012  # m (12mm typical)

        # Oil properties (SAE 10W-40 typical)
        self.oil_viscosity_boundary = MU_OIL_BOUNDARY
        self.oil_viscosity_hydro = MU_OIL_HYDRODYNAMIC

        # Friction coefficients
        self.mu_boundary = 0.12  # Boundary friction coefficient
        self.mu_mixed_min = 0.05
        self.mu_mixed_max = 0.10
        self.mu_hydrodynamic = 0.002  # Viscous friction

        # Constants for pumping/accessories
        self.base_pumping_loss = 0.3  # Nm base
        self.pumping_rpm_coeff = 0.001  # Nm per RPM
        self.seal_friction = 0.08  # Nm constant
        self.accessory_load = 0.15  # Nm for ignition, water pump, etc.

    def calculate_ring_friction(
        self,
        side_thrust_force: float,  # N
        piston_speed: float,  # m/s
        wall_temp: float = 450.0,  # K
    ) -> tuple[float, LubricationRegime]:
        """Calculate piston ring friction force.

        Uses Stribeck curve with speed-dependent lubrication regime.

        Args:
            side_thrust: Normal force from side thrust (N)
            piston_speed: Instantaneous piston velocity (m/s)
            wall_temp: Cylinder wall temperature (K)

        Returns:
            (friction_force_N, lubrication_regime)
        """
        # Total normal force on rings = ring tension + gas pressure behind rings
        # Simplified: ring tension dominates at low load
        normal_force = self.num_rings * self.ring_tension + side_thrust_force * 0.3

        # Determine lubrication regime based on speed
        # Stribeck parameter ~ viscosity * speed / load
        mean_piston_speed = abs(piston_speed)

        if mean_piston_speed < 0.5:  # m/s
            regime = LubricationRegime.BOUNDARY
            mu = self.mu_boundary
        elif mean_piston_speed < 2.5:
            regime = LubricationRegime.MIXED
            # Interpolate in mixed regime
            ratio = (mean_piston_speed - 0.5) / 2.0
            mu = self.mu_mixed_max - ratio * (self.mu_mixed_max - self.mu_mixed_min)
        else:
            regime = LubricationRegime.HYDRODYNAMIC
            # Viscous friction in hydrodynamic regime
            # F_viscous = viscosity * area * speed / clearance
            film_thickness = OIL_FILM_THICKNESS_HYDRO
            viscous_force = (
                self.oil_viscosity_hydro
                * self.num_rings * math.pi * self.bore * self.ring_width
                * mean_piston_speed
                / film_thickness
            )
            mu = viscous_force / max(normal_force, 1e-6)
            mu = min(mu, self.mu_hydrodynamic * 2)  # Cap mu

        friction_force = mu * normal_force
        return friction_force, regime

    def calculate_skirt_friction(
        self,
        side_thrust_force: float,  # N
        piston_speed: float,  # m/s
    ) -> float:
        """Calculate piston skirt friction.

        Combines Coulomb (boundary) and viscous components.

        Args:
            side_thrust: Normal force from side thrust (N)
            piston_speed: Instantaneous piston velocity (m/s)

        Returns:
            Friction force in Newtons
        """
        mean_speed = abs(piston_speed)

        # Coulomb component (constant with speed)
        # Friction coefficient typically 0.05-0.08 for skirt
        mu_skirt = 0.06
        coulomb_force = mu_skirt * abs(side_thrust_force)

        # Viscous component (proportional to speed)
        # F_viscous = viscosity * area * speed / clearance
        viscous_force = (
            self.oil_viscosity_hydro
            * self.skirt_area
            * mean_speed
            / self.skirt_clearance
        )

        # Total friction (combination of both mechanisms)
        # At low speed: Coulomb dominates
        # At high speed: Viscous dominates
        if mean_speed < 1.0:
            # Mostly Coulomb
            total_friction = coulomb_force + 0.2 * viscous_force
        else:
            # Mixed with increasing viscous component
            viscous_ratio = min(1.0, (mean_speed - 1.0) / 4.0)
            total_friction = coulomb_force * (1 - 0.5 * viscous_ratio) + viscous_force * viscous_ratio

        return total_friction

    def calculate_bearing_friction(
        self,
        bearing_load: float,  # N
        omega: float,  # rad/s
        bearing_diam: float,
        bearing_width: float,
        is_main: bool = True,
    ) -> float:
        """Calculate journal bearing friction torque.

        Uses Petroff's equation for hydrodynamic bearings with
        boundary correction at low speed.

        Args:
            bearing_load: Radial load on bearing (N)
            omega: Angular velocity (rad/s)
            bearing_diam: Bearing diameter (m)
            bearing_width: Bearing width (m)
            is_main: True for main bearing, False for rod bearing

        Returns:
            Friction torque in Nm
        """
        rpm = omega * 30 / math.pi

        if rpm < 100:  # noqa: F841
            # Boundary lubrication at very low speed
            # Simple Coulomb friction
            mu_boundary = 0.08
            friction_force = mu_boundary * bearing_load
            radius = bearing_diam / 2
            return friction_force * radius

        # Hydrodynamic regime - Petroff's equation
        # T = 2 * pi * mu * N * L * R³ / c
        # where c is radial clearance
        radial_clearance = 0.00002  # 20 microns typical

        # Simplified: use empirical relationship
        # Torque proportional to viscosity, speed, and diameter
        oil_viscosity = self.oil_viscosity_hydro  # Pa·s

        # Petroff torque (viscous drag)
        petroff_torque = (
            2
            * math.pi
            * oil_viscosity
            * (rpm / 60)
            * bearing_width
            * (bearing_diam / 2) ** 3
            / radial_clearance
        )

        # Load-dependent component (simplified Sommerfeld)
        # At moderate load, friction coefficient ~ 0.002-0.005
        mu_hydro = 0.003
        load_torque = mu_hydro * bearing_load * bearing_diam / 2

        # Combine (viscous dominates at high speed, load at low)
        if rpm > 2000:
            total_torque = 0.3 * load_torque + 0.7 * petroff_torque
        else:
            ratio = rpm / 2000
            total_torque = (1 - ratio) * load_torque + ratio * petroff_torque

        return total_torque

    def calculate_pumping_work(
        self,
        p_cr: float,  # Pa
        dV_cr: float,  # m³ (negative for compression)
        omega: float,  # rad/s
    ) -> float:
        """Calculate crankcase pumping work/torque.

        Args:
            p_cr: Crankcase pressure (Pa)
            dV_cr: Crankcase volume change (m³)
            omega: Angular velocity (rad/s)

        Returns:
            Pumping torque in Nm (positive = work against engine)
        """
        # Work = pressure * volume change
        # Torque = Work / angle = Work / (omega * dt)
        # But we're given dV, not dV/dt
        # Need to think about this differently

        # For a full cycle, pumping work = integral(p_cr * dV_cr)
        # This is the area of the crankcase PV diagram

        # Instantaneous power = p_cr * dV_cr/dt
        # Torque = Power / omega

        # But since we're given dV, assume this is per unit crank rotation
        # dV/dtheta = dV, and dV/dt = dV * omega
        power = p_cr * dV_cr * omega  # W (if dV is dV/dtheta)
        torque = power / max(omega, 1e-6)

        # Additional pumping loss from throttling
        # This is already partially captured in the pressure
        throttling_loss = abs(dV_cr) * abs(p_cr - P_ATM) * 0.1

        return abs(torque) + throttling_loss / max(omega, 1e-6)

    def calculate_total_friction(
        self,
        omega: float,  # rad/s
        kinematic_state,  # From kinematics.calculate()
        bearing_loads: BearingLoads,
        p_cr: float,
        dV_cr: float,
        wall_temp: float = 450.0,
    ) -> FrictionBreakdown:
        """Calculate complete friction breakdown.

        Args:
            omega: Angular velocity (rad/s)
            kinematic_state: KinematicState from kinematics module
            bearing_loads: Bearing load vectors
            p_cr: Crankcase pressure (Pa)
            dV_cr: Crankcase volume change (m³ per rad)
            wall_temp: Cylinder wall temperature (K)

        Returns:
            FrictionBreakdown with all components
        """
        # Piston velocity from kinematics
        # v = dx/dt = dx/dtheta * dtheta/dt = dx_dtheta * omega
        piston_speed = kinematic_state.dx_dtheta * omega

        # Calculate actual side thrust force
        # kinematic_state gives normalized force, need to scale
        m_omega_sq = self.piston_mass * omega * omega
        side_thrust = kinematic_state.side_thrust_force * m_omega_sq

        # Ring friction
        ring_friction, regime = self.calculate_ring_friction(
            side_thrust, piston_speed, wall_temp
        )
        ring_torque = ring_friction * abs(kinematic_state.dx_dtheta)

        # Skirt friction
        skirt_friction = self.calculate_skirt_friction(side_thrust, piston_speed)
        skirt_torque = skirt_friction * abs(kinematic_state.dx_dtheta)

        # Bearing friction
        main_bearing_torque = self.calculate_bearing_friction(
            bearing_loads.wrist_pin_load_mag,  # Main bearing sees crank pin load
            omega,
            self.main_bearing_diam,
            self.main_bearing_width,
            is_main=True,
        )

        rod_bearing_torque = self.calculate_bearing_friction(
            bearing_loads.wrist_pin_load_mag,
            omega + kinematic_state.beta_dot * omega,  # Relative speed
            self.rod_bearing_diam,
            self.rod_bearing_width,
            is_main=False,
        )

        # Pumping work
        pumping_torque = self.calculate_pumping_work(p_cr, dV_cr, omega)

        # Other losses
        accessory_torque = self.accessory_load * (1 + omega / 300)
        seal_torque = self.seal_friction

        # Total friction torque
        total_torque = (
            ring_torque
            + skirt_torque
            + main_bearing_torque
            + rod_bearing_torque
            + pumping_torque
            + accessory_torque
            + seal_torque
        )

        # Determine dominant source
        torques = {
            "ring": ring_torque,
            "skirt": skirt_torque,
            "main_bearing": main_bearing_torque,
            "rod_bearing": rod_bearing_torque,
            "pumping": pumping_torque,
            "accessory": accessory_torque,
        }
        dominant = max(torques, key=torques.get)

        return FrictionBreakdown(
            ring_friction_N=ring_friction,
            ring_friction_torque_Nm=ring_torque,
            skirt_friction_N=skirt_friction,
            skirt_friction_torque_Nm=skirt_torque,
            main_bearing_friction_Nm=main_bearing_torque,
            rod_bearing_friction_Nm=rod_bearing_torque,
            pumping_torque_Nm=pumping_torque,
            accessory_torque_Nm=accessory_torque,
            seal_friction_Nm=seal_torque,
            total_friction_torque_Nm=total_torque,
            dominant_source=dominant,
            lubrication_regime=regime,
        )

    def get_simple_friction(self, omega: float) -> float:
        """Simple friction model for backward compatibility.

        Returns total friction torque using simplified formula.

        Args:
            omega: Angular velocity (rad/s)

        Returns:
            Friction torque in Nm
        """
        # Original model: friction + pumping_drag
        friction_torque = 0.65  # Base friction
        pumping_drag = omega * 0.008 + 0.000008 * omega * omega
        return friction_torque + pumping_drag
