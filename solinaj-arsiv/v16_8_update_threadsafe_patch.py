# -*- coding: utf-8 -*-
import ast
import re

TARGET_VERSION = "16.8"

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

def _append_methods_to_app(source_text, methods_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    lines = source_text.splitlines(keepends=True)
    insert_line = app.end_lineno
    return "".join(lines[:insert_line]) + "\n" + methods_source.strip("\n") + "\n" + "".join(lines[insert_line:])

def apply_update(source_text):
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', source_text)
    if not m:
        raise RuntimeError("Sürüm bilgisi bulunamadı.")
    if m.group(1) != "16.7":
        raise RuntimeError("Bu düzeltme yalnızca V16.7 içindir. Mevcut: V" + m.group(1))

    start_method = '''
    def start_self_update(self):
        # V16.8: Worker thread Tkinter'a dokunmaz; ana thread sonucu poll eder.
        try:
            if bool(getattr(self, "_v168_update_busy", False)):
                return
            self._v168_update_busy = True
            self._v168_check_result = None
            self._v168_check_started = time.time()
            self._set_update_ui("Güncelleme sunucusu kontrol ediliyor...", button_enabled=False)

            self._v168_check_thread = threading.Thread(
                target=self._v168_manifest_worker,
                daemon=True
            )
            self._v168_check_thread.start()
            self.after(100, self._v168_manifest_poll)
        except Exception as e:
            self._v168_update_busy = False
            self._set_update_ui("Güncelleme başlatılamadı", button_enabled=True)
            try:
                messagebox.showerror(APP_NAME, "Güncelleme başlatılamadı.\n\n" + str(e))
            except Exception:
                pass
'''
    source_text = _replace_method(source_text, "start_self_update", start_method)

    handle_method = '''
    def _handle_update_manifest(self, manifest):
        # Bu metod yalnızca Tk ana thread'inde çalışır.
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
                return

            notes=str(manifest.get("notes","Yeni güncelleme hazır."))
            self._set_update_ui(
                f"Yeni sürüm bulundu: V{manifest['version']}",
                button_enabled=True
            )
            answer=messagebox.askyesno(
                APP_NAME,
                f"Yeni güncelleme bulundu!\n\n"
                f"Mevcut sürüm: V{APP_VERSION}\n"
                f"Yeni sürüm: V{manifest['version']}\n\n"
                f"{notes}\n\n"
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
'''
    source_text = _replace_method(source_text, "_handle_update_manifest", handle_method)

    methods = '''
    def _v168_manifest_worker(self):
        # Burada hiçbir Tkinter çağrısı yok.
        try:
            manifest=self._get_online_manifest()
            self._v168_check_result=("ok", manifest)
        except Exception as e:
            self._v168_check_result=("error", type(e).__name__, str(e))

    def _v168_manifest_poll(self):
        try:
            result=getattr(self, "_v168_check_result", None)
            if result is None:
                started=float(getattr(self, "_v168_check_started", time.time()))
                if time.time()-started > 22:
                    self._v168_update_busy=False
                    self._set_update_ui("Güncelleme kontrolü zaman aşımına uğradı", button_enabled=True)
                    return
                self.after(120, self._v168_manifest_poll)
                return

            self._v168_check_result=None
            if result[0]=="ok":
                self._handle_update_manifest(result[1])
            else:
                self._v168_update_busy=False
                self._update_error(
                    "Güncelleme kontrolü başarısız",
                    f"{result[1]}: {result[2]}"
                )
        except Exception as e:
            self._v168_update_busy=False
            self._set_update_ui("Güncelleme kontrolü başarısız", button_enabled=True)
            try:
                messagebox.showerror(APP_NAME, "Güncelleme kontrolü başarısız.\n\n"+str(e))
            except Exception:
                pass

    def _v168_download_worker(self, manifest):
        # Burada hiçbir Tkinter çağrısı yok.
        try:
            patch_raw=self._download_update_bytes(str(manifest["patch_url"]),timeout=60)

            actual=hashlib.sha256(patch_raw).hexdigest().lower()
            expected=str(manifest["patch_sha256"]).strip().lower()
            if actual != expected:
                raise ValueError("İndirilen güncellemenin SHA-256 doğrulaması başarısız.")

            patch_text=patch_raw.decode("utf-8-sig")
            patch_ns={}
            exec(compile(patch_text,"solinaj_online_patch.py","exec"),patch_ns)
            apply_update=patch_ns.get("apply_update")
            if not callable(apply_update):
                raise ValueError("Güncelleme paketi geçersiz: apply_update bulunamadı.")

            current=Path(__file__).resolve()
            source_text=current.read_text(encoding="utf-8")
            updated_text=apply_update(source_text)
            if not isinstance(updated_text,str) or len(updated_text)<1000:
                raise ValueError("Güncelleme geçersiz bir program dosyası üretti.")

            m=re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',updated_text)
            remote_ver=self._version_tuple(str(manifest["version"]))
            if not m or self._version_tuple(m.group(1)) != remote_ver:
                raise ValueError("Güncelleme sonrası sürüm bilgisi hedef sürümle eşleşmiyor.")

            compile(updated_text,"solinaj_arsivleyici.py","exec")

            staged=BASE/'solinaj_arsivleyici_UPDATE_NEW.py'
            staged.write_text(updated_text,encoding="utf-8")
            backup=BASE/'solinaj_arsivleyici_UPDATE_BACKUP.py'
            updater=BASE/'_solinaj_online_update.ps1'

            ps=[
                "$ErrorActionPreference='Stop'",
                f"$pidToWait={os.getpid()}",
                "while(Get-Process -Id $pidToWait -ErrorAction SilentlyContinue){Start-Sleep -Milliseconds 500}",
                f"Copy-Item -LiteralPath {repr(str(current))} -Destination {repr(str(backup))} -Force",
                f"Copy-Item -LiteralPath {repr(str(staged))} -Destination {repr(str(current))} -Force",
                f"Remove-Item -LiteralPath {repr(str(staged))} -Force -ErrorAction SilentlyContinue",
                "Add-Type -AssemblyName System.Windows.Forms",
                f"[System.Windows.Forms.MessageBox]::Show('V{manifest['version']} güncellemesi tamamlandı. Programı masaüstündeki Solinaj Arşiv simgesinden yeniden açın.','Solinaj Arşivleyici')|Out-Null",
                "Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue",
            ]
            updater.write_text("\r\n".join(ps)+"\r\n",encoding="utf-8-sig")
            self._v168_download_result=("ok", str(updater))
        except Exception as e:
            self._v168_download_result=("error", type(e).__name__, str(e))

    def _v168_download_poll(self, manifest):
        try:
            result=getattr(self, "_v168_download_result", None)
            if result is None:
                started=float(getattr(self, "_v168_download_started", time.time()))
                if time.time()-started > 90:
                    self._v168_update_busy=False
                    self._set_update_ui("Güncelleme indirme zaman aşımı", button_enabled=True)
                    return
                self.after(150, lambda m=manifest: self._v168_download_poll(m))
                return

            self._v168_download_result=None
            if result[0]=="ok":
                self._v168_update_busy=False
                self._confirm_install_ready(manifest, Path(result[1]))
            else:
                self._v168_update_busy=False
                self._update_error("Güncelleme indirilemedi", f"{result[1]}: {result[2]}")
        except Exception as e:
            self._v168_update_busy=False
            self._update_error("Güncelleme kuruluma hazırlanamadı", str(e))
'''
    source_text = _append_methods_to_app(source_text, methods)

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V16.8"',
        source_text,
        count=1
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "16.8"',
        source_text,
        count=1
    )

    compile(source_text, "<solinaj_arsivleyici_v16_8>", "exec")
    return source_text
