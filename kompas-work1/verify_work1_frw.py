# -*- coding: utf-8 -*-
"""Проверка нативного параметрического FRW через повторное открытие в КОМПАС."""
from pathlib import Path
import math
import sys
import pythoncom
from win32com.client import Dispatch, gencache

HERE = Path(__file__).resolve().parent
FRW = HERE / "Работа_1_параметрическая.frw"
REPORT = HERE / "verification.txt"

KOMPAS6_CONSTANTS = "{75C9F5D0-B5B8-4526-8681-9903C567D2ED}"
KOMPAS_API7 = "{69AC2981-37C0-4379-84FD-5DD2F3C0A520}"
EXPECTED = {"l1": 15.0, "l2": 55.0, "l3": 80.0, "L": 75.0}


def line_signature(draw):
    lines = draw.LineSegments
    result = []
    for i in range(lines.Count):
        try:
            s = lines.LineSegment[i]
        except Exception:
            try:
                s = lines.Item(i)
            except Exception:
                continue
        try:
            result.append((float(s.X1), float(s.Y1), float(s.X2), float(s.Y2)))
        except Exception:
            pass
    return result


def crank_endpoint(lines, target_len=15.0):
    best = None
    best_err = 1e9
    for x1, y1, x2, y2 in lines:
        length = math.hypot(x2-x1, y2-y1)
        if math.hypot(x1, y1) < 1e-3:
            err = abs(length-target_len)
            if err < best_err:
                best_err, best = err, (x2, y2)
        if math.hypot(x2, y2) < 1e-3:
            err = abs(length-target_len)
            if err < best_err:
                best_err, best = err, (x1, y1)
    if best is None or best_err > 0.1:
        raise RuntimeError("Не найден кривошип l1=15 мм с шарниром A в (0,0)")
    return best


def main():
    if not FRW.exists() or FRW.stat().st_size < 1024:
        raise RuntimeError(f"Нет корректного выходного FRW: {FRW}")

    pythoncom.CoInitialize()
    const = gencache.EnsureModule(KOMPAS6_CONSTANTS, 0, 1, 0).constants
    api7 = gencache.EnsureModule(KOMPAS_API7, 0, 1, 0)

    raw = Dispatch("KOMPAS.Application.7")
    app = api7.IApplication(
        raw._oleobj_.QueryInterface(api7.IApplication.CLSID, pythoncom.IID_IDispatch)
    )
    app.Visible = True
    app.HideMessage = const.ksHideMessageNo

    doc = app.Documents.Open(str(FRW), False, False)
    if doc is None:
        raise RuntimeError("КОМПАС не смог повторно открыть сохраненный .frw")
    doc.Active = True

    d2 = api7.IKompasDocument2D(doc)
    d21 = api7.IKompasDocument2D1(doc)
    view = d2.ViewsAndLayersManager.Views.ActiveView
    draw = api7.IDrawingContainer(view)

    report = []
    for name, expected in EXPECTED.items():
        var = d21.Variable[name]
        if var is None:
            raise RuntimeError(f"В FRW отсутствует переменная {name}")
        value = float(var.Value)
        if abs(value - expected) > 1e-6:
            raise RuntimeError(f"{name}: ожидалось {expected}, получено {value}")
        report.append(f"{name}={value:.6f}")

    fi = d21.Variable["fi"]
    if fi is None:
        raise RuntimeError("В FRW отсутствует управляющая переменная fi")

    positions = {}
    for angle in (45.0, 90.0, 135.0, 90.0):
        fi.Value = angle
        if not d21.RebuildDocument():
            raise RuntimeError(f"RebuildDocument вернул ошибку при fi={angle}")
        p = crank_endpoint(line_signature(draw), EXPECTED["l1"])
        positions.setdefault(angle, p)

    p45 = positions[45.0]
    p135 = positions[135.0]
    movement = math.hypot(p45[0]-p135[0], p45[1]-p135[1])
    if movement < 1.0:
        raise RuntimeError(
            f"fi меняется, но геометрия не перестраивается: перемещение B={movement:.6f} мм"
        )

    for angle, (x, y) in positions.items():
        ex = EXPECTED["l1"] * math.cos(math.radians(angle))
        ey = EXPECTED["l1"] * math.sin(math.radians(angle))
        if math.hypot(x-ex, y-ey) > 0.15:
            raise RuntimeError(
                f"При fi={angle} точка B=({x:.4f},{y:.4f}), "
                f"ожидалось примерно ({ex:.4f},{ey:.4f})"
            )

    doc.Save()

    report += [
        "fi=45 -> B=(%.6f, %.6f)" % positions[45.0],
        "fi=90 -> B=(%.6f, %.6f)" % positions[90.0],
        "fi=135 -> B=(%.6f, %.6f)" % positions[135.0],
        f"movement_B_45_to_135={movement:.6f} mm",
        f"file_size={FRW.stat().st_size} bytes",
        "RESULT=PASS_NATIVE_PARAMETRIC_REBUILD",
    ]
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        REPORT.write_text("RESULT=FAIL\n" + repr(exc) + "\n", encoding="utf-8")
        print("VERIFICATION FAILED:", exc, file=sys.stderr)
        raise
