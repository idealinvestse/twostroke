# System Architecture

This document describes the architecture of the Two-Stroke Engine Simulation system.

## Overview

The system is designed with a clean separation between physics simulation and visualization, enabling both 2D and 3D rendering modes while sharing the same accurate thermodynamic model.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Application Layer                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐                           ┌──────────────────┐   │
│  │   PyGame App     │                           │   Godot Engine   │   │
│  │   (app.py)       │      ┌─────────────┐      │   (Vulkan)       │   │
│  │                  │      │  TCP Socket │      │                  │   │
│  │  - Event loop    │      │   (9999)    │      │  - 3D renderer   │   │
│  │  - 2D rendering  │◄────►│  60 Hz JSON │◄────►│  - PBR materials │   │
│  │  - User input    │      │             │      │  - UI system     │   │
│  └──────────────────┘      └─────────────┘      └──────────────────┘   │
│           │                                            │                  │
│           └────────────────┬─────────────────────────┘                  │
│                            ▼                                            │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    Physics Engine (600 Hz)                       │    │
│  │                                                                  │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│    │
│  │  │  Kinematics │  │Thermodynamics│  │        Flows            ││    │
│  │  │  (slider-   │  │  (gas laws,  │  │  (orifice, reed,       ││    │
│  │  │   crank)    │  │   heat)      │  │   pipe)                 ││    │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘│    │
│  │                                                                  │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│    │
│  │  │ Combustion  │  │   Friction  │  │      Cylinder           ││    │
│  │  │  (burn,     │  │  (pumping,  │  │   (state management)    ││    │
│  │  │   spark)    │  │   friction) │  │                         ││    │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘│    │
│  │                                                                  │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                            │                                            │
│                            ▼                                            │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    State & Configuration                         │    │
│  │                                                                  │    │
│  │  - EngineSnapshot (immutable state)                            │    │
│  │  - CylinderState (per-cylinder state)                          │    │
│  │  - Quality presets (Simple 2D to Ultra)                          │    │
│  │  - Tuning presets (Stock to Dragrace)                            │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Physics Engine Architecture

### Core Classes

```
EnginePhysics (engine_physics.py)
│
├── Kinematics: SliderCrankKinematics
│   └── Calculates piston position, velocity from crank angle
│
├── Cylinders: List[Cylinder]
│   └── Each cylinder manages:
│       - Thermodynamic state (pressure, temperature, mass)
│       - Combustion state (burn fraction, active flag)
│       - Port timing and areas
│
├── Flow Calculator: FlowCalculator
│   └── Calculates mass flows:
│       - Intake through reed valve
│       - Transfer between crankcase and cylinder
│       - Exhaust through port and pipe
│
├── Combustion Model: CombustionModel
│   └── Manages:
│       - Spark timing and ignition
│       - Burn duration and efficiency
│       - Heat release calculation
│
├── Friction Model: FrictionModel
│   └── Calculates:
│       - Mechanical friction
│       - Pumping losses
│       - Lubrication effects
│
└── Scavenging: ScavengingCalculator
    └── Models:
        - Short-circuiting losses
        - Trapping efficiency
        - Mixing dynamics
```

### Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                      Physics Step (dt = 1/600s)                │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  1. KINEMATICS                                               │
│     - Update crank angle (theta)                             │
│     - Calculate piston position (x) and velocity (v)         │
│     - Determine port openings from piston position           │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  2. GAS FLOWS                                                │
│     - Calculate intake flow (reed valve dynamics)            │
│     - Calculate transfer flow (crankcase ↔ cylinder)         │
│     - Calculate exhaust flow (port + pipe resonance)         │
│     - Update cylinder and crankcase masses                   │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  3. COMBUSTION                                               │
│     - Check ignition conditions (spark timing, fuel present) │
│     - Start combustion if conditions met                     │
│     - Update burn fraction and heat release                  │
│     - Handle fuel film evaporation                           │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  4. THERMODYNAMICS                                           │
│     - Update temperatures from heat transfer                 │
│     - Calculate pressures from ideal gas law                 │
│     - Apply energy balance (work, heat, enthalpy)            │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  5. DYNAMICS                                                 │
│     - Calculate gas pressure forces on piston              │
│     - Add friction and pumping losses                        │
│     - Update angular velocity (omega) from torque balance    │
│     - Apply idle assistance if RPM too low                   │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  6. STATE UPDATE                                               │
│     - Create EngineSnapshot with current state               │
│     - Return state for visualization                         │
└──────────────────────────────────────────────────────────────┘
```

## Visualization Architecture

### 2D Mode (PyGame)

```
EngineApp (app.py)
│
├── Main Loop (60 FPS)
│   ├── Event handling (keyboard input)
│   ├── Physics update (600 Hz, 10 substeps)
│   └── Rendering
│
├── EngineRenderer (renderer.py)
│   ├── draw_crankshaft()     - Animated crank
│   ├── draw_piston()         - Piston with position from kinematics
│   ├── draw_cylinder()       - Cylinder with heat effects
│   ├── draw_rod()            - Connecting rod
│   ├── draw_pv_diagram()     - P-V diagrams for cyl/crankcase
│   ├── draw_dashboard()      - Gauges and readouts
│   └── draw_ui()             - Tuning controls overlay
│
├── Particle System (particles.py)
│   ├── spawn_particles()     - Create particles on events
│   └── update_particles()    - Animate and expire particles
│
└── State Management
    ├── pv_cyl_points         - P-V history (deque, maxlen=300)
    └── pv_cr_points          - Crankcase P-V history
