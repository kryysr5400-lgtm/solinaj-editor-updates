import ast,re

TARGET_VERSION="15.6"

def _replace_method(src,name,body):
    tree=ast.parse(src)
    app=next((n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="App"),None)
    if app is None: raise RuntimeError("App sınıfı bulunamadı.")
    ms=[n for n in app.body if isinstance(n,ast.FunctionDef) and n.name==name]
    if not ms: raise RuntimeError(f"{name} metodu bulunamadı.")
    n=ms[-1]; lines=src.splitlines(keepends=True); indent=" "*n.col_offset
    repl="".join(indent+x+"\n" for x in body.strip("\n").splitlines())
    return "".join(lines[:n.lineno-1])+repl+"".join(lines[n.end_lineno:])

def apply_update(source_text):
    if 'APP_VERSION = "15.5"' not in source_text:
        raise RuntimeError("Bu güncelleme yalnızca V15.5 sürümüne uygulanabilir.")
    if "def scan_worker(self):" not in source_text:
        raise RuntimeError("V15.5 tarama motoru bulunamadı.")

    source_text=re.sub(r'APP_NAME\s*=\s*"Solinaj Arşivleyici V[^"]+"','APP_NAME = "Solinaj Arşivleyici V15.6"',source_text,count=1)
    source_text=re.sub(r'APP_VERSION\s*=\s*"[^"]+"','APP_VERSION = "15.6"',source_text,count=1)

    start=r"""
def start_scan(self):
    if self.running:
        self.status.set("Tarama zaten çalışıyor")
        return
    if not self.config_data.get("watch_folders"):
        messagebox.showwarning(APP_NAME,"Önce Ayarlar bölümünden taranacak klasör ekleyin.")
        return
    self.stop_event.clear()
    self.running=True
    self.scan_started_at=time.time()
    self.status.set("Dosyalar aranıyor...")
    self.progress_text.set("Dosyalar aranıyor...")
    try:
        self.progress.stop()
        self.progress.configure(mode="indeterminate",maximum=100,value=0)
        self.progress.start(12)
    except Exception:
        pass
    self._set_live(action="Dosyalar aranıyor",done_bytes=0,total_bytes=0,speed_bps=0,event="Tarama başlatıldı")
    threading.Thread(target=self.scan_worker,daemon=True).start()
"""
    stop=r"""
def stop_scan(self):
    if not self.running:
        self.status.set("Hazır - çalışan tarama yok")
        return
    self.stop_event.set()
    self.status.set("Durduruluyor...")
    self.progress_text.set("Durduruluyor...")
    try:
        self.progress.stop()
    except Exception:
        pass
    self._set_live(action="Durduruluyor...",event="DURDUR komutu alındı")
    self.add_log_ui("DURDUR komutu alındı. Aktif işlem güvenli şekilde kesiliyor...")
"""
    copy=r"""
def _copy_with_progress(self,src,dst):
    total=max(1,src.stat().st_size); done=0; started=time.time()
    dst.parent.mkdir(parents=True,exist_ok=True)
    self.after(0,self.progress.stop)
    self.after(0,lambda:self.progress.configure(mode="determinate",maximum=100,value=0))
    self._set_live(done_bytes=0,total_bytes=total,speed_bps=0)
    try:
        with src.open("rb") as rf,dst.open("wb") as wf:
            while True:
                if self.stop_event.is_set():
                    raise RuntimeError("Kullanıcı tarafından durduruldu")
                chunk=rf.read(512*1024)
                if not chunk: break
                wf.write(chunk); done+=len(chunk)
                pct=min(100.0,done*100.0/total)
                elapsed=max(0.001,time.time()-started)
                self.after(0,lambda p=pct:self.progress.configure(value=p))
                self._set_live(done_bytes=done,total_bytes=total,speed_bps=done/elapsed)
        try: shutil.copystat(src,dst)
        except Exception: pass
    except Exception:
        try:
            if dst.exists(): dst.unlink()
        except Exception: pass
        raise
"""
    source_text=_replace_method(source_text,"start_scan",start)
    source_text=_replace_method(source_text,"stop_scan",stop)
    source_text=_replace_method(source_text,"_copy_with_progress",copy)

    source_text=source_text.replace(
        'self.after(0,lambda:self.progress.configure(maximum=max(1,total),value=0))',
        'self.after(0,self.progress.stop)\n            self.after(0,lambda:self.progress.configure(mode="determinate",maximum=max(1,total),value=0))',
        1
    )
    compile(source_text,"<solinaj_v15_6>","exec")
    if 'APP_VERSION = "15.6"' not in source_text or "threading.Thread(target=self.scan_worker" not in source_text:
        raise RuntimeError("V15.6 doğrulaması başarısız.")
    return source_text
