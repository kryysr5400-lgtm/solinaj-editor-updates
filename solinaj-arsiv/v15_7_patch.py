import ast
import re

TARGET_VERSION = "15.7"

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sınıfı bulunamadı.")

def _replace_app_method(source_text, method_name, new_method_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == method_name]
    if not matches:
        raise RuntimeError(f"{method_name} metodu bulunamadı.")
    target = matches[-1]  # Python'da son tanım etkindir.
    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    indent = " " * target.col_offset
    replacement = "".join(indent + line + "\n" for line in new_method_source.strip("\n").splitlines())
    return "".join(lines[:start]) + replacement + "".join(lines[end:])

def _patch_ui(source_text):
    # DURDUR düğmesini nesne olarak sakla ki aktif/pasif durumu yönetilebilsin.
    old = 'ttk.Button(controls,text="■  DURDUR",command=self.stop_scan,style="Danger.TButton").pack(side="left",padx=8)'
    new = 'self.stop_btn=ttk.Button(controls,text="■  DURDUR",command=self.stop_scan,style="Danger.TButton")\n        self.stop_btn.pack(side="left",padx=8)'
    if old in source_text:
        source_text = source_text.replace(old, new, 1)

    # Güncelleme sayfasına Windows tarzı hareketli bar ekle.
    anchor = 'self.left_update_btn.pack(anchor="w",padx=24,pady=(8,4))'
    if anchor in source_text and 'self.update_progress=ttk.Progressbar' not in source_text:
        insert = anchor + '\n                self.update_progress=ttk.Progressbar(pg,mode="indeterminate",maximum=100,style="Neon.Horizontal.TProgressbar")\n                self.update_progress.pack(fill="x",padx=24,pady=(4,8),ipady=4)'
        source_text = source_text.replace(anchor, insert, 1)
    return source_text