```

### 3D Mode (Godot 4.x)

```
Godot Engine
│
├── Main Scene (main.tscn)
│   └── Engine Controller (engine_controller.gd)
│       ├── Cylinder assembly (piston, rod, crank)
│       ├── Reed valve animation
│       └── Exhaust pipe visualization
│
├── Physics Bridge (physics_bridge.gd)
│   ├── TCP client connection to Python physics_server.py
│   ├── JSON protocol with 4-byte length prefix
│   ├── Automatic reconnection logic
│   └── State deserialization
│
├── UI Controller (ui_controller.gd)
│   ├── Dashboard gauges (RPM, temp, pressure)
│   ├── Control panel (throttle, ignition, fuel)
│   └── Tuning interface
│
└── Effects
    ├── Combustion particles (GPU)
    ├── Gas flow visualization
    └── PBR materials (aluminum, steel, carbon fiber)
```

### Inter-Process Communication

```
Python Physics Server                    Godot Client
(physics_server.py)                    (physics_bridge.gd)
│                                          │
│  ┌──────────────────────────────┐       │
│  │  TCP Server (localhost:9999)  │◄──────┤  Connect
│  └──────────────────────────────┘       │
│           │                              │
│           ▼                              │
│  ┌──────────────────────────────┐       │
│  │  4-byte length prefix (big)  │       │
│  │  + JSON payload              │──────►│  4-byte length
│  │  60 times per second         │       │  + Parse JSON
│  └──────────────────────────────┘       │
│                                          │
│  State format:                           │
│  {                                        │
│    "theta": float,      # radians        │
│    "rpm": float,        # rev/min        │
│    "x": float,          # piston pos (m) │
│    "p_cyl": float,      # Pa             │
│    "T_cyl": float,      # Kelvin         │
│    "omega": float,      # rad/s          │
│    "a_exh": float,      # exhaust area   │
│    "a_tr": float,       # transfer area   │
│    ...                                   │
│  }                                        │
│                                          │
│  Commands from Godot:                    │
│  - THROTTLE:<value>                      │
│  - IGNITION_ANGLE:<value>                │
│  - FUEL_RATIO:<value>                  │
│  - IDLE_TRIM:<value>                   │
│  - ENABLE_IGNITION:<bool>                │
│  - KILL_SWITCH:<bool>                    │
│  - STARTER_MOTOR:<bool>                  │
└──────────────────────────────────────────┘
```

## Module Dependencies

```
physics/
├── constants.py          # No dependencies (base constants)
├── utils.py             # No dependencies
├── thermodynamics.py    # Uses: constants
├── kinematics.py        # Uses: constants, dataclasses
├── flows.py             # Uses: constants, thermodynamics, utils, dataclasses
├── friction.py          # Uses: dataclasses, enum
├── combustion.py        # Uses: constants, math, dataclasses
├── cylinder.py          # Uses: constants, thermodynamics, combustion, dataclasses
└── engine_physics.py    # Uses: all above, typing

rendering/
├── animations.py        # Uses: pygame
├── bloom.py             # Uses: pygame, numpy, rendering.procedural
├── gauges.py            # Uses: pygame, math
├── materials.py         # Uses: pygame, dataclasses
└── procedural.py        # Uses: pygame, numpy

