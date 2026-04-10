"""Slider-crank kinematics for 2-stroke engine.

Calculates piston position, velocity, and cylinder volumes
based on crank angle.
"""

import math
from dataclasses import dataclass
from physics.constants import (
    HALF_STROKE_M,
    CON_ROD_M,
    PISTON_AREA_M2,
    CLEARANCE_VOLUME_M3,
    CRANKCASE_VOLUME_M3,
    EPSILON_VOLUME,
)


@dataclass
class KinematicState:
    """Piston kinematic state at a given crank angle."""
    # Basic kinematics
    x: float           # Piston position from TDC (m)
    v_cyl: float       # Cylinder volume (m³)
    v_cr: float        # Crankcase volume (m³)
    dx_dtheta: float   # Rate of change dx/dtheta (m/rad)

    # Advanced kinematics
    d2x_dtheta2: float     # Piston acceleration (m/rad²)
    beta: float            # Connecting rod angle (rad)
    beta_dot: float        # Connecting rod angular velocity (rad/rad)
    beta_ddot: float       # Connecting rod angular acceleration (rad/rad²)

    # Forces (per unit omega², multiply by omega² for actual force)
    piston_inertia_force: float      # F = m * a (N per kg at 1 rad/s)
    side_thrust_force: float        # Normal to cylinder wall (N per kg at 1 rad/s)
    rod_axial_force: float          # Along connecting rod (N per kg at 1 rad/s)

    # Bearing loads (per unit omega²)
    wrist_pin_load_x: float        # X-component at wrist pin (N per kg at 1 rad/s)
    wrist_pin_load_y: float        # Y-component at wrist pin (N per kg at 1 rad/s)
    crank_pin_load_x: float        # X-component at crank pin (N per kg at 1 rad/s)
    crank_pin_load_y: float        # Y-component at crank pin (N per kg at 1 rad/s)

    # Mechanical advantage
    mechanical_advantage: float    # Torque multiplier (dimensionless)


