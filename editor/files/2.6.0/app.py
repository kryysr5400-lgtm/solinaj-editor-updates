from pathlib import Path

_root = Path(__file__).resolve().parent
_parts = sorted((_root / "payload_v260").glob("app_part_*.txt"))
if not _parts:
    raise RuntimeError("SOLINAJ EDITOR V2.6.0 payload dosyalari bulunamadi.")
_source = "".join(p.read_text(encoding="utf-8") for p in _parts)
exec(compile(_source, str(_root / "app.py"), "exec"), globals(), globals())
