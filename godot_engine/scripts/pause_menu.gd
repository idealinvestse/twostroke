extends Control

## Pause Menu - Overlay for pausing, restarting, or returning to main menu

@onready var resume_button: Button = $Panel/VBoxContainer/ResumeButton
@onready var restart_button: Button = $Panel/VBoxContainer/RestartButton
@onready var menu_button: Button = $Panel/VBoxContainer/MenuButton
@onready var quit_button: Button = $Panel/VBoxContainer/QuitButton

var is_visible: bool = false

func _ready():
	# Start hidden
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS  # Keep processing when game is paused
	
	# Connect button signals
	resume_button.pressed.connect(_on_resume_pressed)
	restart_button.pressed.connect(_on_restart_pressed)
	menu_button.pressed.connect(_on_menu_pressed)
	quit_button.pressed.connect(_on_quit_pressed)
	
	# Connect to GameStateManager signals
	GameStateManager.state_changed.connect(_on_state_changed)

func _input(event):
	# Handle ESC/P key to toggle pause
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ESCAPE or event.keycode == KEY_P:
			if GameStateManager.current_state == GameStateManager.SimulationState.SIMULATION_RUNNING:
				GameStateManager.pause_simulation()
			elif GameStateManager.current_state == GameStateManager.SimulationState.SIMULATION_PAUSED:
				GameStateManager.resume_simulation()
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_R and GameStateManager.current_state == GameStateManager.SimulationState.SIMULATION_PAUSED:
			_on_restart_pressed()
			get_viewport().set_input_as_handled()

func _on_state_changed(new_state: GameStateManager.SimulationState) -> void:
	match new_state:
		GameStateManager.SimulationState.SIMULATION_PAUSED:
			visible = true
			is_visible = true
		GameStateManager.SimulationState.SIMULATION_RUNNING:
			visible = false
			is_visible = false
		GameStateManager.SimulationState.MAIN_MENU:
			visible = false
			is_visible = false

func _on_resume_pressed() -> void:
	GameStateManager.resume_simulation()

func _on_restart_pressed() -> void:
	# Use GameStateManager signal which will notify physics bridge
	GameStateManager.restart_simulation()

func _on_menu_pressed() -> void:
	GameStateManager.quit_to_menu()

func _on_quit_pressed() -> void:
	get_tree().quit()
