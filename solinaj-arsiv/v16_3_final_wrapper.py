import ast
import urllib.request

INNER_URL = "https://raw.githubusercontent.com/kryysr5400-lgtm/solinaj-editor-updates/main/solinaj-arsiv/v16_3_force_ui_panel_patch.py"

def _fetch_inner():
    req = urllib.request.Request(
        INNER_URL,
        headers={
            "User-Agent": "Solinaj-Arsiv-V16.3",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8-sig")

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sinifi bulunamadi.")

def _replace_method(source_text, method_name, new_method_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [
        n for n in app.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name
    ]
    if not matches:
        raise RuntimeError(method_name + " metodu bulunamadi.")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    block = new_method_source.strip("\n") + "\n"
    return "".join(lines[:start]) + block + "".join(lines[end:])

def apply_update(source_text):
    code = _fetch_inner()
    ns = {}
    exec(compile(code, "v16_3_inner_patch.py", "exec"), ns)
    fn = ns.get("apply_update")
    if not callable(fn):
        raise RuntimeError("V16.3 ana yama modulu gecersiz.")

    updated = fn(source_text)

    fixed_start_update = '''    def start_self_update(self):
        try:
            self._set_update_ui("En son sürüm kontrol ediliyor...", button_enabled=False)
        except Exception:
            try:
                self.status.set("En son sürüm kontrol ediliyor...")
            except Exception:
                pass
        try:
            threading.Thread(target=self._check_update_worker, daemon=True).start()
        except Exception as e:
            try:
                messagebox.showerror(APP_NAME, "Güncelleme kontrolü başlatılamadı:\\n" + str(e))
            except Exception:
                pass
'''
    updated = _replace_method(updated, "start_self_update", fixed_start_update)
    compile(updated, "<solinaj_arsivleyici_v16_3_final>", "exec")
    return updated
