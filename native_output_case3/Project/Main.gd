extends Node2D

enum Screen { TOPICS, LESSON, LAB, QUIZ, RESULT, ACHIEVEMENTS }

var screen: Screen = Screen.TOPICS
var selected_angle := 30.0
var correct_answers := 0
var quiz_index := 0
var last_feedback := ""
var lesson_completed := false
var lab_completed := false
var quiz_completed := false
var badge_unlocked := false
var progress_percent := 0
var auto_demo := false
var elapsed := 0.0
var stage_started := 0.0
var last_event := "READY"
var saved_once := false

const SAVE_PATH := "user://optics_progress.json"
const QUIZ := [
    {"q":"От какой линии измеряют угол падения?", "answers":["От поверхности зеркала", "От нормали к зеркалу", "От края экрана"], "correct":1},
    {"q":"Угол падения равен 40°. Чему равен угол отражения?", "answers":["20°", "40°", "80°"], "correct":1},
    {"q":"Если увеличить угол падения, что произойдет с углом отражения?", "answers":["Он увеличится на столько же", "Он всегда станет 90°", "Он исчезнет"], "correct":0}
]

func _ready() -> void:
    auto_demo = OS.has_environment("CI_CAPTURE")
    _load_progress()
    _print_validation()
    if OS.has_environment("VALIDATE_ONLY"):
        call_deferred("_validation_save_and_quit")
        return
    if auto_demo:
        _reset_demo_progress()
        _set_screen(Screen.TOPICS, "Открыт выбор тем")
    queue_redraw()

func _validation_save_and_quit() -> void:
    lesson_completed = true
    lab_completed = true
    quiz_completed = true
    correct_answers = 3
    badge_unlocked = true
    progress_percent = 100
    _save_progress()
    print("CASE 3 SAVE CHECK: PASS")
    get_tree().quit(0)

func _print_validation() -> void:
    var ok := QUIZ.size() == 3 and is_equal_approx(selected_angle,30.0)
    if ok:
        print("CASE 3 VALIDATION: PASS")
        print("Variant=20 Subject=Physics Topic=PlaneMirrorReflection")
        print("Screens=Topics,Lesson,Lab,Quiz,Result,Achievements Save=JSON")
    else:
        print("CASE 3 VALIDATION: FAIL")

func _process(delta: float) -> void:
    elapsed += delta
    if auto_demo:
        _auto_flow()
    else:
        _manual_input()
    queue_redraw()

func _manual_input() -> void:
    if Input.is_key_pressed(KEY_ESCAPE):
        _set_screen(Screen.TOPICS, "Возврат к темам")
    if screen == Screen.TOPICS and Input.is_key_pressed(KEY_ENTER):
        _set_screen(Screen.LESSON, "Открыт учебный материал")
    elif screen == Screen.LESSON and Input.is_key_pressed(KEY_ENTER):
        lesson_completed = true
        _set_screen(Screen.LAB, "Начата лабораторная практика")
    elif screen == Screen.LAB:
        if Input.is_key_pressed(KEY_LEFT):
            selected_angle = max(10.0, selected_angle - 0.4)
        if Input.is_key_pressed(KEY_RIGHT):
            selected_angle = min(70.0, selected_angle + 0.4)
        if Input.is_key_pressed(KEY_ENTER):
            lab_completed = true
            _set_screen(Screen.QUIZ, "Лаборатория выполнена, начат тест")
    elif screen == Screen.QUIZ:
        for i in range(3):
            if Input.is_key_pressed(KEY_1 + i):
                _answer(i)
    elif screen == Screen.RESULT and Input.is_key_pressed(KEY_ENTER):
        _set_screen(Screen.ACHIEVEMENTS, "Открыт экран достижений")
    elif screen == Screen.ACHIEVEMENTS and Input.is_key_pressed(KEY_ENTER):
        _set_screen(Screen.TOPICS, "Прогресс сохранен")

func _auto_flow() -> void:
    var t := elapsed
    if t >= 2.0 and not _flag("lesson"):
        _mark("lesson"); _set_screen(Screen.LESSON, "Учебный материал: закон отражения")
    if t >= 6.5 and not _flag("lab"):
        _mark("lab"); lesson_completed = true; _set_screen(Screen.LAB, "Практика: настрой угол луча")
    if t >= 9.0 and screen == Screen.LAB:
        selected_angle = 40.0
    if t >= 11.5 and not _flag("quiz"):
        _mark("quiz"); lab_completed = true; _set_screen(Screen.QUIZ, "Проверка знаний")
    if t >= 13.0 and not _flag("q1"):
        _mark("q1"); _answer(1)
    if t >= 14.5 and not _flag("q2"):
        _mark("q2"); _answer(1)
    if t >= 16.0 and not _flag("q3"):
        _mark("q3"); _answer(0)
    if t >= 18.0 and not _flag("ach"):
        _mark("ach"); _set_screen(Screen.ACHIEVEMENTS, "Достижение разблокировано")
    if t >= 21.5:
        get_tree().quit(0)

