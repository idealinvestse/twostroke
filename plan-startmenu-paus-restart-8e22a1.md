# Plan för Startmeny och Simuleringskontroll

En plan för att utveckla startmeny, paus och restart-funktionalitet för både Godot 3D och PyGame 2D-versionerna av 2-taktsmotorsimuleringen.

## Nuvarande Arkitektur

Systemet har tydlig separation mellan fysikmotor och visualisering:
- **PyGame 2D** (`app.py`): Kör fysik och 2D-rendering i samma process, har redan `paused` flagga
- **Godot 3D** (`godot_engine/`): TCP-baserad kommunikation med Python-fysikservern (`physics_server.py`)
- **Konfiguration**: `config.py` hanterar QualityPreset och TuningPreset
- **Motorprofiler**: `engine_profiles.py` + `engine_profiles.json` med 22+ profiler

## Mål

### Startmeny
- **Motorprofil-val**: Lista alla profiler från `engine_profiles.json` med metadata (cc, kW, RPM)
- **Kvalitetspreset**: Simple 2D / Low / Medium / High / Ultra
- **Display-inställningar**: Upplösning, fullskärm, vsync (Godot); fönsterstorlek (PyGame)

### Runtime-kontroller
- **Paus**: Fryser fysiken helt, behåller state, möjliggör parameterjustering
- **Restart**: Återställer motor till kallt starttillstånd (tom vevhus, 293K) men behåller vald profil och renderingsinställningar
- **Slow-motion**: Separat funktion (25% hastighet) via snabbtangent

## Implementation

### Del 1: PyGame 2D-versionen

**Nya filer:**
- `ui/main_menu.py` - Startmeny med motorprofillista, kvalitetspreset, display-inställningar
- `ui/menu_state.py` - Enum för meny-tillstånd (MAIN_MENU, SIMULATION, PAUSED)

**Ändringar i befintliga filer:**
- `app.py`:
  - Lägg till `menu_state` attribut
  - Modifiera `run()` för att visa startmeny först
  - Lägg till menynavigation (ESC för paus-meny)
  - Utöka `handle_event()` för meny-input
  - Modifiera `update()` för att hoppa över fysik när pausad
- `config.py`: Lägg till display-inställnings-hantering (upplösning, fullskärm)
- `renderer.py`: Lägg till `draw_menu()` och `draw_pause_overlay()`

**Dataflöde:**
```
main.py → EngineApp.run()
   └─> Visa MainMenu → Välj profil + kvalitet + display
      └─> Initiera EnginePhysics med profil
         └─> Starta simuleringsloop (event → update → render)
            └─> ESC → PauseMenu (Fortsätt / Restart / Huvudmeny)
```

### Del 2: Godot 3D-versionen

**Nya filer:**
- `godot_engine/scenes/ui/main_menu.tscn` - Huvudmeny-scen
- `godot_engine/scenes/ui/pause_menu.tscn` - Pausmeny (överlagring)
- `godot_engine/scripts/main_menu.gd` - Logik för startmeny
- `godot_engine/scripts/pause_menu.gd` - Paus-/restart-logik
- `godot_engine/scripts/game_state_manager.gd` - Autoload singleton för global state (SimulationState enum)

**Ändringar i befintliga filer:**
- `project.godot`:
  - Lägg till `GameStateManager` som autoload
  - Lägg till input-mappings: `ui_menu` (ESC), `ui_pause` (P), `ui_restart` (R)
- `physics_bridge.gd`:
  - Lägg till `set_pause_state(bool)` metod
  - Modifiera `_poll_connection()` för att skicka PAUSE-kommando till Python-servern
  - Lägg till `restart_simulation()` signal och metod
- `physics_server.py`:
  - Lägg till `paused` state-variabel
  - Modifiera `handle_client()` för att pausa fysikloopen
  - Lägg till `restart()` metod som återställer motorns tillstånd
  - Lägg till `process_command()` case för "RESTART" och "PAUSE"
- `engine_controller.gd`:
  - Lyssna på `GameStateManager.simulation_restarted` signal
  - Återställ visuella effekter vid restart
- `main.tscn`:
  - Ersätt direktladdning med `GameStateManager`-styrd scenhantering
  - Behåll befintligt Dashboard som undermeny till paus-meny

**Godot scen-hierarki:**
```
GameStateManager (autoload)
   ├─> MainMenu.tscn (vid start)
   │      └─> Profil-dropdown, Quality-dropdown, Display-settings
   │      └─> "Start Simulation" → byt till Main.tscn
   │
   └─> Main.tscn (simulation)
          ├─> EngineAssembly (befintlig)
          ├─> CanvasLayer
          │      ├─> Dashboard (befintlig, alltid synlig)
          │      └─> PauseMenu (överlagring vid ESC/P)
          │              └─> Fortsätt / Restart / Huvudmeny
          └─> PhysicsBridge (befintlig)
```

### Del 3: Python Physics Server

