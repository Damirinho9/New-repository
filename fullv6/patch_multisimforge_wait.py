from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()
path=root/"multisimforge"/"com.py"
text=path.read_text(encoding="utf-8")
old='''        data, pending = _collect(c, names, float(a.get("timeout", 120)))
        if a["type"] == "tran" and c.SimulationState:
            c.StopSimulation()
        pending += [n for n in wanted if n not in outputs]
        results.append({"type": a["type"], "data": data, "missing": pending,
                        "last_error": _clean(c.LastErrorMessage) if pending else ""})
'''
new='''        if a["type"] == "tran":
            # OutputReady becomes true as soon as initial samples exist; it does NOT
            # mean the requested transient duration has completed. Wait for the
            # native Multisim simulation state to become idle before reading data.
            deadline = time.time() + float(a.get("timeout", 120))
            while c.SimulationState and time.time() < deadline:
                time.sleep(0.05)
            if c.SimulationState:
                c.StopSimulation()
                raise RuntimeError(
                    f"Transient did not finish requested {a.get('time')} s within "
                    f"{a.get('timeout', 120)} s; LastError={_clean(c.LastErrorMessage)}"
                )
            data, pending = _collect(c, names, 10.0)
        else:
            data, pending = _collect(c, names, float(a.get("timeout", 120)))
        pending += [n for n in wanted if n not in outputs]
        results.append({"type": a["type"], "data": data, "missing": pending,
                        "last_error": _clean(c.LastErrorMessage)})
'''
if old not in text:
    raise SystemExit("Expected MultisimForge _analyze block not found; refusing blind patch")
path.write_text(text.replace(old,new,1),encoding="utf-8")
print(path)
print("patched full-duration transient wait")
