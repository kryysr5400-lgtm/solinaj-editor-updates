import ast
import re

TARGET_VERSION = "15.6"

def _replace_app_method(source_text, method_name, new_method_source):
    tree = ast.parse(source_text)
    app = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            app = node
            break
    if app is None:
        raise RuntimeError("App sınıfı bulunamadı.")

    matches = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == method_name]
    if not matches:
        raise RuntimeError(f"{method_name} metodu bulunamadı.")

    # Sınıf içindeki son tanım Python'da etkili olandır.
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    indent = " " * target.col_offset
    replacement = "".join(indent + line + "\n" for line in new_method_source.strip("\n").splitlines())
    return "".join(lines[:start]) + replacement + "".join(lines[end:])

def apply_update(source_text):
    # Bu yama gerçek V15.5 kurulum yapısına özeldir.
    if 'APP_VERSION = "15.5"' not in source_text:
        raise RuntimeError("Bu güncelleme yalnızca V15.5 sürümüne uygulanabilir.")
    if "def scan_worker(self):" not in source_text:
        raise RuntimeError("V15.5 tarama motoru bulunamadı.")

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Arşivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V15.6"',
        source_text,
        count=1
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "15.6"',
        source_text,
        count=1
    )

    start_method = r"""
def start_scan(self):
    if self.running:
        self.status.set("Tarama zaten çalışıyor")
        return
    if not self.config_data.get("watch_folders"):
        messagebox.showwarning(APP_NAME, "Önce Ayarlar bölümünden taranacak klasör ekleyin.")
        return

    self.stop_event.clear()
    self.running = True
    self.scan_started_at = time.time()
    self.progress_text.set("Dosyalar aranıyor...")
    self.status.set("Dosyalar aranıyor...")
    self._set_live(
        action="Dosyalar aranıyor",
        done_bytes=0,
        total_bytes=0,
        speed_bps=0,
        event="Tarama başlatıldı"
    )
    try:
        self.progress.stop()
        self.progress.configure(mode="indeterminate", maximum=100, value=0)
        self.progress.start(12)
    except Exception:
        pass
    threading.Thread(target=self.scan_worker, daemon=True).start()
"""

    stop_method = r"""
def stop_scan(self):
    if not self.running:
        self.status.set("Hazır - çalışan tarama yok")
        return
    self.stop_event.set()
    self.status.set("Durduruluyor...")
    self.progress_text.set("Durduruluyor...")
    self._set_live(action="Durduruluyor...", event="DURDUR komutu alındı")
    self.add_log_ui("DURDUR komutu alındı. Aktif işlem güvenli şekilde kesiliyor...")
    try:
        self.progress.stop()
    except Exception:
        pass
"""

    copy_method = r"""
def _copy_with_progress(self, src, dst):
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
            self.after(0,lambda:self.progress_text.set("0 / 0"))
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
                game=detect_game(p) if ext in VIDEO_EXT or (ext in IMAGE_EXT and not is_family(p,self.config_data.get("family_folders",[]))) else "-"
                kind=("Video" if ext in VIDEO_EXT else ("Aile Resmi" if ext in IMAGE_EXT and is_family(p,self.config_data.get("family_folders",[])) else ("Oyun Resmi" if ext in IMAGE_EXT else (ext.lstrip(".").upper() or "Dosya"))))
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
                        if dst is None:
                            self._set_live(action="Desteklenmeyen dosya türü",event=f"Desteklenmedi: {p.name}")
                        else:
                            kind=("Short Video" if ext in VIDEO_EXT and "Shorts" in dst.parts else kind)
                            self._set_live(action="Hedef hazırlanıyor",target=str(dst),game=game,kind=kind)
                            dst.parent.mkdir(parents=True,exist_ok=True)

                            if dst.exists() and dst.stat().st_size == p.stat().st_size:
                                self.history[fingerprint]={"source":str(p),"target":str(dst),"size":p.stat().st_size,"archived_at":time.strftime("%Y-%m-%d %H:%M:%S")}
                                save_history(self.history)
                                self._set_live(action="Zaten arşivde — geçmişe kaydedildi",target=str(dst),event=f"Zaten var: {p.name}")
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

                                if copied:
                                    self.history[fingerprint]={"source":str(p),"target":str(dst),"size":p.stat().st_size,"archived_at":time.strftime("%Y-%m-%d %H:%M:%S")}
                                    save_history(self.history)
                                    self._set_live(action="Buluta kopyalama tamamlandı",target=str(dst),event=f"Kopyalandı: {p.name}")
                                    self.add_log_ui(f"KOPYALANDI: {p.name} -> {dst.parent}")
                                else:
                                    raise RuntimeError(f"{retries} denemede sonuç alınamadı: {last_error}")
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
"""

    source_text = _replace_app_method(source_text, "start_scan", start_method)
    source_text = _replace_app_method(source_text, "stop_scan", stop_method)
    source_text = _replace_app_method(source_text, "_copy_with_progress", copy_method)
    source_text = _replace_app_method(source_text, "scan_worker", scan_method)

    compile(source_text, "<solinaj_arsivleyici_v15_6>", "exec")

    if 'APP_VERSION = "15.6"' not in source_text:
        raise RuntimeError("Sürüm bilgisi V15.6 olarak değiştirilemedi.")
    if "threading.Thread(target=self.scan_worker" not in source_text:
        raise RuntimeError("TARAMAYI BAŞLAT bağlantısı doğrulanamadı.")
    if 'self.stop_event.set()' not in source_text:
        raise RuntimeError("DURDUR işlevi doğrulanamadı.")

    return source_text
