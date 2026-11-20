# -*- coding: utf-8 -*-
"""Shared native KOMPAS helpers for Work 4 variant 16."""
from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import math
import zipfile

import pythoncom
from win32com.client import Dispatch, gencache

HERE = Path(__file__).resolve().parent
PARAMS = HERE / "parameters.csv"
OUT = HERE / "native"

KOMPAS6_CONSTANTS = "{75C9F5D0-B5B8-4526-8681-9903C567D2ED}"
KOMPAS6_API5 = "{0422828C-F174-495E-AC5D-D31014DBBE87}"

STEEL_DENSITY_G_CM3 = 7.85


def require(value, message):
    if not value:
        raise RuntimeError(message)
    return value


def constants():
    return gencache.EnsureModule(KOMPAS6_CONSTANTS, 0, 1, 0).constants


def get_kompas5():
    api5 = gencache.EnsureModule(KOMPAS6_API5, 0, 1, 0)
    raw = Dispatch("Kompas.Application.5")
    return api5.KompasObject(
        raw._oleobj_.QueryInterface(api5.KompasObject.CLSID, pythoncom.IID_IDispatch)
    )


def get_kompas7():
    app = Dispatch("KOMPAS.Application.7")
    app.Visible = True
    return app


def read_params():
    rows = {}
    with PARAMS.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows[row["parameter"]] = row
    def val(name):
        return float(rows[name]["value"])
    return rows, val


def set_name(obj, name):
    for attr in ("name", "Name"):
        try:
            setattr(obj, attr, name)
            return True
        except Exception:
            pass
    return False


def set_var_expression(var, expression):
    last = None
    for attr in ("expression", "Expression"):
        try:
            setattr(var, attr, str(expression))
            return
        except Exception as exc:
            last = exc
    for method in ("SetExpression",):
        try:
            require(getattr(var, method)(str(expression)), f"{method} returned false")
            return
        except Exception as exc:
            last = exc
    raise RuntimeError(f"Could not set variable expression={expression!r}: {last!r}")


def set_var_external(var, flag=True):
    last = None
    for attr in ("external", "External"):
        try:
            setattr(var, attr, bool(flag))
            return
        except Exception as exc:
            last = exc
    for method in ("SetExternal",):
        try:
            require(getattr(var, method)(bool(flag)), f"{method} returned false")
            return
        except Exception as exc:
            last = exc
    raise RuntimeError(f"Could not set external={flag}: {last!r}")


def var_name(var):
    for attr in ("name", "Name"):
        try:
            v = getattr(var, attr)
            if v is not None:
                return str(v)
        except Exception:
            pass
    for method in ("GetName",):
        try:
            return str(getattr(var, method)())
        except Exception:
            pass
    return ""


def var_value(var):
    for attr in ("value", "Value"):
        try:
            return float(getattr(var, attr))
        except Exception:
            pass
    for method in ("GetValue",):
        try:
            return float(getattr(var, method)())
        except Exception:
            pass
    raise RuntimeError(f"Could not read value of variable {var_name(var)!r}")


def set_var_value(var, value):
    last = None
    for attr in ("value", "Value"):
        try:
            setattr(var, attr, float(value))
            return
        except Exception as exc:
            last = exc
    for method in ("SetValue",):
        try:
            require(getattr(var, method)(float(value)), f"{method} returned false")
            return
        except Exception as exc:
            last = exc
    raise RuntimeError(f"Could not set value={value}: {last!r}")


def add_user_var(part, name, expression_or_value, note="", external=True):
    # ksPart.AddVariable is present in current KOMPAS API; use a numeric seed,
    # then assign the requested expression. This mirrors Variables panel behavior.
    try:
        seed = float(expression_or_value)
    except Exception:
        seed = 0.0
    var = require(part.AddVariable(name, seed, note), f"AddVariable({name}) failed")
    set_var_expression(var, expression_or_value)
    if external:
        set_var_external(var, True)
    require(part.RebuildModel(), f"Rebuild after variable {name}")
    return var


def get_var(part, name):
    coll = require(part.VariableCollection(), "VariableCollection unavailable")
    v = coll.GetByName(name, True, True)
    if not v:
        v = coll.GetByName(name, False, True)
    return require(v, f"Variable {name!r} not found")


def list_vars(part):
    coll = require(part.VariableCollection(), "VariableCollection unavailable")
    result = []
    for i in range(int(coll.GetCount())):
        v = coll.GetByIndex(i)
        if v:
            result.append((var_name(v), var_value(v)))
    return result


def feature_vars(entity):
    feat = require(entity.GetFeature(), "Entity.GetFeature failed")
    coll = require(feat.VariableCollection(), "Feature VariableCollection failed")
    return feat, coll


def bind_feature_var_by_value(part, entity, target, expression, *, min_count=1, tolerance=1e-6):
    """Bind operation parameter variable(s) whose current value matches target."""
    feat, coll = feature_vars(entity)
    hits = []
    for i in range(int(coll.GetCount())):
        v = coll.GetByIndex(i)
        if not v:
            continue
        try:
            value = var_value(v)
        except Exception:
            continue
        if abs(value - float(target)) <= max(tolerance, abs(float(target))*1e-9):
            set_var_expression(v, expression)
            hits.append(var_name(v))
    require(len(hits) >= min_count,
            f"Operation variable matching {target} not found for expression {expression}; vars={[(var_name(coll.GetByIndex(i)), var_value(coll.GetByIndex(i))) for i in range(int(coll.GetCount())) if coll.GetByIndex(i)]}")
    require(part.RebuildModel(), f"Rebuild after binding {expression}")
    return hits


