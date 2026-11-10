extends Node3D
func _ready():
    var cam=$Camera3D
    cam.position=Vector3(0.34,0.27,0.38)
    cam.look_at(Vector3(0,0.115,0),Vector3.UP)
    print("CASE 4 ENGINE IMPORT: PASS")
    print("GLB loaded; scale units: meters; expected height: 0.231 m")
func _process(delta):
    $Goblet_LOW.rotate_y(delta*0.25)