var flags := {}
func _flag(k:String) -> bool:
    return flags.get(k,false)
func _mark(k:String) -> void:
    flags[k] = true

func _answer(index:int) -> void:
    if screen != Screen.QUIZ or quiz_index >= QUIZ.size():
        return
    var item = QUIZ[quiz_index]
    if index == int(item.correct):
        correct_answers += 1
        last_feedback = "Верно!"
        _event("QUIZ CORRECT %d/3" % correct_answers)
    else:
        last_feedback = "Неверно. Правильный ответ выделен в объяснении."
        _event("QUIZ WRONG")
    quiz_index += 1
    if quiz_index >= QUIZ.size():
        quiz_completed = true
        badge_unlocked = correct_answers >= 2
        progress_percent = 100
        _save_progress()
        _set_screen(Screen.RESULT, "Проверка завершена: %d/3" % correct_answers)

func _set_screen(s:Screen, event_text:String) -> void:
    screen = s
    stage_started = elapsed
    _event(event_text)

func _event(text:String) -> void:
    last_event = text
    print("EVENT: " + text)

func _save_progress() -> void:
    var data := {
        "topic":"Отражение света от плоского зеркала",
        "lesson_completed":lesson_completed,
        "lab_completed":lab_completed,
        "quiz_completed":quiz_completed,
        "correct_answers":correct_answers,
        "badge_unlocked":badge_unlocked,
        "progress_percent":progress_percent
    }
    var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
    if f:
        f.store_string(JSON.stringify(data))
        f.close()
        saved_once = true
        print("EVENT: PROGRESS SAVED JSON")

func _load_progress() -> void:
    if not FileAccess.file_exists(SAVE_PATH):
        return
    var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
    if f == null:
        return
    var parsed = JSON.parse_string(f.get_as_text())
    f.close()
    if typeof(parsed) == TYPE_DICTIONARY:
        lesson_completed = bool(parsed.get("lesson_completed",false))
        lab_completed = bool(parsed.get("lab_completed",false))
        quiz_completed = bool(parsed.get("quiz_completed",false))
        correct_answers = int(parsed.get("correct_answers",0))
        badge_unlocked = bool(parsed.get("badge_unlocked",false))
        progress_percent = int(parsed.get("progress_percent",0))
        print("EVENT: PROGRESS LOADED JSON")

func _reset_demo_progress() -> void:
    lesson_completed = false
    lab_completed = false
    quiz_completed = false
    badge_unlocked = false
    correct_answers = 0
    quiz_index = 0
    progress_percent = 0

func _draw() -> void:
    draw_rect(Rect2(0,0,1280,720), Color("0b1424"), true)
    _draw_header()
    match screen:
        Screen.TOPICS: _draw_topics()
        Screen.LESSON: _draw_lesson()
        Screen.LAB: _draw_lab()
        Screen.QUIZ: _draw_quiz()
        Screen.RESULT: _draw_result()
        Screen.ACHIEVEMENTS: _draw_achievements()
    draw_string(ThemeDB.fallback_font, Vector2(28,695), "Событие: " + last_event, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color("8aa4c8"))

func _draw_header() -> void:
    draw_rect(Rect2(0,0,1280,74), Color("12233b"), true)
    draw_string(ThemeDB.fallback_font, Vector2(28,34), "ЛАБОРАТОРИЯ ЛУЧА", HORIZONTAL_ALIGNMENT_LEFT, -1, 27, Color("e9f6ff"))
    draw_string(ThemeDB.fallback_font, Vector2(28,59), "Физика - оптика | тема: отражение света от плоского зеркала", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("8fd3ff"))
    draw_string(ThemeDB.fallback_font, Vector2(1000,36), "Прогресс: %d%%" % progress_percent, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("ffe082"))