def apply_update(source_text):
    if 'class App(tk.Tk):' not in source_text:
        raise RuntimeError("Bu kurulum Solinaj Arşivleyici yapısıyla uyumlu değil.")

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Arşivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V15.7"',
        source_text,
        count=1
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "15.7"',
        source_text,
        count=1
    )
    source_text = _patch_ui(source_text)

    start_scan_method = r"""
def start_scan(self):
    if self.running:
        self.status.set("Tarama zaten çalışıyor")
        return
    if not self.config_data.get("watch_folders"):
        messagebox.showwarning(APP_NAME, "Önce Ayarlar bölümünden taranacak klasör ekleyin.")
        return

    self.stop_event.clear()
    self.running=True
    self.scan_started_at=time.time()
    self.status.set("Dosyalar aranıyor...")
    self.progress_text.set("Dosyalar aranıyor...")
    try:
        self.stop_btn.configure(state="normal")
    except Exception:
        pass
    try:
        self.progress.stop()
        self.progress.configure(mode="indeterminate",maximum=100,value=0)
        self.progress.start(14)
    except Exception:
        pass
    self._set_live(action="Dosyalar aranıyor",done_bytes=0,total_bytes=0,speed_bps=0,event="Tarama başlatıldı")
    threading.Thread(target=self.scan_worker,daemon=True).start()
"""

    stop_scan_method = r"""
def stop_scan(self):
    if not self.running:
        self.status.set("Hazır - çalışan tarama yok")
        return
    self.stop_event.set()
    self.status.set("Durduruluyor...")
    self.progress_text.set("Durduruluyor...")
    self._set_live(action="Durduruluyor...",event="DURDUR komutu alındı")
    self.add_log_ui("DURDUR komutu alındı. Aktif tarama/kopyalama güvenli şekilde kesiliyor...")
    try:
        self.stop_btn.configure(state="disabled")
    except Exception:
        pass
    try:
        self.progress.stop()
        self.progress.configure(mode="determinate",maximum=100,value=0)
    except Exception:
        pass
"""

    copy_method = r"""
def _copy_with_progress(self,src,dst):
    total=max(1,src.stat().st_size)
    done=0
    started=time.time()
    dst.parent.mkdir(parents=True,exist_ok=True)
    self._set_live(done_bytes=0,total_bytes=total,speed_bps=0)
    try:
        with src.open("rb") as rf, dst.open("wb") as wf:
            while True:
                if self.stop_event.is_set():
                    raise RuntimeError("Kullanıcı tarafından durduruldu")
                chunk=rf.read(512*1024)
                if not chunk:
                    break
                wf.write(chunk)
                done += len(chunk)
                elapsed=max(0.001,time.time()-started)
                self._set_live(done_bytes=done,total_bytes=total,speed_bps=done/elapsed)
        try:
            shutil.copystat(src,dst)
        except Exception:
            pass
    except Exception:
        try:
            if dst.exists():
                dst.unlink()
        except Exception:
            pass
        raise
    elapsed=max(0.001,time.time()-started)
    self._set_live(done_bytes=total,total_bytes=total,speed_bps=total/elapsed)
"""

    classify_method = r"""
def classify_target(self,p):
    cloud=Path(self.config_data["cloud_root"])
    ext=p.suffix.lower()
    if ext in VIDEO_EXT:
        self._stat("Video")
        mb=p.stat().st_size/(1024*1024)
        game=safe_name(detect_game(p))
        if mb <= int(self.config_data.get("short_max_mb",150)):
            self._stat("Short")
            return cloud/"Videolar"/"Shorts"/game/p.name
        return cloud/"Videolar"/game/p.name
    if ext in IMAGE_EXT:
        if is_family(p,self.config_data.get("family_folders",[])):
            self._stat("Aile Resmi")
            return cloud/"Resimler"/"Aile"/p.name
        game=safe_name(detect_game(p))
        self._stat("Oyun Resmi")
        return cloud/"Resimler"/"Oyunlar"/game/p.name

    groups={
        "Belgeler":{
            "PDF":{".pdf"},"Word":{".doc",".docx",".odt",".rtf"},
            "Excel":{".xls",".xlsx",".ods"},"PowerPoint":{".ppt",".pptx",".odp"},
            "Metin":{".txt",".md"},"Tablo":{".csv",".tsv"}
        },
        "Sesler":{"Ses":{".mp3",".wav",".flac",".aac",".ogg",".m4a",".wma"}},
        "Arsivler":{"Arsiv":{".zip",".rar",".7z",".tar",".gz",".bz2",".xz"}},
        "Programlar":{"Program":{".exe",".msi",".msix",".appx",".apk",".bat",".cmd",".ps1"}},
        "Projeler":{
            "Python":{".py",".pyw"},"JavaScript":{".js",".jsx"},"TypeScript":{".ts",".tsx"},
            "Web":{".html",".htm",".css"},"JSON":{".json"},"XML":{".xml"},
            "YAML":{".yml",".yaml"},"SQL":{".sql"},"CSharp":{".cs"},
            "CPP":{".cpp",".cc",".cxx"},"C":{".c"},"Header":{".h",".hpp"},
            "Java":{".java"},"PHP":{".php"}
        },
        "Veriler":{"Veri":{".db",".sqlite",".sqlite3",".log",".ini",".cfg",".conf",".dat",".sav"}},
        "Tasarim":{"Tasarim":{".psd",".ai",".svg",".blend",".fbx",".obj",".stl"}},
        "Fontlar":{"Font":{".ttf",".otf",".woff",".woff2"}}
    }
    for top,subs in groups.items():
        for sub,exts in subs.items():
            if ext in exts:
                return cloud/top/sub/p.name
    if ext:
        return cloud/"Diger Dosyalar"/ext.lstrip(".").upper()/p.name
    return cloud/"Diger Dosyalar"/"Uzantisiz"/p.name
"""

    scan_method = r"""
def scan_worker(self):
    try:
        files=[]
        cloud=Path(self.config_data["cloud_root"]).resolve()
        self.after(0,lambda:self.status.set("Dosyalar aranıyor..."))
        self.after(0,lambda:self.progress_text.set("Dosyalar aranıyor..."))

        for root in self.config_data.get("watch_folders",[]):
            if self.stop_event.is_set():
                break
            rp=Path(root)
            if not rp.exists():
                self.add_log_ui(f"YOK: {rp}")
                continue
            for p in rp.rglob("*"):
                if self.stop_event.is_set():
                    break
                if not p.is_file():
                    continue
                try:
                    if str(p.resolve()).lower().startswith(str(cloud).lower()):
                        continue
                except Exception:
                    pass
                files.append(p)

        if self.stop_event.is_set():
            self.after(0,self.progress.stop)
            self.after(0,lambda:self.progress.configure(mode="determinate",maximum=100,value=0))
            self.after(0,lambda:self.progress_text.set("Durduruldu"))
            self.after(0,lambda:self.status.set("Tarama durduruldu"))
            self._set_live(action="Tarama durduruldu",done_bytes=0,total_bytes=0,speed_bps=0,event="Tarama durduruldu")
            return

        total=len(files)
        self.after(0,self.progress.stop)
        self.after(0,lambda:self.progress.configure(mode="determinate",maximum=max(1,total),value=0))
        self.after(0,lambda:self.progress_text.set(f"0 / {total}"))

        processed_window=0
        for i,p in enumerate(files,1):
            if self.stop_event.is_set():
                break
            self._stat("Taranan")
            try:
                ext=p.suffix.lower()
                family=(ext in IMAGE_EXT and is_family(p,self.config_data.get("family_folders",[])))
                game=detect_game(p) if ext in VIDEO_EXT or (ext in IMAGE_EXT and not family) else "-"
                if ext in VIDEO_EXT:
                    kind="Video"
                elif family:
                    kind="Aile Resmi"
                elif ext in IMAGE_EXT:
                    kind="Oyun Resmi"
                else:
                    kind=(ext.lstrip(".").upper() or "Uzantısız Dosya")
                self._set_live(action="Dosya analiz ediliyor",file=p.name,source=str(p),target="-",game=game,kind=kind,done_bytes=0,total_bytes=0,speed_bps=0,event=f"Analiz: {p.name}")

                if not file_age_stable(p):
                    self._set_live(action="Dosya hâlâ yazılıyor, atlandı",event=f"Atlandı: {p.name}")
                    self.add_log_ui(f"ATLANDI (dosya hâlâ yazılıyor olabilir): {p}")
                else:
                    fingerprint=file_fingerprint(p)
                    old=self.history.get(fingerprint)
                    if old:
                        self._set_live(action="Daha önce arşivlendi — tekrar kopyalanmadı",target=old.get("target","-"),event=f"Geçmişte arşivlendi: {p.name}")
                        self.add_log_ui(f"GEÇMİŞTE ARŞİVLENDİ, ATLANDI: {p} -> {old.get('target','')}")
                    else:
                        dst=self.classify_target(p)
                        if ext in VIDEO_EXT and "Shorts" in dst.parts:
                            kind="Short Video"
                        self._set_live(action="Hedef hazırlanıyor",target=str(dst),game=game,kind=kind)
                        dst.parent.mkdir(parents=True,exist_ok=True)

                        if dst.exists() and dst.stat().st_size == p.stat().st_size:
                            self.history[fingerprint]={"source":str(p),"target":str(dst),"size":p.stat().st_size,"archived_at":time.strftime("%Y-%m-%d %H:%M:%S")}
                            save_history(self.history)
                            self._set_live(action="Zaten arşivde — tekrar kopyalanmadı",target=str(dst),event=f"Zaten var: {p.name}")
                            self.add_log_ui(f"ZATEN VAR: {dst}")
                        else:
                            dst=unique_target(dst)
                            retries=max(1,int(self.config_data.get("retry_count",5)))
                            last_error=None
                            copied=False
                            for attempt in range(1,retries+1):
                                if self.stop_event.is_set():
                                    break
                                try:
                                    self._set_live(action=f"Buluta kopyalanıyor — deneme {attempt}/{retries}",target=str(dst),done_bytes=0,total_bytes=p.stat().st_size,speed_bps=0)
                                    if dst.exists():
                                        try: dst.unlink()
                                        except Exception: pass
                                    self._copy_with_progress(p,dst)
                                    if dst.exists() and dst.stat().st_size == p.stat().st_size:
                                        copied=True
                                        break
                                    raise IOError("Kopyalama doğrulaması başarısız")
                                except Exception as retry_error:
                                    last_error=retry_error
                                    if self.stop_event.is_set():
                                        break
                                    self.add_log_ui(f"YENİDEN DENENECEK ({attempt}/{retries}): {p.name} | {retry_error}")
                                    time.sleep(min(2*attempt,8))

                            if self.stop_event.is_set():
                                break
                            if not copied:
                                raise RuntimeError(f"{retries} denemede sonuç alınamadı: {last_error}")

                            self.history[fingerprint]={"source":str(p),"target":str(dst),"size":p.stat().st_size,"archived_at":time.strftime("%Y-%m-%d %H:%M:%S")}
                            save_history(self.history)
                            self._set_live(action="Buluta kopyalama tamamlandı",target=str(dst),event=f"Kopyalandı: {p.name}")
                            self.add_log_ui(f"KOPYALANDI: {p.name} -> {dst.parent}")
                processed_window += 1
            except Exception as e:
                if self.stop_event.is_set():
                    break
                self._stat("Hata")
                self._set_live(action=f"HATA: {e}",event=f"Hata: {p.name}")
                self.add_log_ui(f"HATA: {p} | {e}")

            self.after(0,lambda v=i,t=total:(self.progress.configure(value=v),self.progress_text.set(f"{v} / {t}"),self._draw_live_panel()))
            if i%5==0:
                self.update_graph(processed_window)
                processed_window=0

        self.update_graph(processed_window)
        final_text="Tarama durduruldu" if self.stop_event.is_set() else "Tarama tamamlandı"
        self.after(0,self.progress.stop)
        self.after(0,lambda:self.status.set(final_text))
        self.after(0,lambda:self.progress_text.set("Durduruldu" if self.stop_event.is_set() else f"{total} / {total}"))
        self._set_live(action=final_text,done_bytes=0,total_bytes=0,speed_bps=0,event=final_text)
    finally:
        self.running=False
        try:
            self.after(0,lambda:self.stop_btn.configure(state="normal"))
        except Exception:
            pass
"""

    update_method = r"""
def start_self_update(self):
    import subprocess,sys,os
    from pathlib import Path
    try:
        self.update_progress.stop()
        self.update_progress.configure(mode="indeterminate",maximum=100,value=0)
        self.update_progress.start(12)
    except Exception:
        pass
    try:
        self.update_status_var.set("Güncelleme kontrol ediliyor...")
    except Exception:
        pass
    _u=Path(os.environ.get("LOCALAPPDATA",str(Path.home()/"AppData/Local")))/"SolinajArsivUpdater"/"SolinajArsivSafeUpdaterV2.pyw"
    if not _u.exists():
        try:
            self.update_progress.stop()
        except Exception:
            pass
        messagebox.showerror("Solinaj Arşiv","Güvenli güncelleme modülü bulunamadı.")
        return
    _p=Path(sys.executable).with_name("pythonw.exe") if os.name=="nt" else Path(sys.executable)
    if not _p.exists():
        _p=Path(sys.executable)
    _flags=0x08000000 if os.name=="nt" else 0
    subprocess.Popen([str(_p),str(_u),str(os.getpid())],creationflags=_flags)
"""

    for name, method in [
        ("start_scan", start_scan_method),
        ("stop_scan", stop_scan_method),
        ("_copy_with_progress", copy_method),
        ("classify_target", classify_method),
        ("scan_worker", scan_method),
        ("start_self_update", update_method),
    ]:
        source_text = _replace_app_method(source_text, name, method)

    compile(source_text, "<solinaj_arsivleyici_v15_7>", "exec")

    checks = [
        'APP_VERSION = "15.7"',
        'self.stop_btn=ttk.Button',
        'self.update_progress=ttk.Progressbar',
        'threading.Thread(target=self.scan_worker',
        'return cloud/"Diger Dosyalar"',
        'self.stop_event.set()',
    ]
    missing=[x for x in checks if x not in source_text]
    if missing:
        raise RuntimeError("V15.7 doğrulaması başarısız: "+", ".join(missing))
    return source_text
