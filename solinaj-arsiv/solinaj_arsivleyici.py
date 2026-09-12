import os, sys, json, shutil, threading, time, subprocess, hashlib, zipfile
import urllib.request
import urllib.error
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "Solinaj Arşivleyici V15.1"
APP_VERSION = "15.1"
UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/kryysr5400-lgtm/solinaj-editor-updates/main/solinaj-arsiv/latest.json"
BASE = Path(__file__).resolve().parent
CONFIG_FILE = BASE / "config.json"
LOG_FILE = BASE / "solinaj_arsivleyici.log"
HISTORY_FILE = BASE / "arsiv_gecmisi.json"

VIDEO_EXT = {".mp4",".mkv",".mov",".avi",".webm",".m4v",".ts"}
IMAGE_EXT = {".jpg",".jpeg",".png",".webp",".bmp",".gif",".tif",".tiff"}
SHORT_MAX_SECONDS = 180

GAME_KEYWORDS = {
    "7 Days to Die": ["7 days", "7daystodie", "7dtd", "7_days"],
    "Age of Empires II": ["age of empires ii", "age2", "aoe2", "aoe ii"],
    "World of Warships": ["world of warships", "wows"],
    "Battlefield 1": ["battlefield 1", "bf1"],
    "Cities Skylines": ["cities skylines", "cities_skylines"],
    "World of Tanks": ["world of tanks", "wot"],
    "Manor Lords": ["manor lords", "manorlords"],
    "The Long Dark": ["the long dark", "thelongdark"],
    "Valheim": ["valheim"],
    "Counter-Strike": ["counter-strike", "counter strike", "cs2", "csgo"],
    "Crime Simulator": ["crime simulator", "crime_simulator"],
}

DEFAULT = {
    "watch_folders": [],
    "cloud_root": str(Path.home() / "Sync"),
    "family_folders": [],
    "auto_scan_minutes": 10,
    "auto_scan": True,
    "copy_mode": True,
    "retry_count": 5,
    "short_max_mb": 150,
    "short_max_seconds": SHORT_MAX_SECONDS
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            d=json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            x=DEFAULT.copy(); x.update(d); return x
        except Exception:
            pass
    return DEFAULT.copy()

def save_config(d):
    CONFIG_FILE.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")

def log(msg):
    line=time.strftime("[%Y-%m-%d %H:%M:%S] ")+msg
    try:
        with LOG_FILE.open("a",encoding="utf-8") as f: f.write(line+"\n")
    except Exception: pass

def safe_name(s):
    bad='<>:"/\\|?*'
    for c in bad: s=s.replace(c,"_")
    return s.strip() or "Bilinmeyen"

def is_file_stable(path, seconds=8):
    try:
        s1=path.stat().st_size
        m1=path.stat().st_mtime
        if time.time()-m1 < seconds:
            return False
        time.sleep(0.05)
        return path.stat().st_size == s1
    except Exception:
        return False

def unique_target(dst: Path):
    if not dst.exists():
        return dst
    i=2
    while True:
        x=dst.with_name(f"{dst.stem}_{i}{dst.suffix}")
        if not x.exists(): return x
        i+=1

def load_history():
    if HISTORY_FILE.exists():
        try:
            data=json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data,dict): return data
        except Exception:
            pass
    return {}