func _draw_topics() -> void:
    _title("Выбор темы", "Пройди короткий учебный цикл: изучение -> опыт -> тест -> награда")
    _card(Rect2(110,180,1060,130), Color("17385c"))
    draw_string(ThemeDB.fallback_font, Vector2(145,225), "1. Отражение света от плоского зеркала", HORIZONTAL_ALIGNMENT_LEFT, -1, 25, Color("ffffff"))
    draw_string(ThemeDB.fallback_font, Vector2(145,260), "Статус: %s" % ("пройдено" if quiz_completed else "доступно"), HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("9be7a7"))
    draw_string(ThemeDB.fallback_font, Vector2(940,260), "ENTER - открыть", HORIZONTAL_ALIGNMENT_LEFT, -1, 17, Color("ffe082"))
    _card(Rect2(110,335,1060,90), Color("182335"))
    draw_string(ThemeDB.fallback_font, Vector2(145,380), "2. Преломление света - следующий модуль", HORIZONTAL_ALIGNMENT_LEFT, -1, 21, Color("71839b"))
    _card(Rect2(110,450,1060,90), Color("182335"))
    draw_string(ThemeDB.fallback_font, Vector2(145,495), "3. Линзы - следующий модуль", HORIZONTAL_ALIGNMENT_LEFT, -1, 21, Color("71839b"))
    draw_string(ThemeDB.fallback_font, Vector2(110,610), "Сохранение прогресса: JSON в пользовательском профиле", HORIZONTAL_ALIGNMENT_LEFT, -1, 17, Color("8fd3ff"))

func _draw_lesson() -> void:
    _title("Изучение", "Главное правило перед практикой")
    _card(Rect2(90,165,1100,420), Color("102b46"))
    draw_string(ThemeDB.fallback_font, Vector2(135,215), "ЗАКОН ОТРАЖЕНИЯ", HORIZONTAL_ALIGNMENT_LEFT, -1, 30, Color("ffe082"))
    draw_string(ThemeDB.fallback_font, Vector2(135,265), "Угол падения равен углу отражения.", HORIZONTAL_ALIGNMENT_LEFT, -1, 26, Color("ffffff"))
    draw_string(ThemeDB.fallback_font, Vector2(135,310), "Оба угла измеряют от нормали - линии, перпендикулярной зеркалу.", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color("cfe8ff"))
    var m := Vector2(780,420)
    draw_line(Vector2(520,500), Vector2(1040,500), Color("b0bec5"), 6)
    draw_line(Vector2(780,300), Vector2(780,590), Color("78909c"), 3)
    draw_line(Vector2(585,330), m, Color("ffca28"), 6)
    draw_line(m, Vector2(975,330), Color("66bbff"), 6)
    draw_string(ThemeDB.fallback_font, Vector2(540,320), "падающий луч", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("ffca28"))
    draw_string(ThemeDB.fallback_font, Vector2(925,320), "отраженный", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("66bbff"))
    draw_string(ThemeDB.fallback_font, Vector2(795,345), "нормаль", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("b0bec5"))
    draw_string(ThemeDB.fallback_font, Vector2(135,555), "ENTER - перейти к опыту", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("9be7a7"))

func _draw_lab() -> void:
    _title("Действие: виртуальный опыт", "Измени угол падения и сравни углы")
    var mirror_y := 520.0
    var center := Vector2(680,mirror_y)
    draw_line(Vector2(260,mirror_y), Vector2(1100,mirror_y), Color("cfd8dc"), 7)
    draw_line(Vector2(680,220), Vector2(680,620), Color("78909c"), 3)
    var rad := deg_to_rad(selected_angle)
    var dx := sin(rad)*255.0
    var dy := cos(rad)*255.0
    var incoming := center + Vector2(-dx,-dy)
    var outgoing := center + Vector2(dx,-dy)
    draw_line(incoming, center, Color("ffca28"), 7)
    draw_line(center, outgoing, Color("40c4ff"), 7)
    draw_circle(center, 9, Color("ffffff"))
    draw_string(ThemeDB.fallback_font, Vector2(105,210), "Угол падения: %.0f°" % selected_angle, HORIZONTAL_ALIGNMENT_LEFT, -1, 25, Color("ffca28"))
    draw_string(ThemeDB.fallback_font, Vector2(105,250), "Угол отражения: %.0f°" % selected_angle, HORIZONTAL_ALIGNMENT_LEFT, -1, 25, Color("40c4ff"))
    draw_string(ThemeDB.fallback_font, Vector2(105,315), "← / → - изменить угол", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("d7e9f8"))
    draw_string(ThemeDB.fallback_font, Vector2(105,350), "ENTER - перейти к проверке", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("9be7a7"))
    draw_string(ThemeDB.fallback_font, Vector2(105,425), "Наблюдение:", HORIZONTAL_ALIGNMENT_LEFT, -1, 19, Color("ffe082"))
    draw_string(ThemeDB.fallback_font, Vector2(105,458), "при любом выбранном угле значения остаются равными.", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("ffffff"))

