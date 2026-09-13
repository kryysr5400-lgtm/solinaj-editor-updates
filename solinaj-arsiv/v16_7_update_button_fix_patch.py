# -*- coding: utf-8 -*-
import ast
import re

TARGET_VERSION = "16.7"

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sınıfı bulunamadı.")

def _replace_method(source_text, method_name, new_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [n for n in app.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name]
    if not matches:
        raise RuntimeError(f"{method_name} metodu bulunamadı.")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    return "".join(lines[:start]) + new_source.strip("\n") + "\n" + "".join(lines[end:])

def apply_update(source_text):
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', source_text)
    if not m:
        raise RuntimeError("Sürüm bilgisi bulunamadı.")
    current = m.group(1)
    if current not in ("16.4","16.5","16.6"):
        raise RuntimeError("Bu düzeltme V16.4, V16.5 veya V16.6 içindir. Mevcut: V" + current)

    new_method = '''
    def start_self_update(self):
        # V16.7: harici updater yerine dahili güvenli güncelleyici
        try:
            if bool(getattr(self, "_v167_update_busy", False)):
                return
            self._v167_update_busy = True
            self._set_update_ui("Güncelleme sunucusu kontrol ediliyor...", button_enabled=False)

            def _run():
                try:
                    self._check_update_worker()
                finally:
                    def _release():
                        try:
                            self._v167_update_busy = False
                            self.left_update_btn.configure(state="normal")
                        except Exception:
                            pass
                    try:
                        self.after(0, _release)
                    except Exception:
                        pass

            threading.Thread(target=_run, daemon=True).start()
        except Exception as e:
            self._v167_update_busy = False
            try:
                self._update_error("Güncelleme başlatılamadı", str(e))
            except Exception:
                messagebox.showerror(APP_NAME, "Güncelleme başlatılamadı.\n\n" + str(e))
'''

    source_text = _replace_method(source_text, "start_self_update", new_method)

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V16.7"',
        source_text,
        count=1
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "16.7"',
        source_text,
        count=1
    )

    compile(source_text, "<solinaj_arsivleyici_v16_7>", "exec")
    return source_text
