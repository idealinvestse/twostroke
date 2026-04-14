extends Control

## Main Menu - Initial scene for selecting profile, quality, and display settings

@onready var profile_dropdown: OptionButton = $Panel/VBoxContainer/ProfileContainer/ProfileDropdown
@onready var quality_dropdown: OptionButton = $Panel/VBoxContainer/QualityContainer/QualityDropdown
@onready var resolution_dropdown: OptionButton = $Panel/VBoxContainer/DisplayContainer/ResolutionDropdown
@onready var fullscreen_check: CheckBox = $Panel/VBoxContainer/DisplayContainer/FullscreenCheck
@onready var profile_info_label: Label = $Panel/VBoxContainer/ProfileInfoLabel
@onready var start_button: Button = $Panel/VBoxContainer/StartButton

# Profile data loaded from JSON
var profiles: Dictionary = {}
var profile_keys: Array = []

# Quality presets
const QUALITY_PRESETS = [
	{"key": "simple_2d", "name": "Simple 2D", "desc": "Minimal effekt på CPU/GPU"},
	{"key": "low", "name": "Low", "desc": "Grundläggande rendering"},
	{"key": "medium", "name": "Medium", "desc": "Balanserad kvalitet"},
	{"key": "high", "name": "High", "desc": "Avancerade effekter"},
	{"key": "ultra", "name": "Ultra", "desc": "Maximal kvalitet"},
]

# Resolution options
const RESOLUTIONS = [
	Vector2i(1280, 720),
	Vector2i(1366, 768),
	Vector2i(1600, 900),
	Vector2i(1920, 1080),
]

func _ready():
	_load_profiles()
	_setup_ui()
	_update_profile_info()

func _load_profiles() -> void:
	"""Load engine profiles from the JSON file with fallback."""
	# Try multiple possible paths for the JSON file
	var possible_paths = [
		"../../engine_profiles.json",
		"res://../../engine_profiles.json",
		"../engine_profiles.json",
	]
	
	var profiles_loaded = false
	
	for json_path in possible_paths:
		var file = FileAccess.open(json_path, FileAccess.READ)
		
		if file:
			var json_string = file.get_as_text()
			file.close()
			
			var json = JSON.new()
			var error = json.parse(json_string)
			
			if error == OK:
				var data = json.data
				if data.has("profiles"):
					profiles = data["profiles"]
					profile_keys = profiles.keys()
					profile_keys.sort()
					profiles_loaded = true
					print("Loaded profiles from: ", json_path)
					break
				else:
					push_error("No 'profiles' key in engine_profiles.json")
			else:
				push_error("Failed to parse engine_profiles.json from: ", json_path)
	
	if not profiles_loaded:
		push_error("Could not load engine_profiles.json from any path")
		# Fallback: create minimal default profile
		profiles = {
			"am6_stock": {
				"name": "AM6 Stock (Fallback)",
				"B": 0.0403,
				"stroke": 0.039,
				"compression_ratio": 12.0,
				"stock_power_kw": 4.0,
				"stock_rpm_peak": 7500,
				"cooling": "liquid",
			}
		}
		profile_keys = ["am6_stock"]
		print("Using fallback profile")

func _setup_ui() -> void:
	# Populate profile dropdown
	for key in profile_keys:
		var profile = profiles.get(key, {})
		var name = profile.get("name", key)
		profile_dropdown.add_item(name)
	
	if profile_keys.size() > 0:
		profile_dropdown.select(0)
	
	profile_dropdown.item_selected.connect(_on_profile_selected)
	
	# Populate quality dropdown
	for preset in QUALITY_PRESETS:
		quality_dropdown.add_item(preset["name"])
	quality_dropdown.select(2)  # Medium default
	
	# Populate resolution dropdown
	for res in RESOLUTIONS:
		resolution_dropdown.add_item("%d x %d" % [res.x, res.y])
	
	# Set current resolution as default
	var current_size = DisplayServer.window_get_size()
	for i in range(RESOLUTIONS.size()):
		if RESOLUTIONS[i] == current_size:
			resolution_dropdown.select(i)
			break
	
	# Connect signals
	start_button.pressed.connect(_on_start_pressed)
	profile_dropdown.item_selected.connect(_on_profile_selected)
	
	# Set fullscreen checkbox
	var mode = DisplayServer.window_get_mode()
	fullscreen_check.button_pressed = (mode == DisplayServer.WINDOW_MODE_FULLSCREEN)

func _on_profile_selected(index: int) -> void:
	_update_profile_info()

func _update_profile_info() -> void:
	var selected_idx = profile_dropdown.selected
	if selected_idx < 0 or selected_idx >= profile_keys.size():
		return
	
	var key = profile_keys[selected_idx]
	var profile = profiles.get(key, {})
	
	var bore = profile.get("B", 0.04) * 1000  # mm
	var stroke = profile.get("stroke", 0.039) * 1000  # mm
	var cc = PI * pow(bore / 2, 2) * stroke / 1000
	
	var power = profile.get("stock_power_kw", 0)
	var rpm = profile.get("stock_rpm_peak", 0)
	var cooling = profile.get("cooling", "air")
	var carb = profile.get("carburetor", "")
	
	var info = "%s | %.1f×%.1fmm = %.1fcc | %.1fkW @ %d RPM | %s cooled" % [
		profile.get("name", key),
		bore, stroke, cc,
		power, rpm,
		cooling
	]
	
	if carb:
		info += " | %s" % carb
	
	profile_info_label.text = info

func _on_start_pressed() -> void:
	var profile_idx = profile_dropdown.selected
	var quality_idx = quality_dropdown.selected
	var resolution_idx = resolution_dropdown.selected
	
	if profile_idx < 0 or profile_idx >= profile_keys.size():
		profile_idx = 0
	
	var profile_key = profile_keys[profile_idx]
	var quality_key = QUALITY_PRESETS[quality_idx]["key"]
	
	# Apply display settings
	_apply_display_settings(resolution_idx, fullscreen_check.button_pressed)
	
	# Start simulation via GameStateManager
	GameStateManager.start_simulation(profile_key, quality_key)

func _apply_display_settings(resolution_idx: int, fullscreen: bool) -> void:
	var size = RESOLUTIONS[resolution_idx]
	
	if fullscreen:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		DisplayServer.window_set_size(size)
		# Center window
		var screen_size = DisplayServer.screen_get_size()
		var window_pos = (screen_size - size) / 2
		DisplayServer.window_set_position(window_pos)
