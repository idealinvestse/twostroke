"""Physical constants for 2-stroke engine simulation.

All constants are in SI units (kg, m, s, K, Pa, J).
"""

import math

# Gas constants (Air)
R_GAS = 287.05  # J/(kg·K), specific gas constant for air
C_V = 718.0     # J/(kg·K), specific heat at constant volume
C_P = 1005.0    # J/(kg·K), specific heat at constant pressure
GAMMA = C_P / C_V  # Heat capacity ratio (≈1.4 for air)

# Atmospheric conditions
P_ATM = 101325.0  # Pa, standard atmospheric pressure
T_ATM = 293.15    # K, standard atmospheric temperature (20°C)

# Pressure limits (safety clamps)
MIN_PRESSURE = 20000.0           # Pa, minimum cylinder pressure
MIN_CRANKCASE_PRESSURE = 35000.0 # Pa, minimum crankcase pressure
MAX_CYLINDER_PRESSURE = 8_000_000.0  # Pa, ~80 bar max
MAX_CRANKCASE_PRESSURE = 250_000.0  # Pa, ~2.5 bar max

# Engine limits
MAX_OMEGA = 950.0  # rad/s, ~9000 RPM limit for simulation stability

# Fuel properties (Gasoline)
FUEL_LHV = 44_000_000.0  # J/kg, lower heating value
STOICH_AFR = 14.7       # kg air / kg fuel, stoichiometric ratio

# Flow constants
DISCHARGE_COEF_EXHAUST = 0.7
DISCHARGE_COEF_TRANSFER = 0.7
DISCHARGE_COEF_INTAKE_MAIN = 0.72
DISCHARGE_COEF_INTAKE_IDLE = 0.66

# Thermal constants
T_WALL_CYLINDER = 450.0   # K, typical cylinder wall temp for air-cooled
T_WALL_CRANKCASE = 350.0  # K, crankcase wall temp
HEAT_TRANSFER_COEF = 15.0  # W/(m²·K), convective heat transfer

# Combustion constants
OPTIMAL_IGNITION_ANGLE_DEG = 342.0
IGNITION_EFFICIENCY_SIGMA = 18.0  # degrees
MIXTURE_EFFICIENCY_OPTIMAL_LAMBDA = 0.92
MIXTURE_EFFICIENCY_SIGMA = 0.35

# Reed valve constants (simplified spring-mass-damper)
REED_STIFFNESS = 1200.0  # N/m equivalent
REED_DAMPING = 40.0      # N·s/m equivalent
REED_PRESSURE_COEF = 0.02  # m³/Pa effective area

# Exhaust pipe constants
PIPE_RESONANCE_FREQ_HZ = 140.0  # Hz, tuned for ~8400 RPM
PIPE_Q_FACTOR = 2.5
PIPE_AMPLITUDE_DECAY = 15.0  # 1/s, decay when exhaust closed
PIPE_MAX_SUCTION_PA = 60000.0   # Max 0.6 bar below atm
PIPE_MAX_PRESSURE_PA = 40000.0  # Max 0.4 bar above atm
MAX_PIPE_AMPLITUDE = 80000.0    # Max amplitude (Pa) — ~0.8 bar peak, physical limit

# Fuel film constants
CRANKCASE_WET_FRACTION_BASE = 0.50
CRANKCASE_WET_FRACTION_THROTTLE_COEF = 0.30
CRANKCASE_EVAP_BASE = 1.5
CRANKCASE_EVAP_THROTTLE_COEF = 4.0
CRANKCASE_EVAP_TEMP_COEF = 0.02

# Numerical guards
EPSILON_MASS = 1e-9       # Minimum mass to prevent division by zero
EPSILON_VOLUME = 1e-9     # Minimum volume
EPSILON_PRESSURE = 1e-12   # Minimum pressure differential
MIN_DT = 1e-6             # Minimum timestep

# EMA smoothing constants
RPM_EMA_ALPHA = 0.02
TORQUE_EMA_ALPHA = 0.20
POWER_EMA_ALPHA = 0.20

# Mechanical efficiency
MECHANICAL_EFFICIENCY = 0.85

# Engine geometry (more realistic 50cc specs)
# Based on typical 50cc 2-stroke engines (e.g., KTM 50 SX, Yamaha YZ50)
ENGINE_BORE_MM = 40.0           # 40mm bore (was 54mm - too large)
ENGINE_STROKE_MM = 39.7         # ~40mm stroke (was 50mm)
CON_ROD_LENGTH_MM = 81.0        # 81mm connecting rod
COMPRESSION_RATIO = 8.0         # 8.0:1 (was 8.5:1)
CRANKCASE_VOLUME_RATIO = 1.4    # 1.4x displacement (was 1.8x)

# Port positions (relative to TDC, in mm from TDC)
# For 50cc engine with ~40mm stroke:
# Exhaust opens at ~50% of stroke for blowdown
# Transfer opens at ~55% of stroke - earlier to open when crankcase pressure is high
EXHAUST_PORT_OPEN_MM = 20.0     # x_exh (~50% of stroke)
TRANSFER_PORT_OPEN_MM = 22.0     # x_tr (~55% of stroke) - opens before max crankcase compression
EXHAUST_PORT_WIDTH_MM = 35.0     # w_exh (wider for better blowdown)
TRANSFER_PORT_WIDTH_MM = 32.0    # w_tr (wider for better fuel transfer)

# Maximum intake area
MAX_INTAKE_AREA_M2 = 0.0012     # m², A_in_max

# Derived engine constants
BORE_M = ENGINE_BORE_MM / 1000
STROKE_M = ENGINE_STROKE_MM / 1000
CON_ROD_M = CON_ROD_LENGTH_MM / 1000
HALF_STROKE_M = STROKE_M / 2  # Crank radius R
PISTON_AREA_M2 = math.pi * (BORE_M / 2) ** 2
DISPLACEMENT_M3 = PISTON_AREA_M2 * STROKE_M
CLEARANCE_VOLUME_M3 = DISPLACEMENT_M3 / (COMPRESSION_RATIO - 1)
CRANKCASE_VOLUME_M3 = DISPLACEMENT_M3 * CRANKCASE_VOLUME_RATIO

EXHAUST_PORT_OPEN_M = EXHAUST_PORT_OPEN_MM / 1000
TRANSFER_PORT_OPEN_M = TRANSFER_PORT_OPEN_MM / 1000
EXHAUST_PORT_WIDTH_M = EXHAUST_PORT_WIDTH_MM / 1000
TRANSFER_PORT_WIDTH_M = TRANSFER_PORT_WIDTH_MM / 1000

# Friction model constants
# Oil properties (SAE 10W-40 at operating temp)
MU_OIL_BOUNDARY = 0.5        # Pa·s, effective viscosity in boundary regime
MU_OIL_HYDRODYNAMIC = 0.01   # Pa·s, viscosity in hydrodynamic regime

# Piston ring properties
PISTON_RING_TENSION = 8.0    # N per ring (typical for 40mm bore)
PISTON_NUM_RINGS = 2         # Number of rings (typical for 2-stroke)

# Piston skirt
PISTON_SKIRT_AREA = 0.0015   # m², contact area (typical for 40mm bore)

# Bearings
CRANK_BEARING_DIAMETER = 0.020  # m (20mm main bearing)
CRANK_BEARING_WIDTH = 0.015     # m (15mm width)

# Oil film thickness
OIL_FILM_THICKNESS_MIN = 0.000001    # 1 micron minimum
OIL_FILM_THICKNESS_HYDRO = 0.00001   # 10 micron hydrodynamic
