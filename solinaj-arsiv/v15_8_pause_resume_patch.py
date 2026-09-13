import ast
import re

TARGET_VERSION = "15.8"

def _replace_app_method(source_text, method_name, new_method_source):
    tree = ast.parse(source_text)
    app = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App"), None)
    if app is None:
        raise RuntimeError("App class not found")
    matches = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == method_name]
    if not matches:
        raise RuntimeError(method_name + " method not found")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    indent = " " * target.col_offset
    replacement = "".join(indent + line + "\n" for line in new_method_source.strip("\n").splitlines())
    return "".join(lines[:start]) + replacement + "".join(lines[end:])

def apply_update(source_text):
    if 'APP_VERSION = "15.7"' not in source_text:
        raise RuntimeError("This update requires V15.7")

    source_text = re.sub(r'APP_NAME\s*=\s*"Solinaj Arsivleyici V[^"]+"',
                         'APP_NAME = "Solinaj Arsivleyici V15.8"', source_text, count=1)
    source_text = re.sub(r'APP_NAME\s*=\s*"Solinaj Arşivleyici V[^"]+"',
                         'APP_NAME = "Solinaj Arşivleyici V15.8"', source_text, count=1)
    source_text = re.sub(r'APP_VERSION\s*=\s*"[^"]+"',
                         'APP_VERSION = "15.8"', source_text, count=1)

    start_method = r"""
def start_scan(self):
    if not hasattr(self, "pause_event"):
        self.pause_event=threading.Event()
    if self.running:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.status.set("Tarama devam ediyor...")
            self.progress_text.set("Devam ediyor...")
            try:
                self.progress.configure(mode="indeterminate",maximum=100)
                self.progress.start(14)
            except Exception:
                pass
            self._set_live(action="Tarama devam ediyor",event="TARA - devam")
            self.add_log_ui("TARA: Islem kaldigi yerden devam ediyor.")
        else:
            self.status.set("Tarama zaten calisiyor")
        return
    if not self.config_data.get("watch_folders"):
        messagebox.showwarning(APP_NAME, "Once Ayarlar bolumunden taranacak klasor ekleyin.")
        return
    self.stop_event.clear()
    self.pause_event.clear()
    self.running=True
    self.scan_started_at=time.time()
    self.status.set("Dosyalar araniyor...")
    self.progress_text.set("Dosyalar araniyor...")
    try:
        self.progress.stop()
        self.progress.configure(mode="indeterminate",maximum=100,value=0)
        self.progress.start(14)
    except Exception:
        pass
    self._set_live(action="Dosyalar araniyor",done_bytes=0,total_bytes=0,speed_bps=0,event="Tarama baslatildi")
    threading.Thread(target=self.scan_worker,daemon=True).start()
"""

    stop_method = r"""
def stop_scan(self):
    if not self.running:
        self.status.set("Hazir - calisan tarama yok")
        return
    if not hasattr(self, "pause_event"):
        self.pause_event=threading.Event()
    if self.pause_event.is_set():
        self.status.set("Tarama zaten duraklatildi")
        return
    self.pause_event.set()
    self.status.set("Duraklatildi - TARA ile devam et")
    self.progress_text.set("Duraklatildi")
    self._set_live(action="Duraklatildi",event="DURDUR - duraklat")
    self.add_log_ui("DURDUR: Islem duraklatildi. TARA ile kaldigi yerden devam eder.")
    try:
        self.progress.stop()
    except Exception:
        pass
"""

    copy_method = r"""
def _copy_with_progress(self,src,dst):
    if not hasattr(self, "pause_event"):
        self.pause_event=threading.Event()
    total=max(1,src.stat().st_size)
    dst.parent.mkdir(parents=True,exist_ok=True)
    existing=0
    if dst.exists():
        try:
            existing=dst.stat().st_size
            if existing>total:
                dst.unlink()
                existing=0
        except Exception:
            existing=0
    done=existing
    started=time.time()
    mode="ab" if existing else "wb"
    with src.open("rb") as rf, dst.open(mode) as wf:
        if existing:
            rf.seek(existing)
        while True:
            while self.pause_event.is_set():
                if self.stop_event.is_set():
                    raise RuntimeError("Program kapatiliyor")
                time.sleep(0.10)
            if self.stop_event.is_set():
                raise RuntimeError("Program kapatiliyor")
            chunk=rf.read(512*1024)
            if not chunk:
                break
            wf.write(chunk)
            wf.flush()
            done += len(chunk)
            elapsed=max(0.001,time.time()-started)
            self._set_live(done_bytes=done,total_bytes=total,speed_bps=max(0,(done-existing))/elapsed)
    try:
        shutil.copystat(src,dst)
    except Exception:
        pass
    self._set_live(done_bytes=total,total_bytes=total,speed_bps=0)
"""

    scan_method = r"""
def scan_worker(self):
    if not hasattr(self, "pause_event"):
        self.pause_event=threading.Event()
    try:
        files=[]
        cloud=Path(self.config_data["cloud_root"]).resolve()
        for root in self.config_data.get("watch_folders",[]):
            rp=Path(root)
            if not rp.exists():
                self.add_log_ui(f"YOK: {rp}")
                continue
            for p in rp.rglob("*"):
                while self.pause_event.is_set():
                    if self.stop_event.is_set():
                        return
                    time.sleep(0.10)
                if self.stop_event.is_set():
                    return
                if not p.is_file():
                    continue
                try:
                    if str(p.resolve()).lower().startswith(str(cloud).lower()):
                        continue
                except Exception:
                    pass
                files.append(p)

        total=len(files)
        self.after(0,lambda:self.progress_text.set(f"0 / {total}"))
        processed_window=0
        for i,p in enumerate(files,1):
            while self.pause_event.is_set():
                if self.stop_event.is_set():
                    return
                time.sleep(0.10)
            if self.stop_event.is_set():
                return
            self._stat("Taranan")
            try:
                ext=p.suffix.lower()
                family=(ext in IMAGE_EXT and is_family(p,self.config_data.get("family_folders",[])))
                game=detect_game(p) if ext in VIDEO_EXT or (ext in IMAGE_EXT and not family) else "-"
                kind=("Video" if ext in VIDEO_EXT else ("Aile Resmi" if family else ("Oyun Resmi" if ext in IMAGE_EXT else (ext.lstrip(".").upper() or "Dosya"))))
                self._set_live(action="Dosya analiz ediliyor",file=p.name,source=str(p),target="-",game=game,kind=kind,event=f"Analiz: {p.name}")
                if not file_age_stable(p):
                    self.add_log_ui(f"ATLANDI (dosya yaziliyor olabilir): {p}")
                else:
                    fingerprint=file_fingerprint(p)
                    old=self.history.get(fingerprint)
                    if old:
                        self.add_log_ui(f"DAHA ONCE ARSIVLENDI: {p}")
                    else:
                        dst=self.classify_target(p)
                        dst.parent.mkdir(parents=True,exist_ok=True)
                        if dst.exists() and dst.stat().st_size == p.stat().st_size:
                            pass
                        else:
                            if not dst.exists():
                                dst=unique_target(dst)
                            self._set_live(action="Buluta kopyalaniyor",target=str(dst),total_bytes=p.stat().st_size)
                            self._copy_with_progress(p,dst)
                            if not dst.exists() or dst.stat().st_size != p.stat().st_size:
                                raise IOError("Kopyalama dogrulamasi basarisiz")
                        self.history[fingerprint]={"source":str(p),"target":str(dst),"size":p.stat().st_size,"archived_at":time.strftime("%Y-%m-%d %H:%M:%S")}
                        save_history(self.history)
                        self.add_log_ui(f"KOPYALANDI: {p.name} -> {dst.parent}")
                processed_window += 1
            except Exception as e:
                if self.stop_event.is_set():
                    return
                self._stat("Hata")
                self.add_log_ui(f"HATA: {p} | {e}")
            self.after(0,lambda v=i,t=total:self.progress_text.set(f"{v} / {t}"))
            if i%5==0:
                self.update_graph(processed_window)
                processed_window=0
        self.update_graph(processed_window)
        self.after(0,self.progress.stop)
        self.after(0,lambda:self.status.set("Tarama tamamlandi"))
        self.after(0,lambda:self.progress_text.set(f"{total} / {total}"))
        self._set_live(action="Tarama tamamlandi",event="Tarama tamamlandi")
    finally:
        self.running=False
        try:
            self.pause_event.clear()
        except Exception:
            pass
"""

    source_text=_replace_app_method(source_text,"start_scan",start_method)
    source_text=_replace_app_method(source_text,"stop_scan",stop_method)
    source_text=_replace_app_method(source_text,"_copy_with_progress",copy_method)
    source_text=_replace_app_method(source_text,"scan_worker",scan_method)
    compile(source_text,"<solinaj_arsivleyici_v15_8>","exec")
    return source_text
