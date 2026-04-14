"""Unit tests for scavenging model."""
import math
import unittest

from physics.flows import ScavengingCalculator, ScavengingModel, ScavengingState


class ScavengingCalculatorTests(unittest.TestCase):
    def test_initialization_default(self) -> None:
        """Test ScavengingCalculator initialization with defaults."""
        calc = ScavengingCalculator()
        self.assertEqual(calc.model, ScavengingModel.COMBINED)
        self.assertEqual(calc.short_circuit_fraction, 0.15)
        self.assertEqual(calc.displacement_efficiency, 0.7)

    def test_initialization_custom(self) -> None:
        """Test ScavengingCalculator initialization with custom parameters."""
        calc = ScavengingCalculator(
            model=ScavengingModel.PERFECT_DISPLACEMENT,
            short_circuit_fraction=0.2,
            displacement_efficiency=0.8
        )
        self.assertEqual(calc.model, ScavengingModel.PERFECT_DISPLACEMENT)
        self.assertEqual(calc.short_circuit_fraction, 0.2)
        self.assertEqual(calc.displacement_efficiency, 0.8)

    def test_initialization_clamping(self) -> None:
        """Test that parameters are clamped to valid range."""
        calc = ScavengingCalculator(
            short_circuit_fraction=1.5,  # Should be clamped to 1.0
            displacement_efficiency=-0.5  # Should be clamped to 0.0
        )
        self.assertEqual(calc.short_circuit_fraction, 1.0)
        self.assertEqual(calc.displacement_efficiency, 0.0)

    def test_perfect_displacement_full_delivery(self) -> None:
        """Test perfect displacement with full delivery."""
        calc = ScavengingCalculator(model=ScavengingModel.PERFECT_DISPLACEMENT)
        m_fresh = 0.001  # 1g fresh charge
        m_residual = 0.0005  # 0.5g residuals
        
        state = calc.calculate_scavenging(m_fresh, m_residual)
        
        self.assertIsInstance(state, ScavengingState)
        # All residuals should be displaced
        self.assertLess(state.residual_mass, 0.0001)
        # All fresh charge should be retained
        self.assertAlmostEqual(state.fresh_charge_mass, m_fresh, places=6)
        # No short-circuit loss
        self.assertEqual(state.short_circuit_loss, 0.0)
        # Trapping efficiency should be 1.0
        self.assertAlmostEqual(state.trapping_efficiency, 1.0, places=6)
        # Scavenging efficiency should be high
        self.assertGreater(state.scavenging_efficiency, 0.9)

    def test_perfect_displacement_partial_delivery(self) -> None:
        """Test perfect displacement with partial delivery."""
        calc = ScavengingCalculator(model=ScavengingModel.PERFECT_DISPLACEMENT)
        m_fresh = 0.0002  # 0.2g fresh charge
        m_residual = 0.001  # 1g residuals
        
        state = calc.calculate_scavenging(m_fresh, m_residual)
        
        # Some residuals should remain
        self.assertGreater(state.residual_mass, 0.0005)
        # All fresh charge should be retained
        self.assertAlmostEqual(state.fresh_charge_mass, m_fresh, places=6)
        # No short-circuit loss
        self.assertEqual(state.short_circuit_loss, 0.0)
        # Scavenging efficiency should be proportional to delivery
        self.assertGreater(state.scavenging_efficiency, 0.0)
        self.assertLess(state.scavenging_efficiency, 1.0)

    def test_perfect_mixing_full_delivery(self) -> None:
        """Test perfect mixing with full delivery."""
        calc = ScavengingCalculator(model=ScavengingModel.PERFECT_MIXING)
        m_fresh = 0.001  # 1g fresh charge
        m_residual = 0.0005  # 0.5g residuals
        
        state = calc.calculate_scavenging(m_fresh, m_residual)
        
        self.assertIsInstance(state, ScavengingState)
        # Some residuals should remain (mixing is not perfect displacement)
        self.assertGreater(state.residual_mass, 0.0)
        # Some fresh charge should be lost (short-circuiting)
        self.assertGreater(state.short_circuit_loss, 0.0)
        # Trapping efficiency should be less than 1.0
        self.assertLess(state.trapping_efficiency, 1.0)

    def test_perfect_mixing_exponential_decay(self) -> None:
        """Test that perfect mixing follows exponential decay of residuals."""
        calc = ScavengingCalculator(model=ScavengingModel.PERFECT_MIXING)
        m_residual = 0.001  # 1g residuals
        
        # With delivery ratio = 1.0, residuals should decay by exp(-1)
        state1 = calc.calculate_scavenging(0.001, m_residual)
        expected_residual = m_residual * math.exp(-1.0)
        self.assertAlmostEqual(state1.residual_mass, expected_residual, places=4)
        
        # With delivery ratio = 2.0, residuals should decay by exp(-2)
        state2 = calc.calculate_scavenging(0.002, m_residual)
        expected_residual = m_residual * math.exp(-2.0)
        self.assertAlmostEqual(state2.residual_mass, expected_residual, places=4)

    def test_combined_model_short_circuit(self) -> None:
        """Test combined model accounts for short-circuiting."""
        calc = ScavengingCalculator(
            model=ScavengingModel.COMBINED,
            short_circuit_fraction=0.2  # 20% short-circuit
        )
        m_fresh = 0.001  # 1g fresh charge
        m_residual = 0.0005  # 0.5g residuals
        
        state = calc.calculate_scavenging(m_fresh, m_residual)
        
        # Should have short-circuit loss
        self.assertGreater(state.short_circuit_loss, 0.0)
        # Should be approximately 20% of delivered
        expected_short_circuit = m_fresh * 0.2
        self.assertAlmostEqual(state.short_circuit_loss, expected_short_circuit, places=4)

    def test_combined_model_displacement_phase(self) -> None:
        """Test combined model displacement phase."""
        calc = ScavengingCalculator(
            model=ScavengingModel.COMBINED,
            displacement_efficiency=0.8
        )
        m_fresh = 0.001  # 1g fresh charge
        m_residual = 0.0005  # 0.5g residuals
        
        state = calc.calculate_scavenging(m_fresh, m_residual)
        
        # Should have better scavenging than perfect mixing
        # (due to displacement phase)
        self.assertGreater(state.scavenging_efficiency, 0.5)

    def test_charge_purity_calculation(self) -> None:
        """Test charge purity calculation."""
        calc = ScavengingCalculator()
        m_fresh = 0.001
        m_residual = 0.0001
        
        state = calc.calculate_scavenging(m_fresh, m_residual)
        
        # Purity = fresh / (fresh + residual)
        expected_purity = state.fresh_charge_mass / state.total_mass
        self.assertAlmostEqual(state.charge_purity, expected_purity, places=6)
        self.assertGreater(state.charge_purity, 0.0)
        self.assertLessEqual(state.charge_purity, 1.0)

    def test_delivery_ratio_calculation(self) -> None:
        """Test delivery ratio calculation."""
        calc = ScavengingCalculator()
        m_fresh = 0.001
        m_residual = 0.0005
        
        state = calc.calculate_scavenging(m_fresh, m_residual)
        
        # Delivery ratio = delivered / initial cylinder mass (residuals only, fresh_initial=0)
        expected_ratio = m_fresh / max(m_residual, 1e-9)
        self.assertAlmostEqual(state.delivery_ratio, expected_ratio, places=6)

    def test_custom_delivery_ratio(self) -> None:
        """Test with custom delivery ratio."""
        calc = ScavengingCalculator()
        m_fresh = 0.001
        m_residual = 0.0005
        custom_ratio = 2.0
        
        state = calc.calculate_scavenging(m_fresh, m_residual, displacement_ratio=custom_ratio)
        
        self.assertAlmostEqual(state.delivery_ratio, custom_ratio, places=6)

    def test_zero_delivered(self) -> None:
        """Test with zero fresh charge delivered."""
        calc = ScavengingCalculator()
        m_residual = 0.0005
        
        state = calc.calculate_scavenging(0.0, m_residual)
        
        # Should have no fresh charge
        self.assertAlmostEqual(state.fresh_charge_mass, 0.0, places=6)
        # Should have all residuals
        self.assertAlmostEqual(state.residual_mass, m_residual, places=6)
        # Scavenging efficiency should be 0
        self.assertAlmostEqual(state.scavenging_efficiency, 0.0, places=6)

    def test_zero_residuals(self) -> None:
        """Test with zero initial residuals."""
        calc = ScavengingCalculator(model=ScavengingModel.PERFECT_DISPLACEMENT)
        m_fresh = 0.001
        
        state = calc.calculate_scavenging(m_fresh, 0.0)
        
        # Should have all fresh charge (no short-circuit in perfect displacement)
        self.assertAlmostEqual(state.fresh_charge_mass, m_fresh, places=6)
        # Should have no residuals
        self.assertAlmostEqual(state.residual_mass, 0.0, places=6)
        # Scavenging efficiency should be 1.0 (nothing to scavenge)
        self.assertAlmostEqual(state.scavenging_efficiency, 1.0, places=6)

    def test_calculate_charge_efficiency(self) -> None:
        """Test charge efficiency calculation."""
        calc = ScavengingCalculator()
        m_fresh = 0.001
        m_displacement_fill = 0.0012  # Mass to fill displacement at atm
        rho_atm = 1.225  # kg/m³
        
        metrics = calc.calculate_charge_efficiency(m_fresh, m_displacement_fill, rho_atm)
        
        self.assertIn("volumetric_efficiency", metrics)
        self.assertIn("relative_charge_efficiency", metrics)
        self.assertGreater(metrics["volumetric_efficiency"], 0.0)
        self.assertLessEqual(metrics["volumetric_efficiency"], 1.5)  # Can exceed 1.0 with supercharging

    def test_model_comparison(self) -> None:
        """Test that different models produce different results."""
        m_fresh = 0.001
        m_residual = 0.0005
        
        calc_displacement = ScavengingCalculator(model=ScavengingModel.PERFECT_DISPLACEMENT)
        calc_mixing = ScavengingCalculator(model=ScavengingModel.PERFECT_MIXING)
        calc_combined = ScavengingCalculator(model=ScavengingModel.COMBINED)
        
        state_displacement = calc_displacement.calculate_scavenging(m_fresh, m_residual)
        state_mixing = calc_mixing.calculate_scavenging(m_fresh, m_residual)
        state_combined = calc_combined.calculate_scavenging(m_fresh, m_residual)
        
        # Perfect displacement should have highest scavenging efficiency
        self.assertGreaterEqual(
            state_displacement.scavenging_efficiency,
            state_combined.scavenging_efficiency
        )
        # Perfect mixing should have some short-circuit loss
        self.assertGreater(state_mixing.short_circuit_loss, 0.0)
        # Perfect displacement should have no short-circuit loss
        self.assertEqual(state_displacement.short_circuit_loss, 0.0)


if __name__ == "__main__":
    unittest.main()