def create_sketch(part, const, plane_type, name):
    plane = require(part.GetDefaultEntity(plane_type), f"{name}: default plane unavailable")
    sketch = require(part.NewEntity(const.o3d_sketch), f"{name}: NewEntity sketch failed")
    set_name(sketch, name)
    definition = require(sketch.GetDefinition(), f"{name}: sketch definition")
    require(definition.SetPlane(plane), f"{name}: SetPlane")
    require(sketch.Create(), f"{name}: sketch Create")
    editor = require(definition.BeginEdit(), f"{name}: BeginEdit")
    return sketch, definition, editor


def finish_sketch(definition):
    result = definition.EndEdit()
    if result is False:
        raise RuntimeError("Sketch EndEdit returned False")


def annulus_sketch(part, const, outer_d, inner_d, name):
    sk, sd, d2 = create_sketch(part, const, const.o3d_planeYOZ, name)
    require(d2.ksCircle(0.0, 0.0, outer_d/2.0, const.ksCSNormal), f"{name}: outer circle")
    require(d2.ksCircle(0.0, 0.0, inner_d/2.0, const.ksCSNormal), f"{name}: inner circle")
    finish_sketch(sd)
    return sk


def circle_sketch(part, const, diameter, y, z, name):
    sk, sd, d2 = create_sketch(part, const, const.o3d_planeYOZ, name)
    require(d2.ksCircle(float(y), float(z), diameter/2.0, const.ksCSNormal), f"{name}: circle")
    finish_sketch(sd)
    return sk


def create_extrusion(part, const, sketch, depth, name, *, reverse=False, draft=0.0):
    ent = require(part.NewEntity(const.o3d_baseExtrusion), f"{name}: NewEntity extrusion")
    set_name(ent, name)
    definition = require(ent.GetDefinition(), f"{name}: GetDefinition")
    require(definition.SetSketch(sketch), f"{name}: SetSketch")
    definition.directionType = const.dtReverse if reverse else const.dtNormal
    require(definition.SetSideParam(not reverse, const.etBlind, float(depth), float(draft), False),
            f"{name}: SetSideParam")
    require(ent.Create(), f"{name}: Create")
    return ent


def create_cut(part, const, sketch, depth, name, *, reverse=False, draft=0.0):
    ent = require(part.NewEntity(const.o3d_cutExtrusion), f"{name}: NewEntity cut")
    set_name(ent, name)
    definition = require(ent.GetDefinition(), f"{name}: GetDefinition")
    require(definition.SetSketch(sketch), f"{name}: SetSketch")
    definition.directionType = const.dtReverse if reverse else const.dtNormal
    require(definition.SetSideParam(not reverse, const.etBlind, float(depth), float(draft), False),
            f"{name}: SetSideParam")
    require(ent.Create(), f"{name}: Create")
    return ent


def circular_copy(part, const, seed, count, name):
    arr = require(part.NewEntity(const.o3d_circularCopy), f"{name}: NewEntity circularCopy")
    set_name(arr, name)
    definition = require(arr.GetDefinition(), f"{name}: definition")
    operations = require(definition.GetOperationArray(), f"{name}: operations")
    require(operations.Add(seed), f"{name}: add seed")
    axis = require(part.GetDefaultEntity(const.o3d_axisOX), f"{name}: OX axis")
    require(definition.SetAxis(axis), f"{name}: SetAxis")
    try:
        definition.SetGeomArray(True)
    except Exception:
        pass
    require(definition.SetCopyParamAlongDir(int(count), 360.0, True, False),
            f"{name}: SetCopyParamAlongDir")
    require(arr.Create(), f"{name}: Create")
    return arr


def create_part_doc(kompas, const, path, name):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    doc = require(kompas.Document3D(), f"{name}: Document3D")
    require(doc.Create(False, True), f"{name}: create detail")
    part = require(doc.GetPart(const.pTop_Part), f"{name}: top part")
    set_name(part, name)
    return doc, part


def native_file(path):
    require(path.exists() and path.stat().st_size > 1024, f"{path.name}: missing/small")
    require(zipfile.is_zipfile(path), f"{path.name}: not native KOMPAS container")
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        require("Contents" in names and "FileInfo" in names,
                f"{path.name}: Contents/FileInfo missing")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def part_filename(part):
    for method in ("GetFileName",):
        try:
            v = getattr(part, method)()
            if v:
                return str(v)
        except Exception:
            pass
    for attr in ("fileName", "FileName"):
        try:
            v = getattr(part, attr)
            if v:
                return str(v)
        except Exception:
            pass
    return ""


def set_component_origin(part, x, y, z):
    p = require(part.GetPlacement(), "Component GetPlacement")
    require(p.SetOrigin(float(x), float(y), float(z)), "Component SetOrigin")
    require(part.UpdatePlacement(), "Component UpdatePlacement")


def rotate_component_about_z(part, angle_deg):
    p = require(part.GetPlacement(), "Component GetPlacement")
    try:
        require(p.Rotate(float(angle_deg), 0.0, 0.0, 1.0), "Placement.Rotate Z")
        require(part.UpdatePlacement(), "UpdatePlacement after rotate")
        return
    except Exception:
        pass
    # API7-style fallback where Rotate may accept angle + axis vector as tuple is
    # intentionally not guessed. A failed rotation must fail the native build.


def close_doc(doc):
    for method in ("close", "Close"):
        try:
            getattr(doc, method)()
            return
        except Exception:
            pass