def save_history(history):
    tmp=HISTORY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(HISTORY_FILE)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1180x760")
        self.minsize(1000,640)
        self.config_data=load_config()
        self.history=load_history()
        self.running=False
        self.stop_event=threading.Event()
        self.stats={"Taranan":0,"Video":0,"Short":0,"Oyun Resmi":0,"Aile Resmi":0,"Hata":0}
        self._style()
        self._ui()
        self.after(1200,self._start_auto_if_needed)

    def _style(self):
        self.configure(bg="#07101b")
        st=ttk.Style(self)
        try: st.theme_use("clam")
        except Exception: pass
        st.configure("Dark.TFrame", background="#0a1623")
        st.configure("Panel.TFrame", background="#0d1b29")
        st.configure("Dark.TLabel", background="#0a1623", foreground="#edf7ff", font=("Segoe UI",10))
        st.configure("Muted.TLabel", background="#0a1623", foreground="#8ea7ba", font=("Segoe UI",9))
        st.configure("Blue.TButton", font=("Segoe UI",10,"bold"), padding=(16,10), foreground="#ffffff", background="#079af2", borderwidth=0)
        st.map("Blue.TButton", background=[("active","#1ab1ff"),("disabled","#345064")])
        st.configure("Gray.TButton", font=("Segoe UI",10), padding=(14,9), foreground="#eef7ff", background="#233547", borderwidth=0)
        st.map("Gray.TButton", background=[("active","#31495f")])
        st.configure("Danger.TButton", font=("Segoe UI",10,"bold"), padding=(14,9), foreground="#ffffff", background="#79252c", borderwidth=0)
        st.map("Danger.TButton", background=[("active","#9b3039")])
        st.configure("Dark.TLabelframe", background="#0d1b29", foreground="#dceaf5", bordercolor="#1a4c6f", relief="solid")
        st.configure("Dark.TLabelframe.Label", background="#0d1b29", foreground="#dceaf5", font=("Segoe UI",10,"bold"))
        st.configure("Treeview", background="#0a1420", fieldbackground="#0a1420", foreground="#dce9f5", rowheight=25, borderwidth=0)
        st.configure("Treeview.Heading", background="#10283b", foreground="#eaf7ff", font=("Segoe UI",9,"bold"), relief="flat")
        st.map("Treeview", background=[("selected","#0a75aa")])
        st.configure("TProgressbar", troughcolor="#122331", background="#0aa8f5", bordercolor="#122331", lightcolor="#0aa8f5", darkcolor="#0aa8f5")

    def _ui(self):
        root=ttk.Frame(self,style="Dark.TFrame"); root.pack(fill="both",expand=True)
        header=ttk.Frame(root,style="Dark.TFrame"); header.pack(fill="x",padx=18,pady=(14,8))
        left=ttk.Frame(header,style="Dark.TFrame"); left.pack(side="left",fill="x",expand=True)
        ttk.Label(left,text="SOLINAJ ARŞİV",style="Dark.TLabel",font=("Segoe UI",22,"bold")).pack(anchor="w")
        ttk.Label(left,text="Akıllı arşivleme • Kaydet • Ayır • Buluta Gönder",style="Muted.TLabel").pack(anchor="w")
        self.version_lbl=ttk.Label(header,text=f"V{APP_VERSION}",style="Dark.TLabel",font=("Segoe UI",11,"bold")); self.version_lbl.pack(side="right",padx=(8,0))

        actions=ttk.Frame(root,style="Dark.TFrame"); actions.pack(fill="x",padx=18,pady=(0,10))
        self.scan_btn=ttk.Button(actions,text="TARAMAYI BAŞLAT",style="Blue.TButton",command=self.start_scan); self.scan_btn.pack(side="left",padx=(0,8))
        self.stop_btn=ttk.Button(actions,text="DURDUR",style="Danger.TButton",command=self.stop_scan); self.stop_btn.pack(side="left",padx=(0,8))
        self.update_btn=ttk.Button(actions,text="GÜNCELLE",style="Gray.TButton",command=self.start_self_update); self.update_btn.pack(side="left",padx=(0,8))
        ttk.Button(actions,text="AYARLAR",style="Gray.TButton",command=self.open_settings).pack(side="left")
        self.status=tk.StringVar(value="Hazır")
        ttk.Label(actions,textvariable=self.status,style="Muted.TLabel").pack(side="right")

        statsbar=ttk.Frame(root,style="Dark.TFrame"); statsbar.pack(fill="x",padx=18,pady=(0,10))
        self.stat_vars={}
        for key in ["Taranan","Video","Short","Oyun Resmi","Aile Resmi","Hata"]:
            card=ttk.Frame(statsbar,style="Panel.TFrame",padding=10); card.pack(side="left",fill="x",expand=True,padx=4)
            ttk.Label(card,text=key,style="Muted.TLabel").pack(anchor="w")
            v=tk.StringVar(value="0"); self.stat_vars[key]=v
            ttk.Label(card,textvariable=v,style="Dark.TLabel",font=("Segoe UI",15,"bold")).pack(anchor="w")

        center=ttk.Frame(root,style="Dark.TFrame"); center.pack(fill="both",expand=True,padx=18,pady=(0,10))
        leftpanel=ttk.LabelFrame(center,text=" Arşivleme İlerlemesi ",style="Dark.TLabelframe",padding=12); leftpanel.pack(side="left",fill="both",expand=True,padx=(0,8))
        self.progress=ttk.Progressbar(leftpanel,mode="determinate"); self.progress.pack(fill="x",pady=(4,8))
        self.live_text=tk.Text(leftpanel,bg="#07131f",fg="#d8efff",insertbackground="white",height=13,relief="flat",font=("Consolas",9)); self.live_text.pack(fill="both",expand=True)
        self.live_text.insert("end","Hazır. Tarama başlatıldığında canlı işlemler burada görünür.\n"); self.live_text.config(state="disabled")

        rightpanel=ttk.LabelFrame(center,text=" Son İşlemler ",style="Dark.TLabelframe",padding=8); rightpanel.pack(side="left",fill="both",expand=True,padx=(8,0))
        cols=("dosya","tur","hedef")
        self.tree=ttk.Treeview(rightpanel,columns=cols,show="headings",height=14)
        self.tree.heading("dosya",text="Dosya"); self.tree.heading("tur",text="Tür"); self.tree.heading("hedef",text="Hedef")
        self.tree.column("dosya",width=190); self.tree.column("tur",width=90); self.tree.column("hedef",width=240)
        self.tree.pack(fill="both",expand=True)

    def _start_auto_if_needed(self):
        if self.config_data.get("auto_scan") and self.config_data.get("watch_folders"):
            self.start_scan(auto=True)

    def add_log_ui(self,msg):
        log(msg)
        def work():
            try:
                self.live_text.config(state="normal"); self.live_text.insert("end",time.strftime("%H:%M:%S ")+"  "+msg+"\n"); self.live_text.see("end"); self.live_text.config(state="disabled")
            except Exception: pass
        self.after(0,work)

    def _stat(self,k,n=1):
        self.stats[k]+=n
        self.after(0,lambda:self.stat_vars[k].set(str(self.stats[k])))

    def classify_target(self,p):
        cloud=Path(self.config_data["cloud_root"])
        ext=p.suffix.lower()
        if ext in VIDEO_EXT:
            self._stat("Video")
            low=str(p).lower()
            game="Bilinmeyen Oyun"
            for g,keys in GAME_KEYWORDS.items():
                if any(k in low for k in keys): game=g; break
            target=cloud/"Videolar"/safe_name(game)
            try:
                if p.stat().st_size <= int(self.config_data.get("short_max_mb",150))*1024*1024:
                    target=cloud/"Shorts"/safe_name(game); self._stat("Short")
            except Exception: pass
            return target
        if ext in IMAGE_EXT:
            low=str(p).lower()
            fam=False
            for f in self.config_data.get("family_folders",[]):
                try:
                    if str(p.resolve()).lower().startswith(str(Path(f).resolve()).lower()): fam=True; break
                except Exception: pass
            if fam:
                self._stat("Aile Resmi"); return cloud/"Resimler"/"Aile"
            game="Diger"
            for g,keys in GAME_KEYWORDS.items():
                if any(k in low for k in keys): game=g; break
            self._stat("Oyun Resmi"); return cloud/"Resimler"/"Oyun"/safe_name(game)
        return cloud/"Diger"

    def _fingerprint(self,p):
        try:
            st=p.stat(); return f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}"
        except Exception: return str(p)

    def _copy_with_progress(self,src,dst):
        total=max(1,src.stat().st_size); done=0; started=time.time(); chunk=4*1024*1024
        dst.parent.mkdir(parents=True,exist_ok=True)
        with src.open("rb") as fi, dst.open("wb") as fo:
            while True:
                if self.stop_event.is_set(): raise RuntimeError("Durduruldu")
                b=fi.read(chunk)
                if not b: break
                fo.write(b); done+=len(b)
                self.after(0,lambda d=done,t=total:self.progress.configure(maximum=t,value=d))
        try: shutil.copystat(src,dst)
        except Exception: pass

    def start_scan(self,auto=False):
        if self.running: return
        if not self.config_data.get("watch_folders"):
            if not auto: messagebox.showwarning(APP_NAME,"Önce AYARLAR bölümünden en az bir kayıt/tarama klasörü seçin.")
            return
        self.running=True; self.stop_event.clear(); self.status.set("Tarama başladı")
        threading.Thread(target=self._scan_worker,daemon=True).start()

    def stop_scan(self):
        self.stop_event.set(); self.status.set("Durduruluyor...")

    def _scan_worker(self):
        try:
            cloud=Path(self.config_data["cloud_root"]); cloud.mkdir(parents=True,exist_ok=True)
            files=[]
            for folder in self.config_data.get("watch_folders",[]):
                root=Path(folder)
                if not root.exists(): continue
                for p in root.rglob("*"):
                    if self.stop_event.is_set(): break
                    if not p.is_file(): continue
                    try:
                        if str(p.resolve()).lower().startswith(str(cloud.resolve()).lower()): continue
                    except Exception: pass
                    if p.suffix.lower() in VIDEO_EXT|IMAGE_EXT: files.append(p)
            total=len(files); self.after(0,lambda:self.progress.configure(maximum=max(1,total),value=0))
            for i,p in enumerate(files,1):
                if self.stop_event.is_set(): break
                self._stat("Taranan")
                fp=self._fingerprint(p)
                if fp in self.history:
                    self.after(0,lambda i=i:self.progress.configure(maximum=max(1,total),value=i)); continue
                if not is_file_stable(p):
                    self.add_log_ui(f"ATLANDI (dosya kullanımda/yeni): {p.name}"); continue
                try:
                    targetdir=self.classify_target(p); targetdir.mkdir(parents=True,exist_ok=True)
                    dst=unique_target(targetdir/p.name)
                    self.add_log_ui(f"KOPYALANIYOR: {p.name} -> {targetdir}")
                    if self.config_data.get("copy_mode",True): self._copy_with_progress(p,dst)
                    else: shutil.move(str(p),str(dst))
                    self.history[fp]={"source":str(p),"target":str(dst),"time":time.time()}; save_history(self.history)
                    self.after(0,lambda p=p,dst=dst:self.tree.insert("",0,values=(p.name,p.suffix.lower(),str(dst.parent))))
                except Exception as e:
                    self._stat("Hata"); self.add_log_ui(f"HATA: {p.name} | {e}")
                self.after(0,lambda i=i:self.progress.configure(maximum=max(1,total),value=i))
            self.after(0,lambda:self.status.set("Tarama tamamlandı" if not self.stop_event.is_set() else "Tarama durduruldu"))
        finally:
            self.running=False

    def open_settings(self):
        w=tk.Toplevel(self); w.title("Solinaj Arşiv - Ayarlar"); w.geometry("720x520"); w.configure(bg="#07101b"); w.transient(self); w.grab_set()
        frame=ttk.Frame(w,style="Dark.TFrame",padding=16); frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="Tarama / Kayıt Klasörleri",style="Dark.TLabel",font=("Segoe UI",12,"bold")).pack(anchor="w")
        lb=tk.Listbox(frame,bg="#0a1420",fg="#e5f4ff",height=8,relief="flat"); lb.pack(fill="x",pady=6)
        for x in self.config_data.get("watch_folders",[]): lb.insert("end",x)
        row=ttk.Frame(frame,style="Dark.TFrame"); row.pack(fill="x")
        def add():
            p=filedialog.askdirectory(parent=w)
            if p: lb.insert("end",p)
        def rem():
            for i in reversed(lb.curselection()): lb.delete(i)
        ttk.Button(row,text="Klasör Ekle",style="Gray.TButton",command=add).pack(side="left",padx=(0,6))
        ttk.Button(row,text="Seçileni Sil",style="Gray.TButton",command=rem).pack(side="left")
        ttk.Label(frame,text="Bulut / Sync Klasörü",style="Dark.TLabel",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(16,4))
        cloud=tk.StringVar(value=self.config_data.get("cloud_root",str(Path.home()/"Sync")))
        crow=ttk.Frame(frame,style="Dark.TFrame"); crow.pack(fill="x")
        ttk.Entry(crow,textvariable=cloud).pack(side="left",fill="x",expand=True)
        ttk.Button(crow,text="Seç",style="Gray.TButton",command=lambda:cloud.set(filedialog.askdirectory(parent=w) or cloud.get())).pack(side="left",padx=(6,0))
        auto=tk.BooleanVar(value=self.config_data.get("auto_scan",True)); copy=tk.BooleanVar(value=self.config_data.get("copy_mode",True))
        ttk.Checkbutton(frame,text="Bilgisayar açıldığında / program başladığında otomatik tara",variable=auto).pack(anchor="w",pady=(16,4))
        ttk.Checkbutton(frame,text="Dosyaları kopyala (taşımak yerine)",variable=copy).pack(anchor="w")
        def save():
            self.config_data["watch_folders"]=list(lb.get(0,"end")); self.config_data["cloud_root"]=cloud.get(); self.config_data["auto_scan"]=auto.get(); self.config_data["copy_mode"]=copy.get(); save_config(self.config_data); w.destroy(); self.status.set("Ayarlar kaydedildi")
        ttk.Button(frame,text="KAYDET",style="Blue.TButton",command=save).pack(anchor="e",pady=(18,0))

    def _version_tuple(self,text):
        nums=re.findall(r"\d+",str(text))
        return tuple(int(x) for x in nums) if nums else (0,)

    def _version_text(self,ver):
        return ".".join(str(x) for x in ver)

    def _sha256_file(self,path):
        h=hashlib.sha256()
        with Path(path).open("rb") as f:
            for b in iter(lambda:f.read(1024*1024),b""):
                h.update(b)
        return h.hexdigest()

    def _update_search_roots(self):
        roots=[]
        for p in [Path.home()/"Downloads",Path.home()/"İndirilenler",Path.home()/"Desktop",Path.home()/"Masaüstü",BASE]:
            try:
                if p.exists() and p.is_dir() and p not in roots: roots.append(p)
            except Exception: pass
        return roots

    def _update_candidate_version(self,path):
        return self._version_tuple(path.name)

    def _find_update_candidates(self):
        out=[]
        current=Path(__file__).resolve()
        patterns=("*Solinaj*Arsiv*.zip","*Solinaj*Arşiv*.zip","*Solinaj*Arsiv*.py","*Solinaj*Arşiv*.py")
        seen=set()
        for root in self._update_search_roots():
            for pat in patterns:
                for p in root.glob(pat):
                    try:
                        rp=p.resolve()
                        if rp==current or rp in seen: continue
                        seen.add(rp); out.append((p.stat().st_mtime,p))
                    except Exception: pass
        out.sort(key=lambda x:x[0],reverse=True); return out

    def _extract_update_script(self,candidate):
        candidate=Path(candidate)
        if candidate.suffix.lower()==".py": return candidate,None
        if candidate.suffix.lower()!=".zip": raise ValueError("Desteklenmeyen güncelleme paketi")
        tmpdir=Path(tempfile.mkdtemp(prefix="solinaj_update_"))
        with zipfile.ZipFile(candidate,"r") as z:
            z.extractall(tmpdir)
        scripts=list(tmpdir.rglob("solinaj_arsivleyici.py"))
        if not scripts: scripts=list(tmpdir.rglob("*.py"))
        if not scripts:
            shutil.rmtree(tmpdir,ignore_errors=True); raise ValueError("ZIP içinde program dosyası bulunamadı")
        scripts.sort(key=lambda p:(p.name.lower()!="solinaj_arsivleyici.py",len(str(p))))
        return scripts[0],tmpdir

    def _read_script_version(self,script,candidate_name=""):
        try:
            txt=Path(script).read_text(encoding="utf-8",errors="ignore")
            m=re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',txt)
            if m: return self._version_tuple(m.group(1))
            m=re.search(r'APP_NAME\s*=\s*["\'][^"\']*?V\s*([0-9]+(?:\.[0-9]+)*)',txt,re.I)
            if m: return self._version_tuple(m.group(1))
        except Exception: pass
        return self._version_tuple(candidate_name)

    def _extract_update_icon(self, candidate):
        """Güncelleme ZIP'i içinde masaüstü simgesi varsa çıkarır."""
        candidate=Path(candidate)
        if candidate.suffix.lower()!='.zip':
            return None, None
        tmpdir=Path(tempfile.mkdtemp(prefix='solinaj_icon_'))
        try:
            with zipfile.ZipFile(candidate,'r') as z:
                names=z.namelist()
                ico_matches=[n for n in names if n.lower().endswith('.ico') and ('solinaj' in n.lower() or 'arsiv' in n.lower() or 'arşiv' in n.lower())]
                if not ico_matches:
                    shutil.rmtree(tmpdir,ignore_errors=True)
                    return None, None
                member=sorted(ico_matches,key=lambda n:(n.count('/'),len(n)))[0]
                z.extract(member,tmpdir)
                return tmpdir/member, tmpdir
        except Exception:
            shutil.rmtree(tmpdir,ignore_errors=True)
            return None, None

    def _desktop_shortcut_update_lines(self, icon_path):
        """GÜNCELLE butonu için masaüstü simgesini zorla yeniler."""
        ico=str(icon_path).replace("'","''")
        ps = (
            "$ErrorActionPreference='SilentlyContinue';"
            "$ico='"+ico+"';"
            "$appDir='"+str(BASE).replace("'","''")+"';"
            "$target=Join-Path $appDir 'solinaj_arsivleyici.py';"
            "$pythonw=Join-Path $appDir '.venv\\Scripts\\pythonw.exe';"
            "if(!(Test-Path $pythonw)){$c=Get-Command pythonw.exe -ErrorAction SilentlyContinue;if($c){$pythonw=$c.Source}};"
            "$desktop=[Environment]::GetFolderPath('Desktop');"
            "$roots=@($desktop);"
            "if($env:OneDrive){$roots+=@(Join-Path $env:OneDrive 'Desktop');$roots+=@(Join-Path $env:OneDrive 'Masaüstü');$roots+=@(Join-Path $env:OneDrive 'Masaustu')};"
            "$roots=$roots|Select-Object -Unique;"
            "$ws=New-Object -ComObject WScript.Shell;"
            "foreach($r in $roots){if($r -and (Test-Path $r)){Get-ChildItem -LiteralPath $r -Filter '*.lnk' -File -ErrorAction SilentlyContinue|Where-Object{$_.BaseName -match '(?i)solinaj'}|Remove-Item -Force -ErrorAction SilentlyContinue}};"
            "if((Test-Path $pythonw) -and (Test-Path $target)){"
            "$lnk=Join-Path $desktop 'Solinaj Arşiv.lnk';"
            "$s=$ws.CreateShortcut($lnk);$s.TargetPath=$pythonw;$s.Arguments='\"'+$target+'\"';$s.WorkingDirectory=$appDir;$s.IconLocation=$ico+',0';$s.Description='Solinaj Arşiv';$s.Save()};"
            "Start-Process -FilePath ($env:SystemRoot+'\\System32\\ie4uinit.exe') -ArgumentList '-show' -WindowStyle Hidden -ErrorAction SilentlyContinue"
        )
        return ["powershell.exe -NoProfile -ExecutionPolicy Bypass -Command " + subprocess.list2cmdline([ps])]

    def start_self_update(self):
        if self.running:
            if not messagebox.askyesno(APP_NAME,"Tarama şu anda çalışıyor. Taramayı durdurup güncellemeye geçilsin mi?"):
                return
            self.stop_scan()
        self.status.set("En son sürüm aranıyor...")
        try:
            self.update_btn.configure(state='disabled')
        except Exception:
            pass
        threading.Thread(target=self._self_update_worker,daemon=True).start()

    def _download_update_bytes(self, url, timeout=60):
        req=urllib.request.Request(url,headers={"User-Agent":"Solinaj-Arsivleyici/"+APP_VERSION})
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return r.read()

    def _get_online_manifest(self):
        raw=self._download_update_bytes(UPDATE_MANIFEST_URL,timeout=15)
        data=json.loads(raw.decode("utf-8-sig"))
        if not isinstance(data,dict):
            raise ValueError("Güncelleme bilgisi geçersiz.")
        for key in ("version","script_url","script_sha256"):
            if not data.get(key):
                raise ValueError("Güncelleme manifestinde eksik alan: "+key)
        return data

    def _self_update_worker(self):
        try:
            self.add_log_ui("İNTERNET GÜNCELLEME: GitHub kontrol ediliyor...")
            manifest=self._get_online_manifest()
            remote_ver=self._version_tuple(str(manifest["version"]))
            current_ver=self._version_tuple(APP_VERSION)

            if remote_ver <= current_ver:
                self.after(0,lambda:messagebox.showinfo(
                    APP_NAME,
                    f"Program güncel.\n\nMevcut sürüm: V{APP_VERSION}"
                ))
                self.after(0,lambda:self.status.set("Program güncel"))
                return

            notes=str(manifest.get("notes","Yeni güncelleme hazır."))
            answer=messagebox.askyesno(
                APP_NAME,
                f"Yeni sürüm bulundu: V{manifest['version']}\n\n{notes}\n\n"
                "Güncelleme internetten indirilsin ve kurulsun mu?"
            )
            if not answer:
                self.after(0,lambda:self.status.set("Güncelleme iptal edildi"))
                return

            self.after(0,lambda:self.status.set("Güncelleme internetten indiriliyor..."))
            raw=self._download_update_bytes(str(manifest["script_url"]),timeout=60)

            actual=hashlib.sha256(raw).hexdigest().lower()
            expected=str(manifest["script_sha256"]).strip().lower()
            if actual != expected:
                raise ValueError("Güncelleme doğrulanamadı. SHA-256 değeri eşleşmiyor.")

            decoded=raw.decode("utf-8-sig")
            m=re.search(r'APP_VERSION\s*=\s*["\\\']([^"\\\']+)["\\\']',decoded)
            if not m:
                raise ValueError("İndirilen güncellemede sürüm bilgisi bulunamadı.")
            downloaded_ver=self._version_tuple(m.group(1))
            if downloaded_ver != remote_ver:
                raise ValueError("İndirilen dosyanın sürümü manifest ile eşleşmiyor.")

            staged=BASE/'solinaj_arsivleyici_UPDATE_NEW.py'
            staged.write_bytes(raw)

            staged_icon=None
            final_icon=BASE/'Solinaj_Arsiv.ico'
            icon_url=manifest.get("icon_url")
            icon_sha=manifest.get("icon_sha256")
            if icon_url and icon_sha:
                icon_raw=self._download_update_bytes(str(icon_url),timeout=60)
                if hashlib.sha256(icon_raw).hexdigest().lower()!=str(icon_sha).strip().lower():
                    raise ValueError("Masaüstü simgesi doğrulanamadı.")
                staged_icon=BASE/'Solinaj_Arsiv_UPDATE_NEW.ico'
                staged_icon.write_bytes(icon_raw)

            backup=BASE/'solinaj_arsivleyici_UPDATE_BACKUP.py'
            updater=BASE/'_solinaj_online_update.ps1'
            current=Path(__file__).resolve()

            ps=[
                "$ErrorActionPreference='Stop'",
                f"$pidToWait={os.getpid()}",
                "while(Get-Process -Id $pidToWait -ErrorAction SilentlyContinue){Start-Sleep -Milliseconds 500}",
                f"Copy-Item -LiteralPath {repr(str(current))} -Destination {repr(str(backup))} -Force",
                f"Copy-Item -LiteralPath {repr(str(staged))} -Destination {repr(str(current))} -Force",
                f"Remove-Item -LiteralPath {repr(str(staged))} -Force -ErrorAction SilentlyContinue",
            ]

            if staged_icon:
                ps += [
                    f"Copy-Item -LiteralPath {repr(str(staged_icon))} -Destination {repr(str(final_icon))} -Force",
                    f"Remove-Item -LiteralPath {repr(str(staged_icon))} -Force -ErrorAction SilentlyContinue",
                    "$desktop=[Environment]::GetFolderPath('Desktop')",
                    "$roots=@($desktop)",
                    "if($env:OneDrive){$roots+=@(Join-Path $env:OneDrive 'Desktop');$roots+=@(Join-Path $env:OneDrive 'Masaüstü');$roots+=@(Join-Path $env:OneDrive 'Masaustu')}",
                    "$roots=$roots|Select-Object -Unique",
                    "$ws=New-Object -ComObject WScript.Shell",
                    "foreach($r in $roots){if($r -and (Test-Path $r)){Get-ChildItem -LiteralPath $r -Filter '*.lnk' -File -ErrorAction SilentlyContinue|Where-Object{$_.BaseName -match '(?i)solinaj'}|Remove-Item -Force -ErrorAction SilentlyContinue}}",
                    f"$appDir={repr(str(BASE))}",
                    "$target=Join-Path $appDir 'solinaj_arsivleyici.py'",
                    "$pythonw=Join-Path $appDir '.venv\\Scripts\\pythonw.exe'",
                    "if(!(Test-Path $pythonw)){$c=Get-Command pythonw.exe -ErrorAction SilentlyContinue;if($c){$pythonw=$c.Source}}",
                    f"$ico={repr(str(final_icon))}",
                    "if((Test-Path $pythonw) -and (Test-Path $target)){"
                    "$lnk=Join-Path $desktop 'Solinaj Arşiv.lnk';"
                    "$s=$ws.CreateShortcut($lnk);$s.TargetPath=$pythonw;$s.Arguments='\"'+$target+'\"';"
                    "$s.WorkingDirectory=$appDir;$s.IconLocation=$ico+',0';$s.Description='Solinaj Arşiv';$s.Save()}",
                    "Start-Process -FilePath ($env:SystemRoot+'\\System32\\ie4uinit.exe') -ArgumentList '-show' -WindowStyle Hidden -ErrorAction SilentlyContinue",
                ]

            ps += [
                "Add-Type -AssemblyName System.Windows.Forms",
                f"[System.Windows.Forms.MessageBox]::Show('V{manifest['version']} internet güncellemesi tamamlandı. Programı masaüstündeki Solinaj Arşiv simgesinden yeniden açın.','Solinaj Arşivleyici')|Out-Null",
                "Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue",
            ]
            updater.write_text("\r\n".join(ps)+"\r\n",encoding="utf-8-sig")

            self.after(0,lambda:self.status.set(f"V{manifest['version']} kuruluyor..."))
            self.after(0,lambda:messagebox.showinfo(
                APP_NAME,
                f"V{manifest['version']} indirildi ve doğrulandı.\n\n"
                "Program kapanacak ve güncelleme kurulacak.\n"
                "Kurulum bitince masaüstündeki Solinaj Arşiv simgesinden yeniden açın."
            ))
            time.sleep(0.5)

            subprocess.Popen(
                ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(updater)],
                cwd=str(BASE),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
            )
            self.after(0,self.destroy)

        except urllib.error.URLError as e:
            self.add_log_ui(f"İNTERNET GÜNCELLEME HATASI: {e}")
            self.after(0,lambda e=e:messagebox.showerror(APP_NAME,f"İnternete bağlanılamadı:\n{e}"))
            self.after(0,lambda:self.status.set("İnternet bağlantısı hatası"))
        except Exception as e:
            self.add_log_ui(f"GÜNCELLEME HATASI: {e}")
            self.after(0,lambda e=e:messagebox.showerror(APP_NAME,f"Güncelleme sırasında hata oluştu:\n{e}"))
            self.after(0,lambda:self.status.set("Güncelleme hatası"))
        finally:
            try:
                self.after(0,lambda:self.update_btn.configure(state='normal'))
            except Exception:
                pass

    def add_watch(self):
        pass

if __name__=="__main__":
    App().mainloop()
