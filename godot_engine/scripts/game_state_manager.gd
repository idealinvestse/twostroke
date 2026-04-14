extends Node

## Game State Manager - Autoload singleton for global simulation state
## Manages scene transitions, pause state, and simulation control

enum SimulationState {
	MAIN_MENU,
	SIMULATION_RUNNING,
	SIMULATION_PAUSED,
	LOADING
}

# Current state
var current_state: SimulationState = SimulationState.MAIN_MENU
var current_profile: String = "am6_stock"
var current_quality: String = "medium"

# Signals
signal state_changed(new_state: SimulationState)
signal simulation_started(profile: String)
signal simulation_paused
signal simulation_resumed
signal simulation_restarted
signal return_to_menu
signal pause_requested(paused: bool)
signal restart_requested

# Scene paths
const MAIN_MENU_SCENE = "res://scenes/ui/main_menu.tscn"
const SIMULATION_SCENE = "res://scenes/main.tscn"

func _ready():
	print("GameStateManager initialized")
	# Start with main menu
	change_state(SimulationState.MAIN_MENU)

func change_state(new_state: SimulationState) -> void:
	if current_state == new_state:
		return
	
	var old_state = current_state
	current_state = new_state
	
	match new_state:
		SimulationState.MAIN_MENU:
			_load_main_menu()
		SimulationState.SIMULATION_RUNNING:
			if old_state == SimulationState.MAIN_MENU:
				_load_simulation()
			else:
				# Resuming from pause
				_set_simulation_pause(false)
		SimulationState.SIMULATION_PAUSED:
			_set_simulation_pause(true)
		SimulationState.LOADING:
			pass
	
	state_changed.emit(new_state)
	print("State changed: ", _state_to_string(new_state))

func start_simulation(profile: String, quality: String) -> void:
	current_profile = profile
	current_quality = quality
	change_state(SimulationState.SIMULATION_RUNNING)
	simulation_started.emit(profile)

func pause_simulation() -> void:
	if current_state == SimulationState.SIMULATION_RUNNING:
		change_state(SimulationState.SIMULATION_PAUSED)
		simulation_paused.emit()

func resume_simulation() -> void:
	if current_state == SimulationState.SIMULATION_PAUSED:
		change_state(SimulationState.SIMULATION_RUNNING)
		simulation_resumed.emit()

func restart_simulation() -> void:
	simulation_restarted.emit()
	# If paused, resume first
	if current_state == SimulationState.SIMULATION_PAUSED:
		change_state(SimulationState.SIMULATION_RUNNING)

func quit_to_menu() -> void:
	return_to_menu.emit()
	change_state(SimulationState.MAIN_MENU)

func _load_main_menu() -> void:
	get_tree().change_scene_to_file(MAIN_MENU_SCENE)

func _load_simulation() -> void:
	get_tree().change_scene_to_file(SIMULATION_SCENE)

func _set_simulation_pause(paused: bool) -> void:
	# Emit signal for physics bridge to handle
	pause_requested.emit(paused)

func _state_to_string(state: SimulationState) -> String:
	match state:
		SimulationState.MAIN_MENU:
			return "MAIN_MENU"
		SimulationState.SIMULATION_RUNNING:
			return "SIMULATION_RUNNING"
		SimulationState.SIMULATION_PAUSED:
			return "SIMULATION_PAUSED"
		SimulationState.LOADING:
			return "LOADING"
		_:
			return "UNKNOWN"