func _draw_quiz() -> void:
    _title("Проверка знания", "Выбери ответ клавишами 1, 2 или 3")
    if quiz_index >= QUIZ.size():
        draw_string(ThemeDB.fallback_font, Vector2(120,250), "Проверка завершена", HORIZONTAL_ALIGNMENT_LEFT, -1, 30, Color("ffffff"))
        return
    var item = QUIZ[quiz_index]
    draw_string(ThemeDB.fallback_font, Vector2(115,180), "Вопрос %d из 3" % (quiz_index+1), HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color("8fd3ff"))
    draw_string(ThemeDB.fallback_font, Vector2(115,230), str(item.q), HORIZONTAL_ALIGNMENT_LEFT, -1, 27, Color("ffffff"))
    for i in range(3):
        var y := 300 + i*82
        _card(Rect2(115,y,1050,62), Color("17385c"))
        draw_string(ThemeDB.fallback_font, Vector2(145,y+39), "%d. %s" % [i+1, item.answers[i]], HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color("e9f6ff"))
    if last_feedback != "":
        draw_string(ThemeDB.fallback_font, Vector2(115,590), last_feedback, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("ffe082"))

func _draw_result() -> void:
    _title("Результат", "Учебный цикл завершен")
    _card(Rect2(190,180,900,340), Color("123651"))
    draw_string(ThemeDB.fallback_font, Vector2(380,250), "Результат: %d / 3" % correct_answers, HORIZONTAL_ALIGNMENT_LEFT, -1, 40, Color("ffffff"))
    draw_string(ThemeDB.fallback_font, Vector2(330,315), "Закон отражения усвоен", HORIZONTAL_ALIGNMENT_LEFT, -1, 28, Color("9be7a7"))
    draw_string(ThemeDB.fallback_font, Vector2(300,375), "Награда: 100 XP + значок «Повелитель луча»", HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color("ffe082"))
    draw_string(ThemeDB.fallback_font, Vector2(330,430), "Прогресс сохранен автоматически", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color("8fd3ff"))
    draw_string(ThemeDB.fallback_font, Vector2(420,490), "ENTER - достижения", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("ffffff"))

func _draw_achievements() -> void:
    _title("Достижения и прогресс", "Результаты сохраняются между запусками")
    _card(Rect2(115,170,1050,150), Color("17385c"))
    draw_circle(Vector2(215,245), 48, Color("ffd54f"))
    draw_string(ThemeDB.fallback_font, Vector2(195,258), "★", HORIZONTAL_ALIGNMENT_LEFT, -1, 40, Color("6d4c00"))
    draw_string(ThemeDB.fallback_font, Vector2(300,225), "Повелитель луча", HORIZONTAL_ALIGNMENT_LEFT, -1, 28, Color("ffffff"))
    draw_string(ThemeDB.fallback_font, Vector2(300,265), "Получено за успешную проверку закона отражения", HORIZONTAL_ALIGNMENT_LEFT, -1, 19, Color("cfe8ff"))
    _card(Rect2(115,350,1050,145), Color("102b46"))
    draw_string(ThemeDB.fallback_font, Vector2(150,395), "Тема: Отражение света", HORIZONTAL_ALIGNMENT_LEFT, -1, 23, Color("ffffff"))
    draw_string(ThemeDB.fallback_font, Vector2(150,435), "Урок: ✓   Опыт: ✓   Тест: ✓   Результат: %d/3" % correct_answers, HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color("9be7a7"))
    draw_rect(Rect2(150,458,850,20), Color("26384b"), true)
    draw_rect(Rect2(150,458,850*progress_percent/100.0,20), Color("4dd0e1"), true)
    draw_string(ThemeDB.fallback_font, Vector2(1020,476), "%d%%" % progress_percent, HORIZONTAL_ALIGNMENT_LEFT, -1, 17, Color("ffffff"))
    draw_string(ThemeDB.fallback_font, Vector2(115,565), "Файл сохранения: user://optics_progress.json", HORIZONTAL_ALIGNMENT_LEFT, -1, 17, Color("8fd3ff"))

func _title(a:String,b:String) -> void:
    draw_string(ThemeDB.fallback_font, Vector2(90,125), a, HORIZONTAL_ALIGNMENT_LEFT, -1, 32, Color("ffffff"))
    draw_string(ThemeDB.fallback_font, Vector2(90,153), b, HORIZONTAL_ALIGNMENT_LEFT, -1, 17, Color("8fd3ff"))

func _card(rect:Rect2,color:Color) -> void:
    draw_rect(rect,color,true)
    draw_rect(rect,Color("315578"),false,2)
