from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()
path=root/"multisimforge"/"sim.py"
text=path.read_text(encoding="utf-8")
old='''    raw = com.call({"op": "analyze", "ms14": str(probe_file), "analyses": analyses})
    by_output = {v: k for k, v in outputs.items()}
    result = {"outputs": outputs}
'''
new='''    raw = com.call({"op": "analyze", "ms14": str(probe_file), "analyses": analyses})
    by_output = {v: k for k, v in outputs.items()}
    native_analyses = []
    for native in raw.get("results", []):
        item = {
            "type": native.get("type"),
            "missing": native.get("missing", []),
            "last_error": native.get("last_error", ""),
        }
        if native.get("type") == "tran":
            ends = []
            counts = []
            for rows in (native.get("data") or {}).values():
                if rows and len(rows) > 0 and rows[0]:
                    ends.append(rows[0][-1])
                    counts.append(len(rows[0]))
            item["last_time_s"] = max(ends) if ends else None
            item["points"] = max(counts) if counts else 0
        native_analyses.append(item)
    result = {"outputs": outputs, "native_analyses": native_analyses}
'''
if old not in text:
    raise SystemExit("Expected sim.py block not found")
path.write_text(text.replace(old,new,1),encoding="utf-8")
print("patched", path)
