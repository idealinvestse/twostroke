"""Unit tests for friction model."""
import math
import unittest

from physics.friction import FrictionModel, FrictionBreakdown, BearingLoads, LubricationRegime
from physics.kinematics import KinematicState


class FrictionModelTests(unittest.TestCase):
    def test_initialization(self) -> None:
        """Test FrictionModel initialization with default parameters."""
        friction = FrictionModel()
        self.assertIsNotNone(friction)
        self.assertEqual(friction.piston_mass, 0.15)
        self.assertEqual(friction.bore, 0.040)
        self.assertEqual(friction.stroke, 0.040)

    def test_ring_friction_boundary_lubrication(self) -> None:
        """Test ring friction in boundary lubrication regime."""
        friction = FrictionModel()
        # Very low speed should result in boundary lubrication
        side_thrust = 10.0
        speed = 0.1
        force, regime = friction.calculate_ring_friction(side_thrust, speed, 293.0)
        self.assertGreater(force, 0.0)
        self.assertEqual(regime, LubricationRegime.BOUNDARY)
        self.assertLess(force, 100.0)  # Reasonable upper bound

    def test_ring_friction_hydrodynamic_lubrication(self) -> None:
        """Test ring friction in hydrodynamic lubrication regime."""
        friction = FrictionModel()
        side_thrust = 10.0
        # High speed should result in hydrodynamic lubrication
        speed = 5.0
        force, regime = friction.calculate_ring_friction(side_thrust, speed, 293.0)
        self.assertGreater(force, 0.0)
        self.assertEqual(regime, LubricationRegime.HYDRODYNAMIC)

    def test_ring_friction_mixed_lubrication(self) -> None:
        """Test ring friction in mixed lubrication regime."""
        friction = FrictionModel()
        side_thrust = 10.0
        # Medium speed should result in mixed lubrication
        speed = 1.0
        force, regime = friction.calculate_ring_friction(side_thrust, speed, 293.0)
        self.assertGreater(force, 0.0)
        self.assertEqual(regime, LubricationRegime.MIXED)

    def test_skirt_friction(self) -> None:
        """Test piston skirt friction calculation."""
        friction = FrictionModel()
        side_thrust = 10.0
        speed = 5.0
        force = friction.calculate_skirt_friction(side_thrust, speed)
        self.assertGreater(force, 0.0)
        # Skirt friction should be reasonable
        self.assertLess(force, 50.0)

    def test_bearing_friction(self) -> None:
        """Test bearing friction calculation."""
        friction = FrictionModel()
        bearing_load = 100.0  # N
        omega = 100.0  # rad/s
        torque = friction.calculate_bearing_friction(
            bearing_load, omega, friction.main_bearing_diam, friction.main_bearing_width, is_main=True
        )
        self.assertGreater(torque, 0.0)
        self.assertLess(torque, 5.0)

    def test_pumping_work(self) -> None:
        """Test pumping work calculation."""
        friction = FrictionModel()
        p_cr = 120000.0  # Pa (above atmospheric)
        dV_cr = -0.00001  # m³ (compression)
        omega = 100.0  # rad/s
        torque = friction.calculate_pumping_work(p_cr, dV_cr, omega)
        # Should be non-zero (could be positive or negative depending on pressure/volume change)
        self.assertIsInstance(torque, float)
        self.assertTrue(math.isfinite(torque))

    def test_simple_friction(self) -> None:
        """Test simplified friction calculation."""
        friction = FrictionModel()
        omega = 100.0
        torque = friction.get_simple_friction(omega)
        self.assertGreater(torque, 0.0)
        self.assertLess(torque, 10.0)

    def test_simple_friction_scales_with_speed(self) -> None:
        """Test that simple friction scales with speed."""
        friction = FrictionModel()
        low_omega = 10.0
        high_omega = 100.0
        low_torque = friction.get_simple_friction(low_omega)
        high_torque = friction.get_simple_friction(high_omega)
        self.assertGreater(high_torque, low_torque)

    def test_custom_parameters(self) -> None:
        """Test FrictionModel with custom parameters."""
        friction = FrictionModel(
            piston_mass=0.2,
            bore=0.045,
            stroke=0.045,
            con_rod_length=0.090
        )
        self.assertEqual(friction.piston_mass, 0.2)
        self.assertEqual(friction.bore, 0.045)
        self.assertEqual(friction.stroke, 0.045)
        self.assertEqual(friction.L, 0.090)

    def test_total_friction_breakdown(self) -> None:
        """Test complete friction breakdown calculation."""
        friction = FrictionModel()
        
        # Create mock kinematic state
        kinematic_state = KinematicState(
            x=0.02,
            v_cyl=0.0001,
            v_cr=0.0002,
            dx_dtheta=0.00002,
            d2x_dtheta2=0.0,
            beta=0.1,
            beta_dot=0.0,
            beta_ddot=0.0,
            piston_inertia_force=0.5,
            side_thrust_force=0.5,
            rod_axial_force=100.0,
            wrist_pin_load_x=50.0,
            wrist_pin_load_y=30.0,
            crank_pin_load_x=80.0,
            crank_pin_load_y=40.0,
            mechanical_advantage=1.0,
        )
        
        # Create mock bearing loads
        bearing_loads = BearingLoads(
            wrist_pin_load_x=50.0,
            wrist_pin_load_y=30.0,
            wrist_pin_load_mag=58.3,
            crank_pin_load_x=80.0,
            crank_pin_load_y=40.0,
            crank_pin_load_mag=89.4,
        )
        
        omega = 100.0
        p_cr = 120000.0
        dV_cr = -0.00001
        
        breakdown = friction.calculate_total_friction(
            omega, kinematic_state, bearing_loads, p_cr, dV_cr, 450.0
        )
        
        self.assertIsInstance(breakdown, FrictionBreakdown)
        self.assertGreater(breakdown.ring_friction_N, 0.0)
        self.assertGreater(breakdown.skirt_friction_N, 0.0)
        self.assertGreater(breakdown.main_bearing_friction_Nm, 0.0)
        self.assertGreater(breakdown.rod_bearing_friction_Nm, 0.0)
        self.assertGreater(breakdown.total_friction_torque_Nm, 0.0)
        
        # Total should equal sum of components
        expected_total = (
            breakdown.ring_friction_torque_Nm
            + breakdown.skirt_friction_torque_Nm
            + breakdown.main_bearing_friction_Nm
            + breakdown.rod_bearing_friction_Nm
            + breakdown.pumping_torque_Nm
            + breakdown.accessory_torque_Nm
            + breakdown.seal_friction_Nm
        )
        self.assertAlmostEqual(breakdown.total_friction_torque_Nm, expected_total, places=6)


if __name__ == "__main__":
    unittest.main()
