import ast
import re

TARGET_VERSION = "15.6"

def _replace_method(source_text, method_name, new_method_source):
    tree = ast.parse(source_text)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            target = node
            break
    if target is None:
        raise RuntimeError(f"{method_name} metodu bulunamadı.")
    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    indent = " " * target.col_offset
    replacement = "".join(indent + line + "\n" for line in new_method_source.strip("\n").splitlines())
    return "".join(lines[:start]) + replacement + "".join(lines[end:])

def apply_update(source_text):
    source_text = re.sub(r'APP_NAME\s*=\s*"Solinaj Arşivleyici V[^"]+"', 'APP_NAME = "Solinaj Arşivleyici V15.6"', source_text, count=1)
    source_text = re.sub(r'APP_VERSION\s*=\s*"[^"]+"', 'APP_VERSION = "15.6"', source_text, count=1)

    start_method = """
def start_scan(self,auto=False):
    if self.running:
        return
    if not self.config_data.get("watch_folders"):
        if not auto:
            messagebox.showwarning("Uyarı","Önce taranacak klasör ekleyin.")
        return
    self.running=True
    self.stop_event.clear()
    self.status.set("Dosyalar aranıyor...")
    try:
        self.stop_btn.configure(state="normal")
        self.progress.stop()
        self.progress.configure(mode="indeterminate",maximum=100,value=0)
        self.progress.start(10)
    except Exception:
        pass
    threading.Thread(target=self._scan_worker,daemon=True).start()
"""

    stop_method = """
def stop_scan(self):
    if not self.running:
        self.status.set("Hazır - çalışan tarama yok")
        return
    self.stop_event.set()
    self.status.set("Durduruluyor...")
    try:
        self.stop_btn.configure(state="disabled")
        self.progress.stop()
        self.progress.configure(mode="determinate",maximum=100,value=0)
    except Exception:
        pass
    self.add_log_ui("DURDUR komutu alındı. İşlem güvenli şekilde kesiliyor...")
"""

    copy_method = """
def _copy_with_progress(self,src,dst):
    total=max(1,src.stat().st_size)
    done=0
    chunk=512*1024
    dst.parent.mkdir(parents=True,exist_ok=True)
    try:
        self.after(0,self.progress.stop)
        self.after(0,lambda:self.progress.configure(mode="determinate",maximum=100,value=0))
        with src.open("rb") as fi, dst.open("wb") as fo:
            while True:
                if self.stop_event.is_set():
                    raise RuntimeError("Durduruldu")
                b=fi.read(chunk)
                if not b:
                    break
                fo.write(b)
                done+=len(b)
                pct=min(100.0,(done/total)*100.0)
                self.after(0,lambda p=pct:self.progress.configure(value=p))
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
"""

    scan_method = """
def _scan_worker(self):
    try:
        cloud=Path(self.config_data["cloud_root"])
        cloud.mkdir(parents=True,exist_ok=True)
        files=[]
        self.after(0,lambda:self.status.set("Dosyalar aranıyor..."))
        for folder in self.config_data.get("watch_folders",[]):
            root=Path(folder)
            if not root.exists():
                continue
            for p in root.rglob("*"):
                if self.stop_event.is_set():
                    break
                if not p.is_file():
                    continue
                try:
                    if str(p.resolve()).lower().startswith(str(cloud.resolve()).lower()):
                        continue
                except Exception:
                    pass
                files.append(p)
            if self.stop_event.is_set():
                break

        if self.stop_event.is_set():
            return

        self.after(0,self.progress.stop)
        total=len(files)
        self.after(0,lambda:self.progress.configure(mode="determinate",maximum=100,value=0))
        for i,p in enumerate(files,1):
            if self.stop_event.is_set():
                break
            self._stat("Taranan")
            fp=self._fingerprint(p)
            if fp in self.history:
                overall=(i/max(1,total))*100.0
                self.after(0,lambda v=overall:self.progress.configure(value=v))
                continue
            if not is_file_stable(p):
                self.add_log_ui(f"ATLANDI (dosya kullanımda/yeni): {p.name}")
                continue
            try:
                targetdir=self.classify_target(p)
                targetdir.mkdir(parents=True,exist_ok=True)
                dst=unique_target(targetdir/p.name)
                self.add_log_ui(f"KOPYALANIYOR: {p.name} -> {targetdir}")
                if self.config_data.get("copy_mode",True):
                    self._copy_with_progress(p,dst)
                else:
                    if self.stop_event.is_set():
                        break
                    shutil.move(str(p),str(dst))
                if self.stop_event.is_set():
                    break
                self.history[fp]={"source":str(p),"target":str(dst),"time":time.time()}
                save_history(self.history)
                self.after(0,lambda p=p,dst=dst:self.tree.insert("",0,values=(p.name,p.suffix.lower() or "uzantisiz",str(dst.parent))))
            except Exception as e:
                if self.stop_event.is_set() or str(e)=="Durduruldu":
                    self.add_log_ui("Tarama kullanıcı tarafından durduruldu.")
                    break
                self._stat("Hata")
                self.add_log_ui(f"HATA: {p.name} | {e}")
            overall=(i/max(1,total))*100.0
            self.after(0,lambda v=overall:self.progress.configure(value=v))
        self.after(0,self.progress.stop)
        self.after(0,lambda:self.progress.configure(mode="determinate",maximum=100,value=0 if self.stop_event.is_set() else 100))
        self.after(0,lambda:self.status.set("Tarama durduruldu" if self.stop_event.is_set() else "Tarama tamamlandı"))
    finally:
        self.running=False
        self.after(0,lambda:self.stop_btn.configure(state="normal"))
"""

    source_text = _replace_method(source_text, "start_scan", start_method)
    source_text = _replace_method(source_text, "stop_scan", stop_method)
    source_text = _replace_method(source_text, "_copy_with_progress", copy_method)
    source_text = _replace_method(source_text, "_scan_worker", scan_method)
    compile(source_text, "<solinaj_arsivleyici_v15_6>", "exec")
    if 'APP_VERSION = "15.6"' not in source_text:
        raise RuntimeError("Sürüm bilgisi güncellenemedi.")
    return source_text
