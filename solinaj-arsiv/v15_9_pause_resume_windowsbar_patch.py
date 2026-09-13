import ast
import re

TARGET_VERSION = "15.9"

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sinifi bulunamadi.")

def _replace_app_method(source_text, method_name, new_method_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == method_name]
    if not matches:
        raise RuntimeError(f"{method_name} metodu bulunamadi.")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    indent = " " * target.col_offset
    replacement = "".join(indent + line + "\n" for line in new_method_source.strip("\n").splitlines())
    return "".join(lines[:start]) + replacement + "".join(lines[end:])

def apply_update(source_text):
    if 'class App(tk.Tk):' not in source_text:
        raise RuntimeError("Bu kurulum Solinaj Arsivleyici yapisiyla uyumlu degil.")
    if 'APP_VERSION = "15.8"' not in source_text:
        raise RuntimeError("Bu guncelleme V15.8 kurulumu icindir.")

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V15.9"',
        source_text,
        count=1
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "15.9"',
        source_text,
        count=1
    )

    start_scan_method = r"""
def start_scan(self):
    if not hasattr(self, "pause_event"):
        self.pause_event=threading.Event()

    if self.running:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.status.set("Devam ediyor...")
            self.progress_text.set(getattr(self, "_pause_progress_text", "Devam ediyor..."))
            self._set_live(action="Devam ediyor", event="TARA - kaldigi yerden devam")
            self.add_log_ui("TARA: Islem kaldigi yerden devam ediyor.")
            try:
                self._windows_bar_running=True
                self._windows_bar_ensure()
                self._windows_bar_schedule()
            except Exception:
                pass
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
    self._set_live(action="Dosyalar araniyor", done_bytes=0, total_bytes=0, speed_bps=0, event="Tarama baslatildi")

    try:
        self._windows_bar_phase=getattr(self, "_windows_bar_phase", 0.0)
        self._windows_bar_dir=getattr(self, "_windows_bar_dir", 1)
        self._windows_bar_running=True
        self._windows_bar_ensure()
        self._windows_bar_schedule()
    except Exception:
        pass

    threading.Thread(target=self.scan_worker, daemon=True).start()

def _windows_bar_ensure(self):
    if hasattr(self, "_windows_bar") and self._windows_bar.winfo_exists():
        return
    try:
        parent=self.progress
        self._windows_bar=tk.Canvas(parent,height=16,bg="#1f1f1f",highlightthickness=0,bd=0)
        self._windows_bar.place(x=0, y=0, relwidth=1, relheight=1)
        self._windows_bar.lift()
    except Exception:
        return
    self._windows_bar_draw()

def _windows_bar_draw(self):
    try:
        c=self._windows_bar
        c.update_idletasks()
        w=max(20, c.winfo_width())
        h=max(8, c.winfo_height())
        c.delete("all")
        phase=float(getattr(self, "_windows_bar_phase", 0.0))
        block=max(40, int(w*0.24))
        usable=max(1, w-block)
        x=int((phase/100.0)*usable)
        c.create_rectangle(0, 0, w, h, fill="#1f1f1f", outline="")
        c.create_rectangle(x, 1, min(w, x+block), h-1, fill="#0078D4", outline="")
        shine=max(8, int(block*0.22))
        sx=min(w, x+int(block*0.58))
        c.create_rectangle(sx, 1, min(w, sx+shine), h-1, fill="#4CC2FF", outline="")
    except Exception:
        pass

def _windows_bar_schedule(self):
    try:
        if getattr(self, "_windows_bar_job", None):
            return
        self._windows_bar_job=self.after(35, self._windows_bar_tick)
    except Exception:
        pass

def _windows_bar_tick(self):
    self._windows_bar_job=None
    try:
        if not getattr(self, "_windows_bar_running", False):
            self._windows_bar_draw()
            return
        paused=hasattr(self, "pause_event") and self.pause_event.is_set()
        if not paused:
            phase=float(getattr(self, "_windows_bar_phase", 0.0))
            direction=int(getattr(self, "_windows_bar_dir", 1))
            phase += 2.2*direction
            if phase >= 100.0:
                phase=100.0
                direction=-1
            elif phase <= 0.0:
                phase=0.0
                direction=1
            self._windows_bar_phase=phase
            self._windows_bar_dir=direction
            self._windows_bar_draw()
        if getattr(self, "_windows_bar_running", False):
            self._windows_bar_schedule()
    except Exception:
        pass

def _pause_wait(self):
    if not hasattr(self, "pause_event"):
        self.pause_event=threading.Event()
    while self.pause_event.is_set():
        if self.stop_event.is_set():
            raise RuntimeError("Program kapatiliyor")
        time.sleep(0.08)
"""

    stop_scan_method = r"""
def stop_scan(self):
    if not self.running:
        self.status.set("Hazir - calisan tarama yok")
        return
    if not hasattr(self, "pause_event"):
        self.pause_event=threading.Event()
    if self.pause_event.is_set():
        self.status.set("Zaten duraklatildi - TARA ile devam et")
        return

    self.pause_event.set()
    try:
        self._pause_progress_text=self.progress_text.get()
    except Exception:
        self._pause_progress_text="Duraklatildi"

    self.status.set("Duraklatildi - TARA ile devam et")
    self.progress_text.set("Duraklatildi")
    self._set_live(action="Duraklatildi", event="DURDUR - islem beklemede")
    self.add_log_ui("DURDUR: Islem duraklatildi. Dosya ve tarama konumu korunuyor.")
    try:
        self._windows_bar_draw()
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
            if existing > total:
                dst.unlink()
                existing=0
        except Exception:
            existing=0

    done=existing
    active_seconds=0.0
    last_tick=time.time()
    mode="ab" if existing else "wb"

    with src.open("rb") as rf, dst.open(mode) as wf:
        if existing:
            rf.seek(existing)

        while True:
            self._pause_wait()
            if self.stop_event.is_set():
                raise RuntimeError("Program kapatiliyor")

            now=time.time()
            active_seconds += max(0.0, now-last_tick)
            last_tick=now

            chunk=rf.read(512*1024)
            if not chunk:
                break
            wf.write(chunk)
            wf.flush()
            done += len(chunk)

            speed=max(0.0, (done-existing)/max(0.001, active_seconds))
            self._set_live(done_bytes=done,total_bytes=total,speed_bps=speed)

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
            self._pause_wait()
            if self.stop_event.is_set():
                return
            rp=Path(root)
            if not rp.exists():
                self.add_log_ui(f"YOK: {rp}")
                continue

            for p in rp.rglob("*"):
                self._pause_wait()
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
            self._pause_wait()
            if self.stop_event.is_set():
                return

            self._stat("Taranan")
            try:
                ext=p.suffix.lower()
                family=(ext in IMAGE_EXT and is_family(p,self.config_data.get("family_folders",[])))
                game=detect_game(p) if ext in VIDEO_EXT or (ext in IMAGE_EXT and not family) else "-"
                kind=("Video" if ext in VIDEO_EXT else ("Aile Resmi" if family else ("Oyun Resmi" if ext in IMAGE_EXT else (ext.lstrip(".").upper() or "Dosya"))))
                self._set_live(action="Dosya analiz ediliyor",file=p.name,source=str(p),target="-",game=game,kind=kind,event=f"Analiz: {p.name}")

                self._pause_wait()
                if not file_age_stable(p):
                    self.add_log_ui(f"ATLANDI (dosya yaziliyor olabilir): {p}")
                else:
                    self._pause_wait()
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

                        self.history[fingerprint]={
                            "source":str(p),
                            "target":str(dst),
                            "size":p.stat().st_size,
                            "archived_at":time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        save_history(self.history)
                        self.add_log_ui(f"KOPYALANDI: {p.name} -> {dst.parent}")
                processed_window += 1

            except Exception as e:
                if self.stop_event.is_set():
                    return
                self._stat("Hata")
                self.add_log_ui(f"HATA: {p} | {e}")

            self._pause_wait()
            self.after(0,lambda v=i,t=total:self.progress_text.set(f"{v} / {t}"))
            if i%5==0:
                self.update_graph(processed_window)
                processed_window=0

        self.update_graph(processed_window)
        self.after(0,lambda:self.status.set("Tarama tamamlandi"))
        self.after(0,lambda:self.progress_text.set(f"{total} / {total}"))
        self._set_live(action="Tarama tamamlandi",event="Tarama tamamlandi")

    finally:
        self.running=False
        try:
            self.pause_event.clear()
        except Exception:
            pass
        try:
            self._windows_bar_running=False
            self.after(0,self._windows_bar_draw)
        except Exception:
            pass
"""

    source_text=_replace_app_method(source_text,"start_scan",start_scan_method)
    source_text=_replace_app_method(source_text,"stop_scan",stop_scan_method)
    source_text=_replace_app_method(source_text,"_copy_with_progress",copy_method)
    source_text=_replace_app_method(source_text,"scan_worker",scan_method)

    compile(source_text,"<solinaj_arsivleyici_v15_9>","exec")
    return source_text
