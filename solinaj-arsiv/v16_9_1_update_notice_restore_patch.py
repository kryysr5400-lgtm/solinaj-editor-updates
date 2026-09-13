# -*- coding: utf-8 -*-
import ast
import re

TARGET_VERSION = "16.9.1"

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sınıfı bulunamadı.")

def _replace_method(source_text, method_name, new_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [n for n in app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name]
    if not matches:
        raise RuntimeError(f"{method_name} metodu bulunamadı.")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    return "".join(lines[:target.lineno-1]) + new_source.strip("\n") + "\n" + "".join(lines[target.end_lineno:])

def apply_update(source_text):
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', source_text)
    if not m:
        raise RuntimeError("Sürüm bilgisi bulunamadı.")
    current = m.group(1)
    if current != "16.9":
        raise RuntimeError("Bu düzeltme yalnızca V16.9 içindir. Mevcut: V" + current)

    new_handle = r"""
    def _handle_update_manifest(self, manifest):
        # V16.9.1: Güncelleme sonucu tekrar görünür uyarı penceresiyle gösterilir.
        try:
            remote_ver=self._version_tuple(str(manifest["version"]))
            current_ver=self._version_tuple(APP_VERSION)

            if remote_ver <= current_ver:
                self._v168_update_busy = False
                self._set_update_ui(
                    f"Program güncel • V{APP_VERSION}",
                    button_enabled=True
                )
                try:
                    self.add_log_ui(
                        f"GÜNCELLEME: Program güncel. Yerel V{APP_VERSION} / Sunucu V{manifest['version']}"
                    )
                except Exception:
                    pass

                messagebox.showinfo(
                    APP_NAME,
                    f"Program zaten güncel.\\n\\n"
                    f"Bilgisayarındaki sürüm: V{APP_VERSION}\\n"
                    f"Sunucudaki sürüm: V{manifest['version']}"
                )
                return

            notes=str(manifest.get("notes","Yeni güncelleme hazır."))
            self._set_update_ui(
                f"Yeni sürüm bulundu: V{manifest['version']}",
                button_enabled=True
            )
            answer=messagebox.askyesno(
                APP_NAME,
                f"Yeni güncelleme bulundu!\\n\\n"
                f"Mevcut sürüm: V{APP_VERSION}\\n"
                f"Yeni sürüm: V{manifest['version']}\\n\\n"
                f"{notes}\\n\\n"
                "Şimdi indirip kuralım mı?"
            )
            if not answer:
                self._v168_update_busy = False
                self._set_update_ui("Güncelleme kullanıcı tarafından ertelendi", button_enabled=True)
                return

            self._set_update_ui(
                f"V{manifest['version']} indiriliyor...",
                button_enabled=False
            )
            self._v168_download_result = None
            self._v168_download_started = time.time()
            self._v168_download_thread = threading.Thread(
                target=lambda m=manifest: self._v168_download_worker(m),
                daemon=True
            )
            self._v168_download_thread.start()
            self.after(120, lambda m=manifest: self._v168_download_poll(m))
        except Exception as e:
            self._v168_update_busy = False
            self._update_error("Güncelleme bilgisi işlenemedi", str(e))
    """
    source_text = _replace_method(source_text, "_handle_update_manifest", new_handle)

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V16.9.1"',
        source_text, count=1
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "16.9.1"',
        source_text, count=1
    )

    compile(source_text, "<solinaj_arsivleyici_v16_9_1>", "exec")
    return source_text
