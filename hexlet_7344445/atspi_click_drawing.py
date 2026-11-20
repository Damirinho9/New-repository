#!/usr/bin/env python3
import sys, time
import pyatspi

TARGET = "Чертеж"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/atspi-tree.txt"

def state_names(obj):
    try:
        st=obj.getState()
        names=[]
        for s in (pyatspi.STATE_SHOWING, pyatspi.STATE_VISIBLE, pyatspi.STATE_ENABLED, pyatspi.STATE_FOCUSABLE, pyatspi.STATE_FOCUSED):
            if st.contains(s):
                names.append(str(s))
        return ",".join(names)
    except Exception:
        return ""

def action_names(obj):
    try:
        a=obj.queryAction()
        return [a.getName(i) for i in range(a.nActions)]
    except Exception:
        return []

def extents(obj):
    try:
        c=obj.queryComponent()
        e=c.getExtents(pyatspi.DESKTOP_COORDS)
        return (e.x,e.y,e.width,e.height)
    except Exception:
        return None

def walk(obj, depth=0, rows=None, candidates=None):
    if rows is None: rows=[]
    if candidates is None: candidates=[]
    try:
        name=(obj.name or "").strip()
    except Exception:
        name=""
    try:
        role=obj.getRoleName()
    except Exception:
        role="?"
    acts=action_names(obj)
    ex=extents(obj)
    if name or acts:
        rows.append((depth,role,name,acts,ex,state_names(obj)))
    if name == TARGET:
        candidates.append(obj)
    try:
        n=obj.childCount
    except Exception:
        n=0
    if depth < 12:
        for i in range(n):
            try:
                child=obj.getChildAtIndex(i)
                if child is not None:
                    walk(child, depth+1, rows, candidates)
            except Exception:
                pass
    return rows,candidates

desktop=pyatspi.Registry.getDesktop(0)

def subtree_has_kompas(obj, depth=0):
    if depth > 6:
        return False
    try:
        nm=(obj.name or "")
    except Exception:
        nm=""
    if "КОМПАС" in nm or "KOMPAS" in nm.upper():
        return True
    try:
        n=obj.childCount
    except Exception:
        n=0
    for i in range(n):
        try:
            ch=obj.getChildAtIndex(i)
            if ch is not None and subtree_has_kompas(ch, depth+1):
                return True
        except Exception:
            pass
    return False

app=None
deadline=time.time()+45
while time.time()<deadline and app is None:
    print("ATSPI_DESKTOP_CHILDREN", desktop.childCount)
    for i in range(desktop.childCount):
        try:
            a=desktop.getChildAtIndex(i)
            print("DESKTOP_CHILD",i,"name=",repr(a.name),"role=",a.getRoleName())
            if subtree_has_kompas(a):
                app=a; break
        except Exception as exc:
            print("DESKTOP_CHILD_ERROR",i,repr(exc))
    if app is None:
        time.sleep(2)

if app is None:
    print("ATSPI_APP_NOT_FOUND")
    sys.exit(20)

print("ATSPI_APP_FOUND", repr(app.name))
rows,candidates=walk(app)
with open(OUT,"w",encoding="utf-8") as f:
    for depth,role,name,acts,ex,states in rows:
        f.write(f"{'  '*depth}{role} | {name!r} | actions={acts!r} | extents={ex!r} | states={states}\n")

print("ATSPI_TREE_ROWS", len(rows))
print("DRAWING_CANDIDATES", len(candidates))
for idx,obj in enumerate(candidates):
    try: role=obj.getRoleName()
    except: role="?"
    acts=action_names(obj)
    ex=extents(obj)
    print("CANDIDATE",idx,"role=",role,"actions=",acts,"extents=",ex,"states=",state_names(obj))

chosen=None
for obj in candidates:
    acts=action_names(obj)
    ex=extents(obj)
    try:
        st=obj.getState()
        showing=st.contains(pyatspi.STATE_SHOWING)
        enabled=st.contains(pyatspi.STATE_ENABLED)
    except Exception:
        showing=enabled=True
    if showing and enabled and acts and ex and ex[2]>0 and ex[3]>0:
        chosen=obj
        break
if chosen is None:
    print("ATSPI_DRAWING_ACTIONABLE_NOT_FOUND")
    sys.exit(21)

a=chosen.queryAction()
names=[a.getName(i) for i in range(a.nActions)]
preferred=None
for want in ("click","press","activate","open"):
    for i,n in enumerate(names):
        if (n or "").lower()==want:
            preferred=i; break
    if preferred is not None: break
if preferred is None:
    preferred=0

print("ATSPI_DO_ACTION", preferred, names[preferred] if names else "")
ok=a.doAction(preferred)
print("ATSPI_ACTION_RESULT", ok)
if not ok:
    sys.exit(22)
time.sleep(12)
print("RESULT=ATSPI_DRAWING_ACTION_EXECUTED")
