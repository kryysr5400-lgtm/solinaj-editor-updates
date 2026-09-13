import urllib.request

INNER_URL = "https://raw.githubusercontent.com/kryysr5400-lgtm/solinaj-editor-updates/main/solinaj-arsiv/v16_2_windows_transfer_panel_patch.py"

def apply_update(source_text):
    req = urllib.request.Request(INNER_URL, headers={"User-Agent": "Solinaj-Arsivleyici-V16.2"})
    with urllib.request.urlopen(req, timeout=30) as r:
        code = r.read().decode("utf-8-sig")
    ns = {}
    exec(compile(code, "v16_2_inner_patch.py", "exec"), ns)
    fn = ns.get("apply_update")
    if not callable(fn):
        raise RuntimeError("V16.2 ana güncelleme modülü geçersiz.")
    return fn(source_text)
