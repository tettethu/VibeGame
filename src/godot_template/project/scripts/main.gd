extends Node2D

## Starter scene for a VibeGame Godot project.
##
## Replace this script with the game entry point. Everything is drawn with
## Godot's immediate-mode CanvasItem API, so the starter needs no art assets.
## The `VibeGameBridge` autoload is available for console logging and runtime
## state reporting; see .vibegame/spec/godot/engine.md.

var clicks := 0
var time := 0.0


func _ready() -> void:
	VibeGameBridge.log_line("starter scene ready")


func _process(delta: float) -> void:
	time += delta
	queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		clicks += 1


func _draw() -> void:
	var size := get_viewport_rect().size
	draw_rect(Rect2(Vector2.ZERO, size), Color("#1c2333"))
	var center := size * 0.5
	var radius := 74.0 + sin(time * 2.0) * 8.0
	draw_circle(center, radius, Color("#ffb347"))
	draw_circle(center + Vector2(-24, -14), 8.0, Color("#1c2333"))
	draw_circle(center + Vector2(24, -14), 8.0, Color("#1c2333"))
	var project_name := str(ProjectSettings.get_setting("application/config/name", "VibeGame"))
	draw_string(
		ThemeDB.fallback_font,
		center + Vector2(-260, 150),
		"%s - click anywhere (clicks: %d)" % [project_name, clicks],
		HORIZONTAL_ALIGNMENT_CENTER,
		520,
		24,
		Color.WHITE
	)


## The bridge includes this in `vibegame play snapshot`.
func vibegame_state() -> Dictionary:
	return {
		"clicks": clicks,
		"fps": Engine.get_frames_per_second(),
		"size": {"w": get_viewport_rect().size.x, "h": get_viewport_rect().size.y},
	}
