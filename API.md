# Physics API Reference

Complete API reference for the physics simulation module.

## Table of Contents

- [Core Classes](#core-classes)
- [Physics Constants](#physics-constants)
- [Kinematics](#kinematics)
- [Thermodynamics](#thermodynamics)
- [Flows](#flows)
- [Combustion](#combustion)
- [Friction](#friction)
- [Cylinder](#cylinder)
- [Utility Functions](#utility-functions)

## Core Classes

### EnginePhysics

Main controller class for the engine simulation.

```python
from physics import EnginePhysics

engine = EnginePhysics()
```

#### Constructor

```python
EnginePhysics()
```

Initializes engine with default 50cc moped parameters:
- Bore: 40mm, Stroke: 39.5mm
- Rod length: 95mm
- Compression ratio: 7.5:1

#### Key Properties

| Property | Type | Description |
|----------|------|-------------|
| `theta` | float | Crank angle in radians |
| `omega` | float | Angular velocity in rad/s |
| `throttle` | float | Throttle position 0.0-1.0 |
| `ignition_angle_deg` | float | Spark timing in degrees BTDC |
| `fuel_ratio` | float | Fuel/air ratio by mass |
| `idle_fuel_trim` | float | Idle mixture adjustment |
| `compression_ratio` | float | Compression ratio |
| `pipe_resonance_freq` | float | Exhaust pipe resonance Hz |

#### Main Methods

```python
step(dt: float, starter_motor: bool = False) -> EngineSnapshot
```

Advances simulation by `dt` seconds. Returns immutable state snapshot.

```python
snapshot() -> EngineSnapshot
```

Returns current state without advancing simulation.

```python
reset() -> None
```

Resets engine to initial state.

### EngineSnapshot

Immutable dataclass representing engine state at a point in time.

```python
@dataclass(frozen=True)
class EngineSnapshot:
    theta: float              # Crank angle (rad)
    x: float                  # Piston position from TDC (m)
    v_cyl: float             # Cylinder volume (m³)
    v_cr: float              # Crankcase volume (m³)
    p_cyl: float             # Cylinder pressure (Pa)
    p_cr: float              # Crankcase pressure (Pa)
    T_cyl: float             # Cylinder temperature (K)
    T_cr: float              # Crankcase temperature (K)
    m_air_cyl: float         # Cylinder air mass (kg)
    m_fuel_cyl: float        # Cylinder fuel mass (kg)
    m_burned_cyl: float      # Cylinder burned mass (kg)
    m_air_cr: float          # Crankcase air mass (kg)
    m_fuel_cr: float         # Crankcase fuel mass (kg)
    dm_exh: float            # Exhaust mass flow (kg/s)
    dm_tr: float             # Transfer mass flow (kg/s)
    dm_air_in: float         # Intake air flow (kg/s)
    dm_fuel_in: float        # Intake fuel flow (kg/s)
    combustion_active: bool  # Combustion in progress
    spark_active: bool       # Spark firing
    burn_fraction: float     # Fraction of fuel burned
    reed_opening: float      # Reed valve opening 0.0-1.0
    omega: float             # Angular velocity (rad/s)
    cycle_torque: float      # Instantaneous torque (Nm)
    pipe_amplitude: float    # Exhaust pulse amplitude
```

## Physics Constants

All constants defined in `physics/constants.py`:

### Thermodynamic Constants

```python
T_ATM = 293.15              # Atmospheric temperature (K)
P_ATM = 101325.0            # Atmospheric pressure (Pa)
R_GAS = 287.0               # Specific gas constant for air (J/kg·K)
GAMMA = 1.4                 # Heat capacity ratio (air)
C_V = 718.0                 # Specific heat at constant volume (J/kg·K)
C_P = 1005.0                # Specific heat at constant pressure (J/kg·K)
```

### Fuel Constants

```python
STOICH_AFR = 14.7           # Stoichiometric air/fuel ratio
FUEL_LHV = 44.0e6           # Lower heating value (J/kg)
```

### Engine Geometry (Default 50cc)

```python
BORE_M = 0.040              # Cylinder bore (m)
STROKE_M = 0.0395           # Piston stroke (m)
CON_ROD_M = 0.095           # Connecting rod length (m)
DISPLACEMENT_M3 = 0.0000496  # Engine displacement (m³)
PISTON_AREA_M2 = 0.001256   # Piston crown area (m²)
HALF_STROKE_M = 0.01975     # Crank radius (m)
CLEARANCE_VOLUME_M3 = 7.4e-6  # Volume at TDC (m³)
CRANKCASE_VOLUME_M3 = 0.00015  # Crankcase volume (m³)
```

### Port Geometry

```python
EXHAUST_PORT_OPEN_M = 0.024    # Port open height (m)
TRANSFER_PORT_OPEN_M = 0.034   # Port open height (m)
EXHAUST_PORT_WIDTH_M = 0.038   # Port width (m)
TRANSFER_PORT_WIDTH_M = 0.032  # Port width (m)
```

### Discharge Coefficients

```python
DISCHARGE_COEF_EXHAUST = 0.7           # Exhaust port
DISCHARGE_COEF_TRANSFER = 0.6          # Transfer ports
DISCHARGE_COEF_INTAKE_MAIN = 0.65      # Main intake
DISCHARGE_COEF_INTAKE_IDLE = 0.45      # Idle circuit
```

### Limits

```python
MAX_CYLINDER_PRESSURE = 5.0e6          # 5 MPa safety limit
MIN_PRESSURE = 1e-6                    # Minimum for guards
MIN_CRANKCASE_PRESSURE = 100.0         # Minimum crankcase pressure (Pa)
MAX_CRANKCASE_PRESSURE = 300000.0      # Maximum crankcase pressure (Pa)
```

## Kinematics

### SliderCrankKinematics

```python
from physics import SliderCrankKinematics

kinematics = SliderCrankKinematics(
    R=0.01975,      # Crank radius (m)
    L=0.095,        # Rod length (m)
)
```

#### Methods

```python
calculate(theta: float) -> KinematicState
```

Computes kinematic state from crank angle.

Returns `KinematicState`:

```python
@dataclass
class KinematicState:
    x: float           # Piston position from TDC (m)
    v: float           # Piston velocity (m/s)
    v_cyl: float       # Cylinder volume (m³)
    v_cr: float        # Crankcase volume (m³)
    dx_dtheta: float   # Position derivative wrt angle
```

### Equations

**Piston Position:**
```
x = R(1 - cos θ) + L(1 - √(1 - (R/L sin θ)²))
```

**Piston Velocity:**
```
v = ωR(sin θ + (R/2L)sin 2θ / √(1 - (R/L sin θ)²))
```

**Cylinder Volume:**
```
V_cyl = V_clearance + A_piston × x
```

## Thermodynamics

### Thermodynamics Class

```python
from physics import Thermodynamics
```

Static methods for thermodynamic calculations:

#### Flow Function

```python
@staticmethod
def flow_function(pressure_ratio: float, gamma: float = GAMMA) -> float
```

Calculates compressible flow function for isentropic flow:

```
Φ = √[γ × (2/(γ+1))^((γ+1)/(γ-1))]  for choked flow (P2/P1 < critical)
Φ = √[(2γ/(γ-1)) × ((P2/P1)^(2/γ) - (P2/P1)^((γ+1)/γ))]  for subsonic
```

Critical pressure ratio: `(2/(γ+1))^(γ/(γ-1)) ≈ 0.528`

#### Mass Flow

```python
@staticmethod
def mass_flow(
    C_d: float,           # Discharge coefficient
    area: float,          # Flow area (m²)
    P_upstream: float,    # Upstream pressure (Pa)
    T_upstream: float,    # Upstream temperature (K)
    P_downstream: float,  # Downstream pressure (Pa)
    gamma: float = GAMMA
) -> float
```

Returns mass flow rate (kg/s):

```
dm/dt = C_d × A × P_upstream / √(R × T_upstream) × Φ(P2/P1)
```

#### Temperature Change

```python
@staticmethod
def temperature_change(
    mass: float,          # Chamber mass (kg)
    cv: float,           # Heat capacity (J/kg·K)
    heat_added: float,   # Heat transfer (J)
    work_done: float,    # Work transfer (J)
    enthalpy_in: float,  # Enthalpy entering (J)
    enthalpy_out: float  # Enthalpy leaving (J)
) -> float
```

Returns temperature change (K):

```
dT = (heat_added - work_done + enthalpy_in - enthalpy_out) / (mass × cv)
```

## Flows

### FlowCalculator

```python
from physics import FlowCalculator

calc = FlowCalculator(engine_physics_instance)
```

#### Intake Flows

```python
def calculate_intake_flows(
    p_cr: float,      # Crankcase pressure (Pa)
    T_cr: float,      # Crankcase temperature (K)
    throttle: float,  # Throttle 0.0-1.0
    fuel_ratio: float,# Fuel/air ratio
    idle_trim: float # Idle adjustment
) -> IntakeFlows
```

Returns:

```python
@dataclass
class IntakeFlows:
    dm_air: float     # Air mass flow (kg/s)
    dm_fuel: float    # Fuel mass flow (kg/s)
    throttle_factor: float  # Effective throttle opening
```

#### Reed Valve Dynamics

```python
def calculate_reed_dynamics(
    reed_opening: float,  # Current opening 0.0-1.0
    p_cr: float,         # Crankcase pressure (Pa)
    reed_stiffness: float,# Stiffness (N/m)
    dt: float            # Timestep (s)
) -> float
```

Returns new reed opening using spring-mass-damper model.

#### Port Areas

```python
def get_port_areas(x: float) -> PortAreas
```

Returns flow areas based on piston position:

```python
@dataclass
class PortAreas:
    A_exh: float    # Exhaust port area (m²)
    A_tr: float     # Transfer port area (m²)
    A_in: float     # Intake area (m²)
```

### ScavengingCalculator

```python
from physics import ScavengingCalculator

calc = ScavengingCalculator(model=ScavengingModel.BASIC)
```

#### Models

```python
class ScavengingModel(Enum):
    PERFECT = "perfect"      # No short-circuiting
    COMPLETE = "complete"    # Perfect mixing
    SHORT_CIRCUIT = "short"  # Some fresh charge lost
    BASIC = "basic"          # Simplified model
```

#### Calculation

```python
def calculate(
    p_cyl: float,      # Cylinder pressure (Pa)
    p_cr: float,       # Crankcase pressure (Pa)
    m_cyl: float,      # Cylinder mass (kg)
    m_cr: float,       # Crankcase mass (kg)
    dm_tr: float,      # Transfer flow (kg/s)
    dt: float          # Timestep (s)
) -> ScavengingState
```

Returns:

```python
@dataclass
class ScavengingState:
    trapping_efficiency: float   # 0.0-1.0
    scavenge_ratio: float        # Delivery ratio
    mixing_loss: float          # Energy loss from mixing
```

## Combustion

### CombustionModel

```python
from physics import CombustionModel
```

#### Mixture Efficiency

```python
@staticmethod
def calculate_mixture_efficiency(lambda_value: float) -> float
```

Calculates combustion efficiency based on air/fuel ratio:

```
λ = actual_AFR / stoichiometric_AFR
peak at λ = 1.0 (stoichiometric)
drops for lean (λ > 1.2) and rich (λ < 0.8)
```

#### Ignition Efficiency

```python
@staticmethod
def calculate_ignition_efficiency(ignition_angle_deg: float) -> float
```

Returns efficiency based on spark timing:

```
Optimal: 15-20° BTDC
Too early: knock, incomplete burn
Too late: lost power, hot exhaust
```

#### Turbulence Factor

```python
@staticmethod
def turbulence_factor(omega: float) -> float
```

Scales burn rate with engine speed:

```
turbulence = 0.5 + 0.01 × |ω|  (higher RPM = faster burn)
```

### Cylinder Combustion Methods

```python
# Start combustion
cylinder.start_combustion(
    fuel_mass: float,     # Available fuel (kg)
    air_mass: float,      # Available air (kg)
    omega: float,        # Engine speed (rad/s)
    compression_ratio: float,
    burn_duration_factor: float = 1.0,
    combustion_efficiency: float = 1.0
)

# Update during combustion
cylinder.update_combustion(
    dt: float,
    m_fuel_cyl: float,
    omega: float,
    T_cyl: float
) -> CombustionResult
```

## Friction

### FrictionModel

```python
from physics import FrictionModel, FrictionBreakdown

model = FrictionModel(
    A_p=0.001256,         # Piston area (m²)
    mu_oil=0.1,          # Oil viscosity
    bore=0.040,          # Cylinder bore (m)
    stroke=0.0395,       # Piston stroke (m)
    mech_efficiency=0.85 # Base mechanical efficiency
)
```

#### Calculate Friction

```python
def calculate(
    p_cyl: float,        # Cylinder pressure (Pa)
    omega: float,        # Angular velocity (rad/s)
    v_piston: float,     # Piston velocity (m/s)
    ignition_angle: float # Spark timing (deg)
) -> FrictionBreakdown
```

Returns:

```python
@dataclass
class FrictionBreakdown:
    pumping_torque: float      # Gas exchange losses (Nm)
    friction_torque: float     # Mechanical friction (Nm)
    total_loss_torque: float  # Combined losses (Nm)
    regime: LubricationRegime # Current lubrication state
```

#### Lubrication Regimes

```python
class LubricationRegime(Enum):
    BOUNDARY = "boundary"      # High friction, metal contact
    MIXED = "mixed"           # Partial oil film
    HYDRODYNAMIC = "hydrodynamic"  # Full oil film, low friction
```

## Cylinder

### Cylinder Class

```python
from physics import Cylinder

cyl = Cylinder(
    thermodynamics=thermo_instance,
    V_clearance=7.4e-6,   # Clearance volume (m³)
    A_piston=0.001256      # Piston area (m²)
)
```

#### State Management

```python
# Get current state
state = cyl.get_state()  # Returns CylinderState

# Update from flows
cyl.update_from_flows(
    dm_air_in: float,     # Air entering (kg)
    dm_fuel_in: float,    # Fuel entering (kg)
    dm_burned_in: float,  # Burned gases entering (kg)
    dm_air_out: float,    # Air leaving (kg)
    dm_fuel_out: float,  # Fuel leaving (kg)
    dm_burned_out: float # Burned gases leaving (kg)
)
```

#### Transfer Flow with Fuel Film

```python
def add_transfer_with_fuel_film(
    dm_transfer: float,    # Total transfer mass (kg)
    x_fuel_cr: float,     # Fuel fraction in crankcase
    T_cyl: float         # Cylinder temperature (K)
) -> tuple[float, float, float]
```

Returns `(dm_air, dm_fuel, dm_burned)` accounting for fuel film capture.

#### Fuel Film Evaporation

```python
def evaporate_cylinder_fuel_film(
    T_cyl: float,        # Cylinder temperature (K)
    dt: float            # Timestep (s)
) -> float
```

Returns evaporated fuel mass returned to cylinder.

### CylinderState

```python
@dataclass
class CylinderState:
    p_cyl: float          # Pressure (Pa)
    T_cyl: float          # Temperature (K)
    m_air: float          # Air mass (kg)
    m_fuel: float         # Fuel mass (kg)
    m_burned: float       # Burned mass (kg)
    fuel_film: float      # Wet fuel film (kg)
    burn_fraction: float  # Burn progress 0.0-1.0
    combustion_active: bool
    spark_active: bool
    lambda_value: float   # Air/fuel ratio
```

## Utility Functions

### Clamp Functions

```python
from physics import clamp01

clamp01(value: float) -> float
```

Clamps value to range [0.0, 1.0].

### Angle Utilities

```python
from physics import angle_diff

angle_diff(angle1: float, angle2: float) -> float
```

Returns smallest signed difference between two angles (radians), handling wrap-around.

```python
# Example: angle_diff(0.1, 2π-0.1) ≈ 0.2  (wraps correctly)
```

### Rescale Components

```python
from physics import rescale_components

rescale_components(
    current: tuple[float, float, float],  # (air, fuel, burned)
    target_total: float                   # Desired total mass
) -> tuple[float, float, float]
```

Scales component masses proportionally to achieve target total.

## Backward Compatibility

The physics module maintains backward compatibility with monolithic `physics.py` patterns:

```python
# Old style (still works)
from physics import EnginePhysics
engine = EnginePhysics()
x, v_cyl, v_cr, dx_dtheta = engine.get_kinematics(theta)

# Static methods attached for compatibility
EnginePhysics.angle_diff = staticmethod(angle_diff)
EnginePhysics.rescale_components = staticmethod(rescale_components)

# Property compatibility for cylinder state
engine.p_cyl  # Returns primary cylinder pressure
engine.T_cyl  # Returns primary cylinder temperature
engine.m_air_cyl  # Returns primary cylinder air mass
# ... etc
```

## Usage Examples

### Basic Simulation Loop

```python
from physics import EnginePhysics, PHYSICS_DT

engine = EnginePhysics()
dt = 1.0 / 600.0  # 600 Hz

for _ in range(6000):  # 10 seconds
    state = engine.step(dt)
    print(f"RPM: {state.omega * 60 / (2 * 3.14159):.0f}, "
          f"P_cyl: {state.p_cyl / 1000:.1f} kPa")
```

### Custom Engine Configuration

```python
engine = EnginePhysics()

# Tuning parameters
engine.compression_ratio = 9.5
engine.rod_length = 0.090
engine.pipe_resonance_freq = 160.0
engine.reed_stiffness = 1000.0

# Control inputs
engine.throttle = 0.8
engine.ignition_angle_deg = 18
engine.fuel_ratio = 0.045
```

### Accessing Per-Cylinder Data

```python
state = engine.step(dt)

# Primary cylinder (index 0)
cyl = engine.cylinders[0]
print(f"Burn fraction: {cyl.burn_fraction:.2%}")
print(f"Lambda: {cyl.lambda_value:.2f}")
print(f"Fuel film: {cyl.fuel_film * 1000:.3f} g")
```

### Validation

```python
# Validate state after each step
engine.validate_state()

# Returns True if valid, raises AssertionError if invalid
# Checks:
# - No NaN/Infinity in critical values
# - Non-negative masses (with tolerance)
# - Temperature bounds
# - Non-negative omega
```
