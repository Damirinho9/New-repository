# -*- coding: utf-8 -*-
"""
Генератор нативного KOMPAS Fragment (.frw) для работы 1.

Требования:
- Windows
- установленный лицензированный КОМПАС-3D 22-25
- Python 3.x той же разрядности, что и COM-сервер КОМПАС
- pip install pywin32

Важное:
Скрипт не создает "псевдо-FRW". Если KOMPAS COM недоступен, он завершается
с ошибкой. Файл .frw сохраняется самим КОМПАС-3D.

Механизм - пример из методички:
l1=15 мм, l2=55 мм, l3=80 мм, L=75 мм, n=100 об/мин.
"""

from pathlib import Path
import math
import sys
import pythoncom
from win32com.client import Dispatch, gencache

L1 = 15.0
L2 = 55.0
L3 = 80.0
BASE = 75.0
N_RPM = 100.0
FI_INITIAL = 90.0

OUT = Path(__file__).with_name("Работа_1_параметрическая.frw").resolve()

KOMPAS6_CONSTANTS = "{75C9F5D0-B5B8-4526-8681-9903C567D2ED}"
KOMPAS6_API5 = "{0422828C-F174-495E-AC5D-D31014DBBE87}"
KOMPAS_API7 = "{69AC2981-37C0-4379-84FD-5DD2F3C0A520}"


def initial_geometry(fi_deg):
    phi = math.radians(fi_deg)
    ax, ay = 0.0, 0.0
    dx, dy = BASE, 0.0
    bx, by = L1 * math.cos(phi), L1 * math.sin(phi)

    qx, qy = bx - dx, by - dy
    d = math.hypot(qx, qy)
    r = math.sqrt(d*d - L2*L2)
    tq = math.atan2(qy, qx)
    alpha = math.acos(r/d)
    theta = tq - alpha

    cx = dx + r * math.cos(theta)
    cy = r * math.sin(theta)
    ex = dx + L3 * math.cos(theta)
    ey = L3 * math.sin(theta)
    return (ax, ay), (bx, by), (cx, cy), (dx, dy), (ex, ey)


def add_constraint(api7, obj, ctype, index=0, partner=None, partner_index=0,
                   variable=None, value=None, expression=None, comment=None):
    c = api7.IDrawingObject1(obj).NewConstraint()
    c.ConstraintType = ctype
    c.Index = index
    if partner is not None:
        c.Partner = partner
        c.PartnerIndex = partner_index
    if variable is not None:
        c.Variable = variable
    if value is not None:
        c.Value = value
    if expression is not None:
        c.Expression = expression
    if comment is not None:
        c.Comment = comment
    if not c.Create():
        raise RuntimeError("Не удалось создать параметрическое ограничение")
    return c


def add_line(draw, const, p1, p2, construction=False):
    seg = draw.LineSegments.Add()
    seg.Style = const.ksCSConstruction if construction else const.ksCSNormal
    seg.X1, seg.Y1 = p1
    seg.X2, seg.Y2 = p2
    if not seg.Update():
        raise RuntimeError("Не удалось создать отрезок")
    return seg


def add_layer(view, name):
    layers = view.Layers
    layers.Add()
    layer = layers.Layer[layers.Count - 1]
    layer.Name = name
    layer.Current = True
    layer.Update()
    return layer


def make_linear_dim(api7, const, symbols, seg, name, value, offset=10.0):
    x1, y1, x2, y2 = seg.X1, seg.Y1, seg.X2, seg.Y2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length

    dim = symbols.LineDimensions.Add()
    dim.X1, dim.Y1 = x1, y1
    dim.X2, dim.Y2 = x2, y2
    dim.X3 = (x1 + x2) / 2 + nx * offset
    dim.Y3 = (y1 + y2) / 2 + ny * offset
    dim.Angle = math.degrees(math.atan2(dy, dx))
    dim.Orientation = const.ksLinDParallel
    if not dim.Update():
        raise RuntimeError("Не удалось создать линейный размер " + name)

    add_constraint(api7, dim, const.ksCMergePoints, 0, seg, 0)
    add_constraint(api7, dim, const.ksCMergePoints, 1, seg, 1)
    add_constraint(api7, dim, const.ksCFixedDim)
    add_constraint(api7, dim, const.ksCDimWithVariable,
                   variable=name, value=value, comment="Управляющий размер " + name)
    return dim


