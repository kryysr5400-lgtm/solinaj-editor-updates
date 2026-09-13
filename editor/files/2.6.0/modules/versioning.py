
from pathlib import Path
import json

APP_NAME = "Solinaj Editor"
APP_VERSION = "2.6.0"

def _version_tuple(v):
    parts=[]
    for p in v.split("."):
        try: parts.append(int(p))
        except Exception: parts.append(0)
    return tuple(parts)

def check_local_manifest():
    manifest=Path(__file__).resolve().parent.parent/"update_manifest.json"
    if not manifest.exists():
        return {"status":"none"}
    try:
        data=json.loads(manifest.read_text(encoding="utf-8"))
        remote=str(data.get("version",APP_VERSION))
        if _version_tuple(remote)>_version_tuple(APP_VERSION):
            return {"status":"new","version":remote,"notes":data.get("notes","")}
        return {"status":"current","version":APP_VERSION}
    except Exception:
        return {"status":"none"}
