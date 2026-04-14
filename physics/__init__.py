"""Physics package for 2-stroke engine simulation.

This package provides thermodynamic and gas-dynamic simulation
for a realistic 2-stroke engine model.
"""

from physics.engine_physics import EnginePhysics, EngineSnapshot
from physics.cylinder import Cylinder, CylinderState
from physics.thermodynamics import Thermodynamics, EnhancedThermodynamics
from physics.kinematics import SliderCrankKinematics, KinematicState
from physics.flows import FlowCalculator, ScavengingCalculator, ScavengingModel, ScavengingState
from physics.scavenging import AdvancedScavengingModel, ScavengingZones, ScavengingMetrics
from physics.combustion import AdvancedCombustionModel
from physics.fuel_drops import FuelDrop, DropletEnsemble, calculate_sauter_mean_diameter
from physics.carburetor import CarburetorModel, CarburetorState, FuelJetConfig
from physics.gasdynamics import Quasi1DPipe, ExpansionChamberPipe, IntakeRunnerPipe, PipeSegment
from physics.friction import FrictionModel, FrictionBreakdown, LubricationRegime
from physics.constants import (
    MAX_CYLINDER_PRESSURE,
    MIN_PRESSURE,
    T_ATM,
    GAMMA,
    R_GAS,
    P_ATM,
    C_V,
    C_P,
    STOICH_AFR,
    FUEL_LHV,
    MIN_CRANKCASE_PRESSURE,
    MAX_CRANKCASE_PRESSURE,
    DISCHARGE_COEF_EXHAUST,
    DISCHARGE_COEF_TRANSFER,
    DISCHARGE_COEF_INTAKE_MAIN,
    DISCHARGE_COEF_INTAKE_IDLE,
    EXHAUST_PORT_OPEN_M,
    TRANSFER_PORT_OPEN_M,
    EXHAUST_PORT_WIDTH_M,
    TRANSFER_PORT_WIDTH_M,
    PISTON_AREA_M2,
    HALF_STROKE_M,
    CON_ROD_M,
    CLEARANCE_VOLUME_M3,
    CRANKCASE_VOLUME_M3,
    BORE_M,
    STROKE_M,
    DISPLACEMENT_M3,
    PIPE_RESONANCE_FREQ_HZ,
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

# Cylinder state properties for backward compatibility (primary cylinder)
def _T_cyl_compat(self):
    return self.cylinders[0].T_cyl if self.cylinders else T_ATM

def _set_T_cyl_compat(self, value):
    if self.cylinders:
        self.cylinders[0].T_cyl = value

def _m_air_cyl_compat(self):
    return self.cylinders[0].m_air if self.cylinders else 0.0

def _set_m_air_cyl_compat(self, value):
    if self.cylinders:
        self.cylinders[0].m_air = value

def _m_fuel_cyl_compat(self):
    return self.cylinders[0].m_fuel if self.cylinders else 0.0

def _set_m_fuel_cyl_compat(self, value):
    if self.cylinders:
        self.cylinders[0].m_fuel = value

def _m_burned_cyl_compat(self):
    return self.cylinders[0].m_burned if self.cylinders else 0.0

def _set_m_burned_cyl_compat(self, value):
    if self.cylinders:
        self.cylinders[0].m_burned = value

def _burn_fraction_compat(self):
    return self.cylinders[0].burn_fraction if self.cylinders else 0.0

def _combustion_active_compat(self):
    return self.cylinders[0].combustion_active if self.cylinders else False

def _spark_active_compat(self):
    return self.cylinders[0].spark_active if self.cylinders else False

def _lambda_value_compat(self):
    return self.cylinders[0].lambda_value if self.cylinders else 1.0

def _p_cyl_compat(self):
    return self.cylinders[0].p_cyl if self.cylinders else P_ATM

# Attach properties to EnginePhysics class using property() function
EnginePhysics.T_cyl = property(_T_cyl_compat, _set_T_cyl_compat)
EnginePhysics.m_air_cyl = property(_m_air_cyl_compat, _set_m_air_cyl_compat)
EnginePhysics.m_fuel_cyl = property(_m_fuel_cyl_compat, _set_m_fuel_cyl_compat)
EnginePhysics.m_burned_cyl = property(_m_burned_cyl_compat, _set_m_burned_cyl_compat)
EnginePhysics.burn_fraction = property(_burn_fraction_compat)
EnginePhysics.combustion_active = property(_combustion_active_compat)
EnginePhysics.spark_active = property(_spark_active_compat)
EnginePhysics.lambda_value = property(_lambda_value_compat)
EnginePhysics.p_cyl = property(_p_cyl_compat)

# Method for backward compatibility
EnginePhysics.throttle_flow_factor = lambda self: self._throttle_flow_factor()
EnginePhysics.idle_circuit_strength = lambda self: self._idle_circuit_strength()

# Fuel film property
def _fuel_film_cyl_compat(self):
    return self.cylinders[0].fuel_film if self.cylinders else 0.0

def _set_fuel_film_cyl_compat(self, value):
    if self.cylinders:
        self.cylinders[0].fuel_film = value

EnginePhysics.fuel_film_cyl = property(_fuel_film_cyl_compat, _set_fuel_film_cyl_compat)

# Pipe resonance frequency
EnginePhysics.pipe_resonance_freq = PIPE_RESONANCE_FREQ_HZ

# Backwards compatibility exports
flow_function = Thermodynamics.flow_function
mass_flow = Thermodynamics.mass_flow

__all__ = [
    "EnginePhysics",
    "EngineSnapshot",
    "Cylinder",
    "CylinderState",
    "Thermodynamics",
    "EnhancedThermodynamics",
    "SliderCrankKinematics",
    "KinematicState",
    "FlowCalculator",
    "ScavengingCalculator",
    "ScavengingModel",
    "ScavengingState",
    "AdvancedScavengingModel",
    "ScavengingZones",
    "ScavengingMetrics",
    "AdvancedCombustionModel",
    "FuelDrop",
    "DropletEnsemble",
    "calculate_sauter_mean_diameter",
    "CarburetorModel",
    "CarburetorState",
    "FuelJetConfig",
    "Quasi1DPipe",
    "ExpansionChamberPipe",
    "IntakeRunnerPipe",
    "PipeSegment",
    "FrictionModel",
    "FrictionBreakdown",
    "LubricationRegime",
    "flow_function",
    "mass_flow",
    "MAX_CYLINDER_PRESSURE",
    "MIN_PRESSURE",
    "T_ATM",
    "GAMMA",
    "R_GAS",
    "P_ATM",
    "C_V",
    "C_P",
    "STOICH_AFR",
    "FUEL_LHV",
    "MIN_CRANKCASE_PRESSURE",
    "MAX_CRANKCASE_PRESSURE",
    "DISCHARGE_COEF_EXHAUST",
    "DISCHARGE_COEF_TRANSFER",
    "DISCHARGE_COEF_INTAKE_MAIN",
    "DISCHARGE_COEF_INTAKE_IDLE",
    "EXHAUST_PORT_OPEN_M",
    "TRANSFER_PORT_OPEN_M",
    "EXHAUST_PORT_WIDTH_M",
    "TRANSFER_PORT_WIDTH_M",
    "PISTON_AREA_M2",
    "HALF_STROKE_M",
    "CON_ROD_M",
    "CLEARANCE_VOLUME_M3",
    "CRANKCASE_VOLUME_M3",
    "BORE_M",
    "STROKE_M",
    "DISPLACEMENT_M3",
    "clamp01",
]