Root level:
├── config.py            # Uses: dataclasses, enum, json, os
├── particles.py         # Uses: pygame, config, random, math
├── renderer.py          # Uses: pygame, config, physics, rendering.*, collections
├── app.py               # Uses: pygame, physics, renderer, particles, config
└── engine_profiles.py   # Uses: dataclasses
```

## State Management

### EngineSnapshot (Immutable)

```python
@dataclass(frozen=True)
class EngineSnapshot:
    # Kinematics
    theta: float          # Crank angle (radians)
    x: float              # Piston position from TDC (m)
    v_cyl: float          # Cylinder volume (m³)
    v_cr: float           # Crankcase volume (m³)
    
    # Thermodynamics
    p_cyl: float          # Cylinder pressure (Pa)
    p_cr: float           # Crankcase pressure (Pa)
    T_cyl: float          # Cylinder temperature (K)
    T_cr: float           # Crankcase temperature (K)
    
    # Masses
    m_air_cyl: float      # Cylinder air mass (kg)
    m_fuel_cyl: float     # Cylinder fuel mass (kg)
    m_burned_cyl: float   # Cylinder burned mass (kg)
    m_air_cr: float       # Crankcase air mass (kg)
    m_fuel_cr: float      # Crankcase fuel mass (kg)
    
    # Flows
    dm_exh: float         # Exhaust mass flow (kg/s)
    dm_tr: float          # Transfer mass flow (kg/s)
    dm_air_in: float      # Intake air flow (kg/s)
    dm_fuel_in: float     # Intake fuel flow (kg/s)
    
    # State flags
    combustion_active: bool
    spark_active: bool
    burn_fraction: float
    reed_opening: float
    
    # Dynamics
    omega: float          # Angular velocity (rad/s)
    cycle_torque: float   # Instantaneous torque (Nm)
    pipe_amplitude: float # Exhaust pulse amplitude
```

### Configuration Presets

**Quality Presets (RenderConfig)**

| Preset | HD Scale | Bloom | Particles | Materials | Target FPS |
|--------|----------|-------|-----------|-----------|------------|
| Simple 2D | 1.0x | No | 150 | No | 60 |
| Low | 1.0x | No | 200 | No | 60 |
| Medium | 1.0x | No | 300 | Yes | 60 |
| High | 1.5x | Yes | 500 | Yes | 60 |
| Ultra | 2.0x | Yes | 800 | Yes | 60 |

**Tuning Presets (Engine Parameters)**

| Preset | Compression | Pipe Freq | Transfer Height | Use Case |
|--------|-------------|-----------|-----------------|----------|
| Stock | 7.5:1 | 140 Hz | 34mm | Original moped |
| Gattrim | 8.0:1 | 120 Hz | 32mm | Street reliability |
| Racing | 9.5:1 | 160 Hz | 38mm | Competition |
| Classic | 7.0:1 | 100 Hz | 30mm | 70s style |
| Dragrace | 10.0:1 | 180 Hz | 40mm | Max acceleration |

## Design Principles

1. **Separation of Concerns**: Physics engine knows nothing about rendering; visualization layers are interchangeable.

2. **Fixed Timestep**: Physics runs at 600 Hz (1/600s dt) for stability. Rendering interpolates or subsamples.

3. **Immutable State**: EngineSnapshot is frozen; each step creates a new state object.

4. **Defensive Programming**: All division operations guarded against zero. State validation at each step.

5. **Modularity**: Each physics subsystem (kinematics, thermodynamics, etc.) is independently testable.

6. **Backward Compatibility**: Physics module exports compatibility shims for older code patterns.

## Performance Considerations

### Physics (600 Hz)
- Each step: ~0.5 ms on modern CPU
- Target: Consistent 600 Hz regardless of rendering FPS
- Optimizations: Pre-calculated tables, minimal allocations

### 2D Rendering (60 FPS)
- PyGame blitting is the bottleneck
- HD rendering uses scaled blitting
- Bloom requires pixel iteration (expensive, optional)

### 3D Rendering (60 FPS)
- Godot handles all rendering
- TCP IPC adds ~1ms latency
- Physics server runs in separate process

## Future Architecture Considerations

1. **Multi-threading**: Physics could parallelize cylinder calculations
2. **GPU Physics**: CUDA/OpenCL for particle systems
3. **Web Export**: WebAssembly build of physics engine
4. **Multiplayer**: Network-synchronized physics state
5. **Data Export**: Real-time logging to CSV/ HDF5