class SliderCrankKinematics:
    """Slider-crank mechanism for 2-stroke engine.

    Geometry based on crank radius R (half-stroke), connecting rod length L,
    and piston area A_p (derived from bore). Supports wrist pin offset for
    reduced side thrust.
    """

    def __init__(self, wrist_pin_offset: float = 0.0) -> None:
        """
        Args:
            wrist_pin_offset: Lateral offset of wrist pin from crank centerline (m)
                             Positive = offset toward thrust side (typically exhaust side)
        """
        self.R = HALF_STROKE_M      # Crank radius (m)
        self.L = CON_ROD_M          # Connecting rod length (m)
        self.A_p = PISTON_AREA_M2   # Piston area (m²)
        self.V_c = CLEARANCE_VOLUME_M3   # Clearance volume at TDC (m³)
        self.V_cr_base = CRANKCASE_VOLUME_M3  # Base crankcase volume (m³)
        self.e = wrist_pin_offset   # Wrist pin offset (m)
    
    def calculate(self, theta: float) -> KinematicState:
        """Calculate comprehensive kinematic state at given crank angle.

        Args:
            theta: Crank angle in radians (0 at TDC)

        Returns:
            KinematicState with full kinematics, forces, and bearing loads
        """
        s_theta = math.sin(theta)
        c_theta = math.cos(theta)

        # Connecting rod angle beta (with offset)
        beta_arg = (self.R * s_theta - self.e) / self.L
        beta_arg = max(-1.0, min(1.0, beta_arg))
        beta = math.asin(beta_arg)
        s_beta = math.sin(beta)
        c_beta = math.cos(beta)

        # Guard against division by zero
        c_beta = max(c_beta, 1e-6)

        # Piston position from TDC
        x = self.R + self.L - (self.R * c_theta + self.L * c_beta)

        # First derivative: dx/dtheta
        dx_dtheta = self.R * s_theta + self.R * c_theta * s_beta / c_beta

        # Connecting rod angular velocity: d(beta)/dtheta
        beta_dot = self.R * c_theta / (self.L * c_beta)

        # Second derivatives (for acceleration calculations)
        # d²x/dtheta²: Piston acceleration per unit omega²
        d2x_dtheta2 = (
            self.R * c_theta
            + self.R * c_theta * beta_dot * c_beta / c_beta
            + self.R * s_theta * s_beta / c_beta
            + self.R * c_theta * s_beta * beta_dot * s_beta / (c_beta ** 2)
        )
        # Simplified:
        d2x_dtheta2 = (
            self.R * c_theta
            + self.R * c_theta * beta_dot
            + self.R * s_theta * s_beta / c_beta * (1 + beta_dot * s_beta / c_beta)
        )

        # Better formulation using chain rule properly
        term1 = self.R * c_theta
        term2 = self.R * c_theta * beta_dot
        term3 = self.R * s_theta * s_beta / c_beta
        term4 = self.R * s_theta * s_beta * beta_dot * s_beta / (c_beta * c_beta)
        d2x_dtheta2 = term1 + term2 + term3 + term4

        # Connecting rod angular acceleration
        beta_ddot = -self.R * s_theta / (self.L * c_beta) + self.R * c_theta * s_beta * beta_dot / (self.L * c_beta * c_beta)

        # Mechanical advantage: d(x)/d(theta) for torque calculation
        mechanical_advantage = dx_dtheta

        # Forces per unit (piston mass * omega²)
        # Inertia force on piston (opposing acceleration)
        piston_inertia_force = -d2x_dtheta2  # F = -m * a, normalized

        # Rod axial force (along rod direction, compression positive)
        # From piston equilibrium: F_rod * cos(beta) = F_inertia
        rod_axial_force = piston_inertia_force / max(c_beta, 1e-6)

        # Side thrust (normal to cylinder wall)
        # F_thrust = F_rod * sin(beta) - accounts for offset effect
        side_thrust_force = rod_axial_force * s_beta

        # Bearing loads (per unit piston mass * omega²)
        # Wrist pin loads (at piston end of rod)
        wrist_pin_load_x = -rod_axial_force * s_beta  # Horizontal
        wrist_pin_load_y = -rod_axial_force * c_beta  # Vertical (along cylinder)

        # Crank pin loads (at crank end of rod)
        # Rod pushes on crank pin with equal and opposite force
        crank_pin_load_x = rod_axial_force * s_beta
        crank_pin_load_y = rod_axial_force * c_beta

        # Volumes
        v_cyl = max(self.V_c + self.A_p * x, EPSILON_VOLUME)
        v_cr = max(self.V_cr_base + self.A_p * (2 * self.R - x), EPSILON_VOLUME)

        return KinematicState(
            x=x,
            v_cyl=v_cyl,
            v_cr=v_cr,
            dx_dtheta=dx_dtheta,
            d2x_dtheta2=d2x_dtheta2,
            beta=beta,
            beta_dot=beta_dot,
            beta_ddot=beta_ddot,
            piston_inertia_force=piston_inertia_force,
            side_thrust_force=side_thrust_force,
            rod_axial_force=rod_axial_force,
            wrist_pin_load_x=wrist_pin_load_x,
            wrist_pin_load_y=wrist_pin_load_y,
            crank_pin_load_x=crank_pin_load_x,
            crank_pin_load_y=crank_pin_load_y,
            mechanical_advantage=mechanical_advantage,
        )
    
    def get_displacement(self) -> float:
        """Return engine displacement volume (m³)."""
        return self.A_p * 2 * self.R

    def get_compression_ratio(self) -> float:
        """Return geometric compression ratio."""
        V_d = self.get_displacement()
        return (V_d + self.V_c) / self.V_c

    def calculate_actual_forces(
        self,
        kinematic: KinematicState,
        piston_mass: float,
        omega: float,
        gas_pressure_force: float = 0.0,
    ) -> dict[str, float]:
        """Convert normalized kinematic forces to actual forces.

        Args:
            kinematic: KinematicState from calculate()
            piston_mass: Mass of piston assembly (kg)
            omega: Angular velocity (rad/s)
            gas_pressure_force: Additional gas pressure force on piston crown (N)

        Returns:
            Dictionary with actual force values in Newtons
        """
        omega_sq = omega * omega
        m_omega_sq = piston_mass * omega_sq

        # Total axial force includes gas pressure
        total_axial = kinematic.rod_axial_force * m_omega_sq + gas_pressure_force

        return {
            "piston_inertia_N": kinematic.piston_inertia_force * m_omega_sq,
            "side_thrust_N": kinematic.side_thrust_force * m_omega_sq,
            "rod_axial_N": total_axial,
            "rod_axial_inertia_only_N": kinematic.rod_axial_force * m_omega_sq,
            "wrist_pin_load_x_N": kinematic.wrist_pin_load_x * m_omega_sq,
            "wrist_pin_load_y_N": kinematic.wrist_pin_load_y * m_omega_sq + gas_pressure_force,
            "wrist_pin_load_mag_N": math.sqrt(
                (kinematic.wrist_pin_load_x * m_omega_sq) ** 2
                + (kinematic.wrist_pin_load_y * m_omega_sq + gas_pressure_force) ** 2
            ),
            "crank_pin_load_x_N": kinematic.crank_pin_load_x * m_omega_sq,
            "crank_pin_load_y_N": kinematic.crank_pin_load_y * m_omega_sq,
            "crank_pin_load_mag_N": math.sqrt(
                (kinematic.crank_pin_load_x * m_omega_sq) ** 2
                + (kinematic.crank_pin_load_y * m_omega_sq) ** 2
            ),
        }

    def analyze_side_thrust(
        self,
        kinematic: KinematicState,
        piston_mass: float,
        omega: float,
    ) -> dict[str, float]:
        """Analyze side thrust characteristics for friction calculations.

        Args:
            kinematic: KinematicState from calculate()
            piston_mass: Mass of piston assembly (kg)
            omega: Angular power velocity (rad/s)

        Returns:
            Dictionary with side thrust analysis
        """
        m_omega_sq = piston_mass * omega * omega
        thrust_force = kinematic.side_thrust_force * m_omega_sq

        # Determine thrust direction
        # Positive thrust = toward thrust side (exhaust side with positive offset)
        thrust_direction = "thrust_side" if thrust_force > 0 else "anti_thrust_side"

        # Magnitude for friction calculation
        thrust_magnitude = abs(thrust_force)

        return {
            "thrust_force_N": thrust_force,
            "thrust_magnitude_N": thrust_magnitude,
            "thrust_direction": thrust_direction,
            "thrust_per_unit_pressure_N_bar": thrust_magnitude / 1e5,  # Per bar of cylinder pressure
        }