def make_angle_dim(api7, const, symbols, base_line, crank, value):
    dim = symbols.AngleDimensions.Add(const.ksDrADimension)
    dim.BaseObject1 = base_line
    dim.BaseObject2 = crank
    dim.Radius = 22.0
    dim.Direction = False
    if not dim.Update():
        raise RuntimeError("Не удалось создать угловой размер fi")
    add_constraint(api7, dim, const.ksCFixedDim)
    add_constraint(api7, dim, const.ksCDimWithVariable,
                   variable="fi", value=value, comment="Угол поворота кривошипа")
    return dim


def read_endpoint(seg, idx):
    if idx == 0:
        return float(seg.X1), float(seg.Y1)
    return float(seg.X2), float(seg.Y2)


def main():
    pythoncom.CoInitialize()

    const = gencache.EnsureModule(KOMPAS6_CONSTANTS, 0, 1, 0).constants
    api5 = gencache.EnsureModule(KOMPAS6_API5, 0, 1, 0)
    api7 = gencache.EnsureModule(KOMPAS_API7, 0, 1, 0)

    raw7 = Dispatch("KOMPAS.Application.7")
    app7 = api7.IApplication(
        raw7._oleobj_.QueryInterface(api7.IApplication.CLSID, pythoncom.IID_IDispatch)
    )
    app7.Visible = True
    app7.HideMessage = const.ksHideMessageNo

    raw5 = Dispatch("Kompas.Application.5")
    kompas5 = api5.KompasObject(
        raw5._oleobj_.QueryInterface(api5.KompasObject.CLSID, pythoncom.IID_IDispatch)
    )

    doc_type = getattr(const, "ksDocumentFragment", 2)
    doc = app7.Documents.Add(doc_type, True)
    doc.Active = True

    doc2d = api7.IKompasDocument2D(doc)
    doc2d1 = api7.IKompasDocument2D1(doc)
    doc2d1.ParametricMode = True

    manager = doc2d.ViewsAndLayersManager
    view = manager.Views.ActiveView
    draw = api7.IDrawingContainer(view)
    symbols = api7.ISymbols2DContainer(view)

    add_layer(view, "Контуры")

    A, B, C, D, E = initial_geometry(FI_INITIAL)

    crank = add_line(draw, const, A, B)
    coupler = add_line(draw, const, B, C)
    rocker = add_line(draw, const, D, E)

    add_constraint(api7, crank, const.ksCFixedPoint, 0)
    add_constraint(api7, coupler, const.ksCMergePoints, 0, crank, 1)
    add_constraint(api7, coupler, const.ksCPointOnCurve, 1, rocker, 0)
    add_constraint(api7, coupler, const.ksCPerpendicular, 0, rocker, 0)
    add_constraint(api7, crank, const.ksCHAlignPoints, 0, rocker, 0)

    add_layer(view, "Вспомогательные построения")
    base_line = add_line(draw, const, A, D, construction=True)
    add_constraint(api7, base_line, const.ksCMergePoints, 0, crank, 0)
    add_constraint(api7, base_line, const.ksCMergePoints, 1, rocker, 0)

    add_layer(view, "Размеры")
    make_linear_dim(api7, const, symbols, crank, "l1", L1, 10.0)
    make_linear_dim(api7, const, symbols, coupler, "l2", L2, 10.0)
    make_linear_dim(api7, const, symbols, rocker, "l3", L3, 10.0)
    make_linear_dim(api7, const, symbols, base_line, "L", BASE, -12.0)
    make_angle_dim(api7, const, symbols, base_line, crank, FI_INITIAL)

    if not doc2d1.RebuildDocument():
        raise RuntimeError("Первая перестройка модели завершилась ошибкой")

    fi_var = doc2d1.Variable["fi"]
    test = []
    for value in (60.0, 120.0, 90.0):
        fi_var.Value = value
        if not doc2d1.RebuildDocument():
            raise RuntimeError(f"Не удалось перестроить модель при fi={value}")
        test.append((value, read_endpoint(crank, 1)))

    if math.hypot(test[0][1][0] - test[1][1][0], test[0][1][1] - test[1][1][1]) < 1e-3:
        raise RuntimeError("Проверка провалена: при изменении fi кривошип не перестроился")

    fi_var.Value = FI_INITIAL
    if not doc2d1.RebuildDocument():
        raise RuntimeError("Не удалось вернуть fi=90")

    add_layer(view, "Исследование")
    doc2d1.ParametricMode = False

    d2 = kompas5.ActiveDocument2D()
    if d2 is None:
        raise RuntimeError("API5 не получил активный 2D документ")

    samples = []
    for value in [0.001] + list(range(10, 360, 10)):
        fi_var.Value = float(value)
        if not doc2d1.RebuildDocument():
            raise RuntimeError(f"Не удалось получить положение fi={value}")
        samples.append((float(coupler.X2), float(coupler.Y2)))

    fi_var.Value = FI_INITIAL
    doc2d1.RebuildDocument()

    d2.ksBezier(1, const.ksCSNormal)
    for x, y in samples:
        bp = kompas5.GetParamStruct(const.ko_BezierPointParam)
        bp.Init()
        bp.x = x
        bp.y = y
        try:
            bp.ang = 0.0
        except Exception:
            pass
        d2.ksBezierPoint(bp)
    traj_ref = d2.ksEndObj()
    if not traj_ref:
        raise RuntimeError("Не удалось создать замкнутую траекторию Безье")

    r_min = math.sqrt((BASE - L1)**2 - L2**2)
    r_max = math.sqrt((BASE + L1)**2 - L2**2)
    d2.ksCircle(BASE, 0.0, r_min, const.ksCSConstruction)
    d2.ksCircle(BASE, 0.0, r_max, const.ksCSConstruction)

    def theta_for(deg):
        A0, B0, C0, D0, E0 = initial_geometry(deg)
        return math.atan2(C0[1] - D0[1], C0[0] - D0[0])

    vals = []
    prev = None
    offset = 0.0
    for deg in [i/20.0 for i in range(1, 7200)]:
        th = theta_for(deg)
        if prev is not None:
            diff = th + offset - prev
            if diff > math.pi:
                offset -= 2*math.pi
            elif diff < -math.pi:
                offset += 2*math.pi
        unwrapped = th + offset
        vals.append((deg, unwrapped))
        prev = unwrapped

    th_min = min(vals, key=lambda z: z[1])[1]
    th_max = max(vals, key=lambda z: z[1])[1]
    for th in (th_min, th_max):
        d2.ksLineSeg(BASE, 0.0,
                     BASE + L3*math.cos(th),
                     L3*math.sin(th),
                     const.ksCSConstruction)

    graph_x0, graph_y0 = 130.0, 0.0
    sx, sy = 0.25, 1.0
    d2.ksLineSeg(graph_x0, graph_y0, graph_x0 + 90.0, graph_y0, const.ksCSConstruction)
    d2.ksLineSeg(graph_x0, graph_y0, graph_x0, graph_y0 + 55.0, const.ksCSConstruction)
    graph_pts = []
    for deg in range(0, 361, 5):
        r = math.sqrt(BASE*BASE + L1*L1 - 2*BASE*L1*math.cos(math.radians(deg)) - L2*L2)
        xrel = r - r_min
        graph_pts.append((graph_x0 + deg*sx, graph_y0 + xrel*sy))
    for p1, p2 in zip(graph_pts, graph_pts[1:]):
        d2.ksLineSeg(p1[0], p1[1], p2[0], p2[1], const.ksCSNormal)

    omega = 2*math.pi*N_RPM/60.0
    graph_vx0, graph_vy0 = 130.0, -80.0
    st, sv = 140.0, 0.12
    period = 60.0/N_RPM
    d2.ksLineSeg(graph_vx0, graph_vy0, graph_vx0 + period*st, graph_vy0, const.ksCSConstruction)
    d2.ksLineSeg(graph_vx0, graph_vy0-35.0, graph_vx0, graph_vy0+35.0, const.ksCSConstruction)
    vel_pts = []
    for deg in range(0, 361, 5):
        ph = math.radians(deg)
        r = math.sqrt(BASE*BASE + L1*L1 - 2*BASE*L1*math.cos(ph) - L2*L2)
        v = (BASE*L1*math.sin(ph)/r)*omega
        t = deg/360.0*period
        vel_pts.append((graph_vx0 + t*st, graph_vy0 + v*sv))
    for p1, p2 in zip(vel_pts, vel_pts[1:]):
        d2.ksLineSeg(p1[0], p1[1], p2[0], p2[1], const.ksCSNormal)

    doc2d1.ParametricMode = True

    for value in (45.0, 135.0, 90.0):
        fi_var.Value = value
        if not doc2d1.RebuildDocument():
            raise RuntimeError(f"Финальный тест не прошел при fi={value}")
    fi_var.Value = FI_INITIAL
    doc2d1.RebuildDocument()

    if OUT.exists():
        OUT.unlink()
    doc.SaveAs(str(OUT))
    if not OUT.exists():
        raise RuntimeError("КОМПАС не создал итоговый .frw")
    print("OK")
    print("Создан:", OUT)
    print("Тест fi:", test)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ОШИБКА:", exc, file=sys.stderr)
        sys.exit(1)