**Ändringar i `physics_server.py`:**
```python
class PhysicsServer:
    def __init__(self):
        # ... existing code ...
        self.paused = False
        self.restart_requested = False
    
    def process_command(self, data: str):
        # ... existing commands ...
        elif key == 'PAUSE':
            self.paused = value.upper() in ('TRUE', '1', 'YES')
        elif key == 'RESTART':
            self.restart_requested = True
    
    def restart_simulation(self):
        """Återställ motor till kallt starttillstånd."""
        # Spara nuvarande profil-inställningar
        profile_backup = self._get_current_profile_settings()
        
        # Återställ all state
        self.engine = EnginePhysics()
        self._apply_profile_settings(self.engine, profile_backup)
        
        # Återställ hjälp-variabler
        self.pv_cyl_points.clear()
        self.pv_cr_points.clear()
        self._tick_count = 0
        self._starter_pressed = False
        
        print("Simulation restarted")
```

## Tekniska Detaljer

### Motorprofil-laddning

**PyGame:**
```python
from engine_profiles import list_all_profiles, apply_profile

profiles = list_all_profiles()  # [(key, name, source), ...]
# Rendera lista med name, cc, kW, RPM från metadata
```

**Godot:**
```gdscript
# Ladda JSON via HTTPRequest eller FileAccess
var json_path = ProjectSettings.globalize_path("res://../../engine_profiles.json")
var profiles = parse_json_profiles(json_path)
# Fyll OptionButton med profil-namn
```

### State-hantering

| Tillstånd | PyGame | Godot + Python |
|-----------|--------|----------------|
| Startmeny | `MainMenu` klass | `MainMenu.tscn` |
| Simulering | `EngineApp.running` | `SimulationState.RUNNING` |
| Paus | `EngineApp.paused` + skip physics | `PAUSE` kommando till servern |
| Restart | Återställ `EnginePhysics` | `RESTART` kommando + återställ GD |

### Kommunikationsprotokoll (Godot)

Nya TCP-kommandon från Godot till Python:
```
PAUSE:TRUE       → Pausa fysiken
PAUSE:FALSE      → Återuppta
RESTART:1        → Återställ motorstate
PROFILE:am6_stock → Växla profil (vid runtime, krävs restart)
```

## Uppgiftslista

1. **PyGame Main Menu** (`ui/main_menu.py`)
   - [ ] UI-klass med profillista, kvalitet, display
   - [ ] Motorprofil-metadata display (cc, kW, RPM)
   - [ ] Start-knapp som initierar EngineApp

2. **PyGame Integration** (`app.py`, `config.py`)
   - [ ] Modifiera `EngineApp` för menystyrning
   - [ ] Paus-meny med ESC
   - [ ] Restart-funktion i paus-meny

3. **Godot GameStateManager** (`scripts/game_state_manager.gd`)
   - [ ] Autoload singleton
   - [ ] SimulationState enum
   - [ ] Scene-växlingslogik

4. **Godot Main Menu** (`scenes/ui/main_menu.tscn`, `scripts/main_menu.gd`)
   - [ ] Scen med UI-kontroller
   - [ ] JSON-profilladdning
   - [ ] Quality-preset dropdown
   - [ ] Display-inställningar

5. **Godot Pause Menu** (`scenes/ui/pause_menu.tscn`, `scripts/pause_menu.gd`)
   - [ ] Överlagrings-UI
   - [ ] Fortsätt/Restart/Huvudmeny-knappar
   - [ ] ESC/P-tangenthantering

6. **Physics Server** (`physics_server.py`)
   - [ ] PAUSE-kommando-hantering
   - [ ] RESTART-kommando-hantering
   - [ ] State-återställningslogik

7. **Integrationstest**
   - [ ] Testa Godot → Python PAUSE-kommando
   - [ ] Testa RESTART återställer state korrekt
   - [ ] Testa PyGame meny → simulering → paus → restart

## Filstruktur

```
twostroke/
├── ui/
│   ├── __init__.py
│   ├── main_menu.py          # Ny
│   └── menu_state.py         # Ny
├── app.py                    # Modifierad
├── config.py                 # Modifierad
├── renderer.py               # Modifierad
├── godot_engine/
│   ├── scripts/
│   │   ├── game_state_manager.gd   # Ny (autoload)
│   │   ├── main_menu.gd            # Ny
│   │   ├── pause_menu.gd           # Ny
│   │   ├── physics_bridge.gd       # Modifierad
│   │   └── physics_server.py       # Modifierad
│   ├── scenes/
│   │   ├── ui/
│   │   │   ├── main_menu.tscn      # Ny
│   │   │   ├── pause_menu.tscn     # Ny
│   │   │   └── dashboard.tscn      # Befintlig
│   │   └── main.tscn               # Modifierad
│   └── project.godot               # Modifierad
```

## Beroenden

- PyGame: Använd befintliga `pygame_menu` om tillgängligt, annars custom UI
- Godot: Endast inbyggda UI-noder (Control, Panel, Button, OptionButton, etc.)
- Python: Befintliga `engine_profiles` för JSON-laddning
