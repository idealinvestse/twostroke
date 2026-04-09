"""Physics package for 2-stroke engine simulation.

This package provides thermodynamic and gas-dynamic simulation
for a realistic 2-stroke engine model.
"""

from physics.engine_physics import EnginePhysics, EngineSnapshot
from physics.thermodynamics import Thermodynamics
from physics.constants import (
    MAX_CYLINDER_PRESSURE,
    MIN_PRESSURE,
    T_ATM,
    GAMMA,
)
from physics.utils import clamp01, angle_diff, rescale_components
from physics.combustion import CombustionModel

# Backwards compatibility - attach static methods to EnginePhysics
EnginePhysics.angle_diff = staticmethod(angle_diff)
EnginePhysics.rescale_components = staticmethod(rescale_components)

# get_kinematics returns tuple for backwards compatibility (old code expected 4 values)
def _get_kinematics_compat(self, theta):
    k = self._kinematics.calculate(theta)
    return (k.x, k.v_cyl, k.v_cr, k.dx_dtheta)
EnginePhysics.get_kinematics = _get_kinematics_compat

EnginePhysics.mixture_efficiency = lambda self, lambda_value=None: CombustionModel.calculate_mixture_efficiency(lambda_value if lambda_value is not None else getattr(self, 'lambda_value', 1.0))
EnginePhysics.ignition_efficiency = lambda self: CombustionModel.calculate_ignition_efficiency(self.ignition_angle_deg)

# intake_conditions returns tuple for backwards compatibility (old code expected 5 values)
def _intake_conditions_compat(self, p_cr):
    ic = self._flow_calc.calculate_intake_conditions(p_cr, self.throttle, self.idle_fuel_trim)
    return (ic.throttle_factor, ic.idle_circuit, ic.pressure, ic.area_main, ic.area_idle)
EnginePhysics.intake_conditions = _intake_conditions_compat

# m_cyl and m_cr property setters for test compatibility
def _set_m_cyl(self, value):
    # Distribute to air (backwards compat hack for tests)
    self.m_air_cyl = value - self.m_fuel_cyl - self.m_burned_cyl
EnginePhysics.m_cyl = property(lambda self: self.m_air_cyl + self.m_fuel_cyl + self.m_burned_cyl, _set_m_cyl)

def _set_m_cr(self, value):
    self.m_air_cr = value - self.m_fuel_cr - self.m_residual_cr
EnginePhysics.m_cr = property(lambda self: self.m_air_cr + self.m_fuel_cr + self.m_residual_cr, _set_m_cr)

# Backwards compatibility exports
flow_function = Thermodynamics.flow_function
mass_flow = Thermodynamics.mass_flow

__all__ = [
    "EnginePhysics",
    "EngineSnapshot",
    "flow_function",
    "mass_flow",
    "MAX_CYLINDER_PRESSURE",
    "MIN_PRESSURE",
    "T_ATM",
    "GAMMA",
    "clamp01",
]
