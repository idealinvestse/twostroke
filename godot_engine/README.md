# 2-Stroke Engine Simulation v3.0 - Godot 4.x

Professional 3D visualization of 2-stroke engine thermodynamics with Vulkan rendering.

## Requirements

- Windows 10/11
- Godot 4.6+ (Vulkan-compatible GPU)
- Python 3.11+ (for physics server)

## Quick Start

1. **Install Godot 4.6.2:**
   - Download from https://godotengine.org/download
   - Place `Godot_v4.6.2-stable_win64.exe` in this directory

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch:**
   ```bash
   launch.bat
   ```

## Architecture

```
┌─────────────────┐     TCP Socket      ┌─────────────────┐
│  Physics Server │  ←──────────────→  │   Godot Engine    │
│   (Python)      │    60 Hz JSON       │    (Vulkan)       │
│                 │                     │                 │
│ • Thermodynamics│                     │ • 3D Rendering  │
│ • Combustion    │                     │ • Animation     │
│ • Gas flows     │                     │ • Effects       │
│ • PV diagrams   │                     │ • UI/Gauges     │
└─────────────────┘                     └─────────────────┘
        600 Hz                                   60 FPS
```

## Project Structure

```
godot_engine/
├── project.godot          # Godot project config
├── launch.bat            # Windows launcher
├── scenes/
│   ├── main.tscn         # Main 3D scene
│   ├── engine/
│   │   ├── cylinder.tscn # Cylinder assembly
│   │   ├── piston.tscn   # Animated piston
│   │   ├── crankshaft.tscn # Rotating crank
│   │   └── reed_valve.tscn # Flexing reed
│   ├── effects/
│   │   ├── combustion.tscn # Fire/sparks
│   │   └── gas_flows.tscn  # Particle systems
│   └── ui/
│       ├── dashboard.tscn  # 3D gauges
│       └── controls.tscn   # Interactive panel
├── scripts/
│   ├── physics_server.py   # TCP physics server
│   ├── physics_bridge.gd   # Godot client
│   ├── engine_controller.gd # Main controller
│   └── animation_controller.gd # Animation system
└── assets/
    ├── materials/          # PBR materials
    ├── models/             # 3D meshes
    └── shaders/            # Custom effects
```

## Controls

- **Mouse Left + Drag:** Orbit camera
- **Mouse Scroll:** Zoom in/out
- **C:** Toggle cutaway view
- **Space:** Toggle play/pause
- **Up/Down:** Throttle control

## Features

### v3.0 New Features
- ✅ Full 3D engine visualization
- ✅ PBR materials (aluminum, steel, carbon fiber)
- ✅ Real-time shadows and lighting
- ✅ Hardware-accelerated bloom
- ✅ Volumetric combustion effects
- ✅ 3D particle systems (100k+ particles)
- ✅ Animated slider-crank mechanism
- ✅ Interactive camera system
- ✅ Real-time PV diagrams
- ✅ Single .exe export

### Performance
- Target: 60 FPS @ 1080p
- Physics: 600 Hz
- Rendering: Vulkan Forward+
- Memory: < 200 MB

## Development

### Physics Integration
The physics server runs independently and streams state via TCP:

```python
# physics_server.py
state = {
    'theta': crank_angle,           # radians
    'rpm': engine_rpm,              # rev/min
    'x': piston_position,           # meters from TDC
    'p_cyl': cylinder_pressure,     # Pascals
    'T_cyl': cylinder_temp,       # Kelvin
    'combustion_active': bool,      # true/false
    'spark_active': bool,          # true/false
    'reed_opening': float,         # 0.0-1.0
}
```

### Adding Components
1. Create scene in `scenes/engine/`
2. Add to `main.tscn`
3. Reference in `engine_controller.gd`
4. Animate in `_update_*` method

## Troubleshooting

### "Physics server connection failed"
- Check Python is installed: `python --version`
- Verify physics_server.py exists in scripts/
- Check port 9999 is not in use

### "Godot crashes on startup"
- Update GPU drivers (Vulkan support required)
- Try `--rendering-driver opengl3` flag
- Check Windows Event Viewer for details

### "Low FPS"
- Reduce shadow quality in Project Settings
- Disable SSAO/Glow if needed
- Lower particle counts

## License

Same as parent project.
