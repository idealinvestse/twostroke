# User Guide

Complete guide for using the Two-Stroke Engine Simulation.

## Table of Contents

- [Getting Started](#getting-started)
- [Running the Simulation](#running-the-simulation)
- [Controls](#controls)
- [Understanding the Display](#understanding-the-display)
- [Tuning Guide](#tuning-guide)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)

## Getting Started

### Installation

1. **Install Python 3.11+** from [python.org](https://python.org)

2. **Download the simulation**:
   ```bash
   git clone https://github.com/yourusername/twostroke.git
   cd twostroke
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the simulation**:
   ```bash
   python main.py
   ```

### First Run

When you first start the simulation:

1. The engine will be stopped (0 RPM)
2. Hold `S` to engage the starter motor
3. The engine should start and idle around 1000-1500 RPM
4. Use `↑`/`↓` to control throttle

## Running the Simulation

### 2D Mode (PyGame)

The default 2D visualization provides:
- Real-time animated engine
- P-V diagrams
- Dashboard with gauges
- Particle effects

### 3D Mode (Godot)

For 3D visualization:

1. Download Godot 4.6.2 from [godotengine.org](https://godotengine.org)
2. Place `Godot_v4.6.2-stable_win64.exe` in `godot_engine/` folder
3. Run `launch.bat` in the godot_engine folder

## Controls

### Basic Controls

| Key | Action | Notes |
|-----|--------|-------|
| `S` | Starter motor | Hold to crank engine |
| `↑` | Increase throttle | 0% to 100% |
| `↓` | Decrease throttle | 0% to 100% |
| `Space` | Pause/Resume | Freezes simulation |
| `P` | Toggle pause | Same as Space |
| `I` | Toggle ignition | Enable/disable spark |
| `K` | Kill switch | Cut fuel supply |

### Ignition Timing

| Key | Action | Effect |
|-----|--------|--------|
| `←` | Retard ignition | Move spark later (lower angle) |
| `→` | Advance ignition | Move spark earlier (higher angle) |

**Ignition timing tips:**
- Stock: ~18-22° BTDC (Before Top Dead Center)
- Too early: Knocking, rough running
- Too late: Loss of power, hot exhaust

### Fuel Control

| Key | Action | Range |
|-----|--------|-------|
| `PgUp` | Increase fuel ratio | 0.02 - 0.15 |
| `PgDn` | Decrease fuel ratio | 0.02 - 0.15 |
| `Home` | Increase idle trim | 0.4 - 2.0 |
| `End` | Decrease idle trim | 0.4 - 2.0 |

**Fuel ratio guide:**
- 0.03-0.04: Lean, economical, hot running
- 0.045-0.055: Normal operation
- 0.06-0.08: Rich, cool running, more power potential

### Tuning Presets

| Key | Preset | Characteristics |
|-----|--------|-----------------|
| `1` | Stock | Original moped settings, reliable |
| `2` | Gattrim | Street-optimized, good reliability |
| `3` | Racing | High power, aggressive |
| `4` | Classic | 70s style, smooth and warm |
| `5` | Dragrace | Maximum acceleration |

### Engine Parameters

| Key | Parameter | Effect |
|-----|-----------|--------|
| `6` | Increase compression | More power, harder to start |
| `7` | Decrease compression | Easier starting, less power |
| `8` | Increase pipe frequency | Peak power at higher RPM |
| `9` | Decrease pipe frequency | Peak power at lower RPM |

### Advanced Tuning

| Key | Parameter | Notes |
|-----|-----------|-------|
| `[` | Decrease transfer port height | Affects mid-range torque |
| `]` | Increase transfer port height | Affects mid-range torque |
| `;` | Decrease exhaust port height | Changes power band |
| `'` | Increase exhaust port height | Changes power band |
| `,` | Decrease reed stiffness | Easier opening, more flow |
| `.` | Increase reed stiffness | More responsive, less flow |
| `/` | Decrease inertia | Faster revving |
| `\` | Increase inertia | Slower revving, more stable |
| `Shift -` | Decrease stroke | Affects displacement |
| `Shift =` | Increase stroke | Affects displacement |
| `0` | Save current tuning | Saves to `my_tune.json` |

### Quality Presets (2D Mode)

| Key | Preset | Visual Quality | Performance |
|-----|--------|----------------|-------------|
| `F1` | Simple 2D | Minimal | Fastest |
| `F2` | Low | Basic effects | Fast |
| `F3` | Medium | Good quality | Normal |
| `F4` | High | High quality | Slower |
| `F5` | Ultra | Maximum | Slowest |

## Understanding the Display

### 2D Mode Layout

```
┌─────────────────────────────────────────────────────┐
│  Engine Simulation v3.0        FPS: 60   RPM: 4500  │
├──────────────────┬──────────────────────────────────┤
│                  │                                  │
│   ENGINE         │     P-V DIAGRAMS                │
│   VISUALIZATION  │                                  │
│                  │   ┌─────────────┐ ┌────────────┐ │
│   [Animated      │   │ Cylinder    │ │ Crankcase  │ │
│    Piston,       │   │ 20         │ │  150       │ │
│    Crank,        │   │    /\      │ │     /\     │ │
│    Rod]          │   │   /  \     │ │    /  \    │ │
│                  │   │  /    \    │ │   /    \   │ │
│                  │   │ /      \   │ │  /      \  │ │
│                  │   │/        \  │ │ /        \ │ │
│                  │   │0        50│ │0        150│ │
│                  │   └─────────────┘ └────────────┘ │
│                  │   Volume (cc)    Volume (cc)   │
├──────────────────┴──────────────────────────────────┤
│  DASHBOARD                                          │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌──────┐ │
│  │ RPM   │ │ Temp  │ │ P_cyl │ │ Thr   │ │ AFR  │ │
│  │ 4500  │ │ 450°C │ │ 25bar │ │ 0.75  │ │ 14.2 │ │
│  └───────┘ └───────┘ └───────┘ └───────┘ └──────┘ │
│  [Tuning: Racing]  [Ign: 22°]  [Fuel: 0.05]         │
└─────────────────────────────────────────────────────┘
```

### Dashboard Gauges

- **RPM**: Engine speed in revolutions per minute
- **Temp**: Cylinder temperature in Celsius
- **P_cyl**: Cylinder pressure in bar (atmospheric = ~1 bar)
- **Thr**: Throttle position (0.0 to 1.0)
- **AFR**: Air/Fuel Ratio (stoichiometric = 14.7)

### P-V Diagrams

**Left (Cylinder)**: Shows pressure vs volume for cylinder
- X-axis: Volume in cc (cubic centimeters)
- Y-axis: Pressure in bar
- Loop shows complete thermodynamic cycle

**Right (Crankcase)**: Shows crankcase pressure vs volume
- Lower pressures than cylinder
- Shows transfer port effects

### Particle Effects

- **Blue particles**: Fresh air/fuel mixture entering
- **Red particles**: Hot exhaust gases
- **Yellow particles**: Combustion/spark effects

## Tuning Guide

### Stock Configuration

Best for: Learning, reliability testing

- Compression: 7.5:1
- Pipe frequency: 140 Hz
- Transfer height: 34mm
- Exhaust height: 24mm

Characteristics:
- Easy starting
- Smooth idle
- Moderate power
- Good fuel economy

### Gattrim (Street)

Best for: Daily riding simulation

- Compression: 8.0:1
- Pipe frequency: 120 Hz
- Transfer height: 32mm
- Exhaust height: 22mm

Characteristics:
- Good reliability
- Better mid-range torque
- Street-optimized

### Racing

Best for: Maximum power

- Compression: 9.5:1
- Pipe frequency: 160 Hz
- Transfer height: 38mm
- Exhaust height: 28mm

Characteristics:
- High RPM power
- Aggressive acceleration
- Requires premium fuel
- Harder starting

### Classic

Best for: Vintage feel

- Compression: 7.0:1
- Pipe frequency: 100 Hz
- Transfer height: 30mm
- Exhaust height: 20mm

Characteristics:
- Smooth power delivery
- Lower RPM operation
- "Warm" running feel

### Dragrace

Best for: Short bursts

- Compression: 10.0:1
- Pipe frequency: 180 Hz
- Transfer height: 40mm
- Exhaust height: 30mm

Characteristics:
- Extreme acceleration
- Very high RPM
- Maximum power
- Difficult to control

### Tuning Tips

#### Compression Ratio

- **Increase for**: More power, better efficiency
- **Decrease for**: Easier starting, cooler running
- **Too high**: Hard to start, knocking, damage risk
- **Too low**: Poor performance, hard to idle

#### Exhaust Pipe

The pipe is "tuned" for specific RPM:
- **Higher frequency**: Power at high RPM
- **Lower frequency**: Power at low RPM
- The "resonance" affects scavenging efficiency

#### Port Timing

Transfer ports:
- **Higher (earlier opening)**: More time for transfer, better at high RPM
- **Lower (later opening)**: More compression, better at low RPM

Exhaust port:
- **Higher**: Earlier blowdown, better high-RPM breathing
- **Lower**: More expansion ratio, better low-RPM torque

#### Reed Valve

- **Stiffer**: More responsive, less flow at low pressure
- **Softer**: More flow, can flutter at high RPM

## Troubleshooting

### Engine Won't Start

**Symptom**: Holding `S` but RPM stays at 0

**Solutions**:
1. Check ignition is enabled (`I` to toggle)
2. Check fuel isn't cut off (`K` to toggle)
3. Try lowering compression (`7` key)
4. Increase idle trim (`Home` key)
5. Make sure fuel ratio is in range (0.03-0.08)

### Engine Dies at Idle

**Symptom**: Runs with throttle but stalls when idle

**Solutions**:
1. Increase idle fuel trim (`Home` key)
2. Retard ignition timing slightly (`←` key)
3. Switch to "Gattrim" or "Stock" preset (`2` or `1`)
4. Check fuel ratio isn't too lean

### No Power / Weak Acceleration

**Symptom**: High RPM but poor torque

**Solutions**:
1. Check tuning preset (use `3` for racing)
2. Increase compression (`6` key)
3. Optimize ignition timing
4. Check fuel ratio (try 0.06-0.07)

### Engine Knocking / Rough

**Symptom**: Rough sound, vibration

**Solutions**:
1. Retard ignition timing (`←` key)
2. Decrease compression (`7` key)
3. Increase fuel ratio (richer mixture)
4. Check if running too lean

### Overheating

**Symptom**: Temperature gauge shows >500°C

**Solutions**:
1. Increase fuel ratio (richer = cooler)
2. Improve scavenging (adjust ports)
3. Reduce compression slightly
4. Check pipe frequency matching RPM

### Low FPS / Lag

**Symptom**: Choppy animation, low frame rate

**Solutions**:
1. Lower quality preset (`F1` or `F2`)
2. Disable bloom (not available in MEDIUM or lower)
3. Reduce particle count
4. Close other applications
5. Check GPU drivers are updated

## Advanced Topics

### Understanding the Physics

#### Two-Stroke Cycle

1. **Intake/Scavenging** (Piston near BDC):
   - Transfer ports open
   - Fresh charge enters cylinder
   - Pushes exhaust out
   - Reed valve opens to fill crankcase

2. **Compression** (Piston rising):
   - Ports close
   - Fuel-air mixture compressed
   - Pressure and temperature rise

3. **Combustion** (Near TDC):
   - Spark ignites mixture
   - Rapid pressure rise
   - Heat release

4. **Expansion** (Piston forced down):
   - Power stroke
   - Pressure pushes piston
   - Torque generated

5. **Exhaust** (Piston near BDC):
   - Exhaust port opens
   - Pressure wave enters pipe
   - Blowdown reduces cylinder pressure

#### Key Concepts

**Scavenging**: Process of pushing exhaust out with fresh charge
- Good scavenging = more power, cooler running
- Poor scavenging = wasted fuel, overheating

**Pipe Tuning**: Using pressure waves to improve exhaust
- Expansion wave helps draw out exhaust
- Reflection can push fresh charge back in
- Tuned for specific RPM range

**Port Timing**: When ports open/close relative to piston position
- Earlier opening = more flow, less trapping
- Later opening = more compression, less flow

### Performance Tuning Strategy

1. **Start with baseline**: Use Stock or Gattrim preset
2. **Get it running**: Ensure stable idle
3. **Optimize ignition**: Find best timing for your setup
4. **Adjust fuel**: Balance power and temperature
5. **Fine-tune ports**: Adjust for desired RPM range
6. **Pipe matching**: Ensure pipe frequency matches operating RPM

### Saving Custom Tunes

Press `0` to save current settings to `my_tune.json`

Load with:
```python
from config import load_tuning_preset
load_tuning_preset(engine, "path/to/my_tune.json")
```

### Data Export

You can log engine data for analysis:

```python
import csv

with open('engine_data.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Time', 'RPM', 'P_cyl', 'T_cyl'])
    
    for i in range(6000):  # 10 seconds at 600 Hz
        state = engine.step(1.0/600.0)
        if i % 60 == 0:  # Log at 10 Hz
            writer.writerow([
                i/600.0,
                state.omega * 60 / (2*3.14159),
                state.p_cyl,
                state.T_cyl
            ])
```

### Network Visualization

The 3D mode uses TCP communication:
- Physics server (Python) runs on port 9999
- Godot client connects and receives state at 60 Hz
- Can be modified to work across network

## Tips and Tricks

1. **Watch the P-V diagram**: A tight, high loop = efficient engine
2. **Temperature matters**: Keep T_cyl < 500°C for longevity
3. **Lambda target**: Aim for 0.9-1.1 (slightly rich to slightly lean)
4. **Ignition sweep**: Try advancing timing until knock, then back off 2-3°
5. **Pipe resonance**: Set frequency to match your typical operating RPM

## Resources

- [Two-Stroke Engine Tuning](https://www.amazon.com/Two-Stroke-Engine-Technology-Gordon-Blair/dp/0768004409) - Technical reference
- [Engine Builder Calculator](http://www.wiseco.com/) - Real-world tools
- [Online P-V Diagram Tool](https://www.desmos.com/) - Visualize cycles
