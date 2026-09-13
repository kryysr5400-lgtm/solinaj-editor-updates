import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import subprocess, threading, shutil, os, re, json, time, tempfile, urllib.request, hashlib, sys, ctypes

from modules.versioning import APP_NAME, APP_VERSION

BG = "#111317"
PANEL = "#1b1e24"
PANEL2 = "#232730"
TEXT = "#f5f7fa"
MUTED = "#939aa6"
ACCENT = "#00e3bd"
ACCENT_HOVER = "#00cdaa"
BORDER = "#303641"
RED = "#ff5d73"


def fmt_time(sec):
    sec=max(0, int(float(sec or 0)))
    return f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d}"


def find_ffmpeg_pair():
    root=Path(__file__).resolve().parent
    candidates=[
        root/'ffmpeg.exe', root/'bin/ffmpeg.exe', root/'ffmpeg/bin/ffmpeg.exe',
        root/'tools/ffmpeg/bin/ffmpeg.exe', root/'tools/ffmpeg.exe'
    ]
    exe=next((p for p in candidates if p.exists()), None)
    if exe is None:
        w=shutil.which('ffmpeg') or shutil.which('ffmpeg.exe')
        exe=Path(w) if w else None
    if exe is None:
        try:
            for p in root.rglob('ffmpeg.exe'):
                exe=p; break
        except Exception:
            pass
    if exe is None:
        return None, None
    probe=exe.with_name('ffprobe.exe') if exe.suffix.lower()=='.exe' else exe.with_name('ffprobe')
    if not probe.exists():
        w=shutil.which('ffprobe') or shutil.which('ffprobe.exe')
        probe=Path(w) if w else None
    return str(exe), str(probe) if probe else None


def probe_duration(path, ffmpeg, ffprobe):
    if ffprobe:
        p=subprocess.run([ffprobe,'-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],
                         capture_output=True,text=True,errors='ignore',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            return float((p.stdout or '').strip())
        except Exception:
            pass
    p=subprocess.run([ffmpeg,'-i',str(path)],capture_output=True,text=True,errors='ignore',
                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    m=re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', (p.stderr or '')+(p.stdout or ''))
    if m:
        return int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3))
    raise RuntimeError('Video süresi okunamadı.')


# Windows taskbar kimligi: Arsivleyici/Python ile ayni gruba dusmesini engeller.
if os.name == "nt":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Solinaj.Shorts.2.8")
    except Exception:
        pass



class ShortsMaker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} V{APP_VERSION}")
        try:
            icon_path = str(Path(__file__).resolve().parent / "solinaj_shorts.ico")
            self.iconbitmap(default=icon_path)
            self.after(250, lambda: self.iconbitmap(default=icon_path))
        except Exception:
            pass
        self.geometry('1220x790')
        self.minsize(1000,680)
        self.configure(bg=BG)
        self.video=tk.StringVar()
        self.duration=0.0
        self.count=tk.IntVar(value=5)
        self.short_len=tk.IntVar(value=45)
        self.layout=tk.StringVar(value='Tam görüntü + bulanık arka plan')
        self.status=tk.StringVar(value='Hazır • Uzun videonu seç ve tek tuşla Shorts oluştur.')
        self.progress=tk.DoubleVar(value=0)
        self.progress_detail=tk.StringVar(value='0% • Bekliyor')
        self.output_dir=None
        self.settings_path=Path(__file__).resolve().parent/'user_settings.json'
        self.output_base=tk.StringVar(value='Kayıt klasörü henüz seçilmedi')
        self.results=[]
        self.busy=False
        self.low_resource=tk.BooleanVar(value=True)
        self.active_process=None
        try:
            self._style(); self._ui()
        except Exception as e:
            self._startup_error_screen(e)
            return
        self.protocol('WM_DELETE_WINDOW',self._clean_exit)
        self.after(250,self._startup)

    def _popen_light(self,cmd,**kwargs):
        flags=kwargs.pop('creationflags',0)
        if os.name=='nt':
            flags |= getattr(subprocess,'CREATE_NO_WINDOW',0)
            flags |= getattr(subprocess,'IDLE_PRIORITY_CLASS',0)
        kwargs['creationflags']=flags
        p=subprocess.Popen(cmd,**kwargs)
        self.active_process=p
        return p

    def _run_light(self,cmd,**kwargs):
        flags=kwargs.pop('creationflags',0)
        if os.name=='nt':
            flags |= getattr(subprocess,'CREATE_NO_WINDOW',0)
            flags |= getattr(subprocess,'IDLE_PRIORITY_CLASS',0)
        timeout=kwargs.pop('timeout',None)
        capture=kwargs.pop('capture_output',False)
        if capture:
            kwargs['stdout']=subprocess.PIPE; kwargs['stderr']=subprocess.PIPE
        p=subprocess.Popen(cmd,creationflags=flags,**kwargs)
        self.active_process=p
        try:
            out,err=p.communicate(timeout=timeout)
        finally:
            self.active_process=None
        class Result: pass
        r = Result()
        r.args = cmd
        r.returncode = p.returncode
        r.stdout = out
        r.stderr = err
        return r

    def _startup_error_screen(self, err):
        try:
            for w in self.winfo_children():
                w.destroy()
            self.configure(bg="#111317")
            tk.Label(self,text="SOLINAJ SHORTS",bg="#111317",fg="white",
                     font=("Segoe UI",18,"bold")).pack(pady=(60,15))
            tk.Label(self,text="Arayüz açılırken bir hata oluştu.",bg="#111317",fg="#ff808f",
                     font=("Segoe UI",12,"bold")).pack()
            tk.Label(self,text=str(err),bg="#111317",fg="#d7dbe1",
                     font=("Segoe UI",10),wraplength=850,justify="left").pack(padx=40,pady=20)
            log=Path(__file__).resolve().parent/"shorts_startup_error.txt"
            log.write_text(str(err),encoding="utf-8")
        except Exception:
            pass

    def _style(self):
        s=ttk.Style(self)
        try:s.theme_use('clam')
        except:pass
        s.configure('Treeview',background=PANEL2,fieldbackground=PANEL2,foreground=TEXT,rowheight=31,borderwidth=0,font=('Segoe UI',10))
        s.configure('Treeview.Heading',background=PANEL,foreground='#cbd0d8',relief='flat',font=('Segoe UI',9,'bold'))
        s.map('Treeview',background=[('selected','#315a55')])
        s.configure('Horizontal.TProgressbar',troughcolor='#242a32',background=ACCENT,bordercolor='#242a32')
        s.configure('TCombobox',fieldbackground=PANEL2,background=PANEL2,foreground=TEXT,arrowcolor=TEXT)

    def btn(self,parent,text,cmd,accent=False,width=None):
        return tk.Button(parent,text=text,command=cmd,bg=ACCENT if accent else '#2a2f38',fg='#06110f' if accent else TEXT,
                         activebackground=ACCENT_HOVER if accent else '#353b46',activeforeground='#06110f' if accent else TEXT,
                         relief='flat',bd=0,font=('Segoe UI',10,'bold' if accent else 'normal'),padx=15,pady=9,cursor='hand2',width=width)

    def _ui(self):
        top=tk.Frame(self,bg='#171a1f',height=58,highlightthickness=1,highlightbackground=BORDER)
        top.pack(fill='x'); top.pack_propagate(False)
        tk.Label(top,text='SOLINAJ SHORTS',bg='#171a1f',fg=TEXT,font=('Segoe UI',14,'bold')).pack(side='left',padx=20)
        tk.Label(top,text=f'V{APP_VERSION}',bg='#171a1f',fg=MUTED,font=('Segoe UI',9)).pack(side='left')
        self.update_btn=self.btn(top,'↻ Güncelle',self.check_update)
        self.update_btn.pack(side='right',padx=14,pady=10)

        body=tk.Frame(self,bg=BG); body.pack(fill='both',expand=True,padx=18,pady=16)

        hero=tk.Frame(body,bg=PANEL,highlightthickness=1,highlightbackground=BORDER)
        hero.pack(fill='x')
        tk.Label(hero,text='1. UZUN VİDEONU EKLE',bg=PANEL,fg=TEXT,font=('Segoe UI',12,'bold')).pack(anchor='w',padx=18,pady=(15,7))
        row=tk.Frame(hero,bg=PANEL); row.pack(fill='x',padx=18,pady=(0,14))
        self.path_entry=tk.Entry(row,textvariable=self.video,bg='#111419',fg='#dfe3e8',insertbackground='white',relief='flat',font=('Segoe UI',10))
        self.path_entry.pack(side='left',fill='x',expand=True,ipady=9)
        self.btn(row,'VİDEO SEÇ',self.pick_video,accent=True).pack(side='left',padx=(10,0))

        settings=tk.Frame(body,bg=PANEL,highlightthickness=1,highlightbackground=BORDER)
        settings.pack(fill='x',pady=(12,0))
        tk.Label(settings,text='2. SHORT AYARLARI',bg=PANEL,fg=TEXT,font=('Segoe UI',12,'bold')).pack(anchor='w',padx=18,pady=(14,8))
        sr=tk.Frame(settings,bg=PANEL); sr.pack(fill='x',padx=18,pady=(0,14))
        self._field(sr,'Kaç Short?',self.count,[3,5,8,10]).pack(side='left',padx=(0,18))
        self._field(sr,'Short Süresi',self.short_len,[30,45,60],suffix=' sn').pack(side='left',padx=(0,18))
        lf=tk.Frame(sr,bg=PANEL)
        tk.Label(lf,text='9:16 Görünüm',bg=PANEL,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(0,4))
        ttk.Combobox(lf,textvariable=self.layout,state='readonly',values=['Tam görüntü + bulanık arka plan','Merkez kırp'],width=31).pack(ipady=5)
        lf.pack(side='left')
        self.make_btn=self.btn(sr,'⚡ OTOMATİK SHORT OLUŞTUR',self.start_make,accent=True)
        self.make_btn.pack(side='right',padx=(18,0),pady=(13,0))

        save_row=tk.Frame(settings,bg=PANEL); save_row.pack(fill='x',padx=18,pady=(0,14))
        tk.Label(save_row,text='Kayıt Yeri:',bg=PANEL,fg=MUTED,font=('Segoe UI',9)).pack(side='left')
        self.output_label=tk.Label(save_row,textvariable=self.output_base,bg=PANEL,fg=TEXT,font=('Segoe UI',9),anchor='w')
        self.output_label.pack(side='left',fill='x',expand=True,padx=(8,10))
        self.btn(save_row,'📁 Değiştir',self.change_output_folder).pack(side='right')
        tk.Checkbutton(save_row,text='Ultra Hafif Mod • AÇIK',variable=self.low_resource,state='disabled',
                       bg=PANEL,fg=TEXT,disabledforeground='#9ee7da',selectcolor=BG,
                       activebackground=PANEL,activeforeground=TEXT,font=('Segoe UI',9,'bold')).pack(side='right',padx=(0,14))

        mid=tk.Frame(body,bg=BG); mid.pack(fill='both',expand=True,pady=(12,0))
        left=tk.Frame(mid,bg=PANEL,highlightthickness=1,highlightbackground=BORDER)
        left.pack(side='left',fill='both',expand=True)
        tk.Label(left,text='3. HAZIR SHORTLAR',bg=PANEL,fg=TEXT,font=('Segoe UI',12,'bold')).pack(anchor='w',padx=14,pady=(12,8))
        self.tree=ttk.Treeview(left,columns=('n','start','end','score','file'),show='headings')
        for c,t,w in [('n','#',45),('start','Başlangıç',90),('end','Bitiş',90),('score','Hareket',80),('file','Dosya',400)]:
            self.tree.heading(c,text=t); self.tree.column(c,width=w,stretch=(c=='file'),anchor='center' if c!='file' else 'w')
        self.tree.pack(fill='both',expand=True,padx=12,pady=(0,8))
        self.tree.bind('<Double-1>',lambda e:self.open_selected())
        acts=tk.Frame(left,bg=PANEL); acts.pack(fill='x',padx=12,pady=(0,12))
        self.btn(acts,'▶ Seçileni Aç',self.open_selected).pack(side='left')
        self.btn(acts,'📁 Klasörü Aç',self.open_folder).pack(side='left',padx=7)
        self.btn(acts,'💬 ChatGPT Paketi',self.chatgpt_package).pack(side='left')

        info=tk.Frame(mid,bg='#171a1f',width=290,highlightthickness=1,highlightbackground=BORDER)
        info.pack(side='left',fill='y',padx=(12,0)); info.pack_propagate(False)
        tk.Label(info,text='NASIL ÇALIŞIYOR?',bg='#171a1f',fg=TEXT,font=('Segoe UI',11,'bold')).pack(anchor='w',padx=16,pady=(16,10))
        text=("Program videoyu otomatik tarar.\n\n"
              "• Sahne + sessizlik analizini tek geçişte yapar\n"
              "• Hareketli bölümleri hızlıca puanlar\n"
              "• İlerlemeyi Windows kopyalama çubuğu gibi gösterir\n"
              "• En iyi anlardan Short çıkarır\n"
              "• 9:16 dikey MP4 hazırlar\n\n"
              "ChatGPT Paketi düğmesi, çıkan shortların zamanlarını ve dosya listesini hazırlar. Bulut AI kullanımı için API bağlantısı gerekir; ana analiz internet beklemeden yerelde hızlı çalışır. Beğendiğin shortları bu sohbete at; başlık, kanca ve açıklamayı birlikte tamamlarız.")
        tk.Label(info,text=text,bg='#171a1f',fg='#b8bec7',font=('Segoe UI',10),justify='left',wraplength=255).pack(anchor='w',padx=16)

        bottom=tk.Frame(self,bg='#171a1f',height=82,highlightthickness=1,highlightbackground=BORDER)
        bottom.pack(fill='x',side='bottom'); bottom.pack_propagate(False)
        prow=tk.Frame(bottom,bg='#171a1f'); prow.pack(fill='x',padx=18,pady=(10,3))
        self.progress_bar=ttk.Progressbar(prow,variable=self.progress,maximum=100,mode='determinate')
        self.progress_bar.pack(side='left',fill='x',expand=True)
        tk.Label(prow,textvariable=self.progress_detail,bg='#171a1f',fg='#dfe4ea',
                 font=('Segoe UI',9,'bold'),width=18,anchor='e').pack(side='right',padx=(12,0))
        tk.Label(bottom,textvariable=self.status,bg='#171a1f',fg='#c7ccd4',
                 font=('Segoe UI',9),anchor='w').pack(fill='x',padx=18,pady=(0,5))

    def _field(self,parent,title,var,values,suffix=''):
        f=tk.Frame(parent,bg=PANEL)
        tk.Label(f,text=title,bg=PANEL,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(0,4))
        vals=[f'{x}{suffix}' for x in values]
        cb=ttk.Combobox(f,state='readonly',values=vals,width=13)
        current=f'{var.get()}{suffix}'; cb.set(current)
        def changed(e):
            raw=cb.get().replace(suffix,'').strip()
            try:var.set(int(raw))
            except:pass
        cb.bind('<<ComboboxSelected>>',changed); cb.pack(ipady=5)
        return f

    def _load_user_settings(self):
        try:
            if self.settings_path.exists():
                data=json.loads(self.settings_path.read_text(encoding='utf-8-sig'))
                folder=str(data.get('output_base','')).strip()
                if folder:
                    self.output_base.set(folder)
                else:
                    self.output_base.set('Kayıt klasörü henüz seçilmedi')
            else:
                self.output_base.set('Kayıt klasörü henüz seçilmedi')
        except Exception:
            self.output_base.set('Kayıt klasörü henüz seçilmedi')

    def _save_user_settings(self):
        try:
            folder=self.output_base.get().strip()
            self.settings_path.write_text(json.dumps({'output_base':folder},ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as e:
            messagebox.showwarning('Ayar kaydedilemedi',str(e))

    def change_output_folder(self, first_time=False):
        current=self.output_base.get().strip()
        initial=current if current and current != 'Kayıt klasörü henüz seçilmedi' else str(Path.home())
        folder=filedialog.askdirectory(title='Shortların kayıt klasörünü seç',initialdir=initial,mustexist=True)
        if not folder:
            if first_time and not self.output_base.get().strip():
                self.status.set('Short oluşturmadan önce kayıt yerini seçmelisin.')
            return False
        self.output_base.set(folder)
        self._save_user_settings()
        self.status.set(f'Kayıt yeri kaydedildi • {folder}')
        return True

    def _startup(self):
        self._load_user_settings()
        self.update_idletasks()
        try:
            self.deiconify()
            self.lift()
            self.after(700, lambda:self.attributes('-topmost', False))
        except Exception:
            pass
        ff,fp=find_ffmpeg_pair()
        if ff:self.status.set(f'Hazır • FFmpeg bulundu • V{APP_VERSION}')
        else:self.status.set('FFmpeg bulunamadı. Mevcut Solinaj Editor FFmpeg kurulumunu kontrol et.')
        marker=Path(__file__).resolve().parent/'update_success.json'
        if marker.exists():
            try:
                data=json.loads(marker.read_text(encoding='utf-8-sig')); marker.unlink(missing_ok=True)
                self.status.set(f"Güncelleme tamamlandı • V{data.get('version',APP_VERSION)}")
            except:pass

    def pick_video(self):
        p=filedialog.askopenfilename(title='Uzun videoyu seç',filetypes=[('Video','*.mp4 *.mkv *.mov *.avi *.webm *.m4v'),('Tüm dosyalar','*.*')])
        if not p:return
        self.video.set(p); self.results=[]; self._clear_tree()
        ff,fp=find_ffmpeg_pair()
        if not ff:
            messagebox.showerror('FFmpeg yok','FFmpeg bulunamadı.'); return
        try:
            self.duration=probe_duration(p,ff,fp)
            self.status.set(f'Video hazır • Süre {fmt_time(self.duration)} • Otomatik Short Oluştur düğmesine bas.')
        except Exception as e:
            messagebox.showerror('Video okunamadı',str(e))

    def _clear_tree(self):
        for i in self.tree.get_children():self.tree.delete(i)

    def start_make(self):
        p=Path(self.video.get().strip())
        if not p.exists():
            messagebox.showwarning('Video seç','Önce uzun videonu seç.'); return
        if self.busy:return
        current_out=self.output_base.get().strip()
        if not current_out or current_out == 'Kayıt klasörü henüz seçilmedi':
            if not self.change_output_folder(first_time=True): return
        ff,fp=find_ffmpeg_pair()
        if not ff:
            messagebox.showerror('FFmpeg yok','FFmpeg bulunamadı.'); return
        self.busy=True; self.make_btn.config(state='disabled',text='ANALİZ EDİLİYOR...'); self.progress.set(1); self.progress_detail.set('1% • Başlatılıyor'); self._clear_tree(); self.results=[]
        threading.Thread(target=self._worker,args=(p,ff,fp),daemon=True).start()

    def _ui_status(self,text,pct=None,detail=None):
        self.after(0,lambda:self.status.set(text))
        if pct is not None:
            pct=max(0,min(100,float(pct)))
            self.after(0,lambda p=pct:self.progress.set(p))
            d=detail if detail is not None else f'{int(round(pct))}%'
            self.after(0,lambda x=d:self.progress_detail.set(x))

    def _ffmpeg_progress_capture(self,cmd,total_duration,start_pct,end_pct,label):
        """FFmpeg ilerlemesini gerçek zamanlı okuyup Windows tarzı yüzde çubuğuna yansıtır."""
        cmd=list(cmd)
        if '-progress' not in cmd:
            cmd[1:1]=['-progress','pipe:1','-nostats']
        flags=0
        if os.name == 'nt':
            flags |= getattr(subprocess,'CREATE_NO_WINDOW',0)
            flags |= getattr(subprocess,'IDLE_PRIORITY_CLASS',0)

        err_file=tempfile.TemporaryFile(mode='w+',encoding='utf-8',errors='ignore')
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err_file,text=True,errors='ignore',
                           bufsize=1,creationflags=flags)
        self.active_process=p
        last_pct=-1
        try:
            if p.stdout:
                for raw in p.stdout:
                    line=raw.strip()
                    seconds=None
                    if line.startswith('out_time_us=') or line.startswith('out_time_ms='):
                        try:
                            seconds=float(line.split('=',1)[1])/1000000.0
                        except Exception:
                            seconds=None
                    elif line.startswith('out_time='):
                        try:
                            hh,mm,ss=line.split('=',1)[1].split(':')
                            seconds=float(hh)*3600+float(mm)*60+float(ss)
                        except Exception:
                            seconds=None
                    if seconds is not None and total_duration and total_duration>0:
                        frac=max(0.0,min(1.0,seconds/float(total_duration)))
                        pct=start_pct+(end_pct-start_pct)*frac
                        ip=int(pct)
                        if ip!=last_pct:
                            last_pct=ip
                            self._ui_status(label,pct,f'{ip}% • {fmt_time(seconds)} / {fmt_time(total_duration)}')
            p.wait()
        finally:
            self.active_process=None
        err_file.seek(0)
        err=err_file.read()
        err_file.close()

        class Result: pass
        r=Result()
        r.returncode=p.returncode
        r.stderr=err
        r.stdout=''
        return r

    def _analyze_fast(self,path,ff,dur):
        """Sahne değişimi + sessizlikleri tek FFmpeg geçişinde toplar."""
        cmd=[ff,'-hide_banner','-threads','1','-i',str(path),
             '-vf',r'scale=320:-2,fps=2,select=gt(scene\,0.22),showinfo',
             '-af','silencedetect=noise=-36dB:d=1.2',
             '-f','null','-']
        p=self._ffmpeg_progress_capture(
            cmd,dur,5,34,
            'Hızlı analiz • sahne ve sessizlikler tek geçişte taranıyor...'
        )
        log=p.stderr or ''
        scenes=[]
        for m in re.finditer(r'pts_time:([0-9.]+)',log):
            try: scenes.append(float(m.group(1)))
            except Exception: pass
        if len(scenes)>2500:
            step=max(1,len(scenes)//2500)
            scenes=scenes[::step]

        starts=[float(x) for x in re.findall(r'silence_start:\s*([0-9.]+)',log)]
        ends=[float(x) for x in re.findall(r'silence_end:\s*([0-9.]+)',log)]
        silences=[]
        for i,st in enumerate(starts):
            en=ends[i] if i<len(ends) else dur
            if en>st:
                silences.append((st,en))
        return scenes,silences

    def _worker(self,path,ff,fp):
        try:
            dur=probe_duration(path,ff,fp); self.duration=dur
            clip_len=max(15,min(int(self.short_len.get()),max(15,int(dur))))
            n=max(1,min(10,int(self.count.get())))
            self._ui_status('Hızlı analiz başlıyor...',4,'4% • Hazırlanıyor')
            scenes,silences=self._analyze_fast(path,ff,dur)
            self._ui_status(f'{len(scenes)} hareket noktası bulundu • en iyi Short anları seçiliyor...',36,'36% • Adaylar seçiliyor')
            picks=self._pick_windows(dur,clip_len,n,scenes,silences)
            self._ui_status(f'{len(picks)} güçlü Short adayı bulundu.',40,'40% • Analiz tamam')
            stamp=time.strftime('%Y%m%d_%H%M%S')
            folder=self.output_base.get().strip()
            if not folder or folder == 'Kayıt klasörü henüz seçilmedi':
                raise RuntimeError('Önce kayıt klasörünü seç.')
            base=Path(folder)
            out=base/f'{path.stem}_{stamp}'
            try:
                out.mkdir(parents=True,exist_ok=True)
            except Exception as e:
                raise RuntimeError(f'Kayıt klasörü oluşturulamadı: {e}')
            self.output_dir=out
            rows=[]
            total=len(picks)
            for idx,(start,score) in enumerate(picks,1):
                length=min(clip_len,max(1,dur-start))
                target=out/f'Solinaj_Short_{idx:02d}_{int(start)}s.mp4'
                base_pct=40+(idx-1)/max(1,total)*58
                end_pct=40+idx/max(1,total)*58
                self._ui_status(f'Short {idx}/{total} hazırlanıyor • {fmt_time(start)}...',base_pct,
                                f'{int(base_pct)}% • Short {idx}/{total}')
                self._export_short(path,target,start,length,ff,base_pct,end_pct,idx,total)
                rows.append({'no':idx,'start':start,'end':start+length,'score':score,'file':str(target)})
            self.results=rows
            meta={'source':str(path),'duration':dur,'short_length':clip_len,'created_at':time.strftime('%Y-%m-%d %H:%M:%S'),'results':rows}
            (out/'shorts_analiz.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
            self.after(0,self._fill_tree)
            self._ui_status(f'Tamamlandı • {len(rows)} Short hazır • {out}',100,'100% • Tamamlandı')
        except Exception as e:
            self.after(0,lambda:messagebox.showerror('Short oluşturulamadı',str(e)))
            self._ui_status('İşlem durdu.',0)
        finally:
            self.active_process=None
            self.busy=False
            self.after(0,lambda:self.make_btn.config(state='normal',text='⚡ OTOMATİK SHORT OLUŞTUR'))

    def _scene_times(self,path,ff):
        cmd=[ff,'-hide_banner','-threads','1','-i',str(path),'-vf',r'scale=320:-2,fps=2,select=gt(scene\,0.22),showinfo','-an','-f','null','-']
        p=self._run_light(cmd,capture_output=True,text=True,errors='ignore',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        text=(p.stderr or '')+(p.stdout or '')
        vals=[]
        for m in re.finditer(r'pts_time:([0-9.]+)',text):
            try:vals.append(float(m.group(1)))
            except:pass
        # Çok uzun videolarda binlerce nokta çıkarsa hafızayı gereksiz doldurma.
        if len(vals)>2500:
            step=max(1,len(vals)//2500); vals=vals[::step]
        return vals

    def _silences(self,path,ff):
        cmd=[ff,'-hide_banner','-threads','1','-i',str(path),'-af','silencedetect=noise=-36dB:d=1.2','-vn','-f','null','-']
        p=self._run_light(cmd,capture_output=True,text=True,errors='ignore',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        text=(p.stderr or '')+(p.stdout or '')
        starts=[float(x) for x in re.findall(r'silence_start:\s*([0-9.]+)',text)]
        ends=[float(x) for x in re.findall(r'silence_end:\s*([0-9.]+)',text)]
        pairs=[]
        for i,st in enumerate(starts):
            en=ends[i] if i<len(ends) else self.duration
            if en>st:pairs.append((st,en))
        return pairs

    def _pick_windows(self,dur,length,n,scenes,silences):
        if dur<=length:return [(0.0,100.0)]
        step=max(5,length/3)
        candidates=[]
        t=0.0
        while t<=dur-length:
            en=t+length
            sc=sum(1 for x in scenes if t<=x<=en)
            silent=0.0
            for a,b in silences:
                silent+=max(0,min(en,b)-max(t,a))
            density=sc/max(1,length)
            score=density*100 - (silent/length)*35
            # Orta kısımda küçük bir bonus; intro/outro sessizliklerine saplanmasın.
            if dur>length*2 and length<t<dur-length*1.2:score+=1.5
            candidates.append((score,t))
            t+=step
        if not candidates:
            candidates=[(0.0,0.0)]
        candidates.sort(reverse=True)
        chosen=[]
        min_gap=max(8,length*0.65)
        for score,t in candidates:
            if all(abs(t-x)>min_gap for x,_ in chosen):
                chosen.append((t,score))
            if len(chosen)>=n:break
        if len(chosen)<n:
            for i in range(n):
                t=max(0,min(dur-length,(dur-length)*(i+1)/(n+1)))
                if all(abs(t-x)>max(3,length*.3) for x,_ in chosen):chosen.append((t,0.0))
                if len(chosen)>=n:break
        chosen.sort(key=lambda x:x[0])
        return [(round(t,2),round(score,2)) for t,score in chosen[:n]]

    def _export_short(self,src,dst,start,length,ff,start_pct,end_pct,idx,total):
        if self.layout.get().startswith('Tam görüntü'):
            vf=("[0:v]split=2[bg][fg];"
                "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=18:6[bg2];"
                "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg2];"
                "[bg2][fg2]overlay=(W-w)/2:(H-h)/2,setsar=1[v]")
            cmd=[ff,'-y','-ss',str(start),'-t',str(length),'-i',str(src),'-filter_complex',vf,'-map','[v]','-map','0:a?','-c:v','libx264','-preset','faster','-threads','2','-crf','22','-c:a','aac','-b:a','160k','-movflags','+faststart',str(dst)]
        else:
            vf='scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1'
            cmd=[ff,'-y','-ss',str(start),'-t',str(length),'-i',str(src),'-vf',vf,'-c:v','libx264','-preset','faster','-threads','2','-crf','22','-c:a','aac','-b:a','160k','-movflags','+faststart',str(dst)]
        p=self._ffmpeg_progress_capture(
            cmd,length,start_pct,end_pct,
            f'Short {idx}/{total} oluşturuluyor...'
        )
        if p.returncode!=0 or not dst.exists():
            err=(p.stderr or '')[-1800:]
            raise RuntimeError('FFmpeg çıktı oluşturamadı.\n'+err)

    def _fill_tree(self):
        self._clear_tree()
        for r in self.results:
            self.tree.insert('', 'end', values=(r['no'],fmt_time(r['start']),fmt_time(r['end']),r['score'],Path(r['file']).name))

    def open_selected(self):
        sel=self.tree.selection()
        if not sel:
            messagebox.showinfo('Short seç','Listeden bir Short seç.'); return
        vals=self.tree.item(sel[0],'values')
        try:r=self.results[int(vals[0])-1]
        except:return
        p=Path(r['file'])
        if p.exists():os.startfile(str(p)) if os.name=='nt' else subprocess.Popen(['xdg-open',str(p)])

    def open_folder(self):
        p=self.output_dir
        if not p or not Path(p).exists():
            base=self.output_base.get().strip()
            if base and base != 'Kayıt klasörü henüz seçilmedi' and Path(base).exists():
                p=Path(base)
            else:
                messagebox.showinfo('Klasör yok','Henüz Short oluşturulmadı.'); return
        os.startfile(str(p)) if os.name=='nt' else subprocess.Popen(['xdg-open',str(p)])

    def chatgpt_package(self):
        if not self.results or not self.output_dir:
            messagebox.showinfo('Önce Short oluştur','Önce otomatik Short işlemini tamamla.'); return
        out=Path(self.output_dir)
        lines=[
            'SOLINAJ SHORTS — CHATGPT ANALİZ PAKETİ','',
            f'Kaynak video: {self.video.get()}',f'Kaynak süre: {fmt_time(self.duration)}','',
            'Aşağıdaki shortlardan beğendiklerini bu sohbete MP4 olarak yükle.',
            'İstediğim çıktı: kanca etkili başlık + 1-2 cümle açıklama + SEO etiketleri + kapak yazısı.',''
        ]
        for r in self.results:
            lines.append(f"Short {r['no']:02d}: {fmt_time(r['start'])} - {fmt_time(r['end'])} | hareket puanı {r['score']} | {Path(r['file']).name}")
        f=out/'CHATGPT_ICIN_YUKLE.txt'; f.write_text('\n'.join(lines),encoding='utf-8')
        messagebox.showinfo('ChatGPT paketi hazır',f'Paket oluşturuldu:\n{f}\n\nBeğendiğin MP4 shortları bu sohbete yükleyebilirsin.')

    def _version_tuple(self,v):
        nums=re.findall(r'\d+',str(v))
        return tuple(int(x) for x in (nums+['0','0','0'])[:3])

    def _read_update_config(self):
        cfg=Path(__file__).resolve().parent/'update_config.json'
        if not cfg.exists():return None
        try:return json.loads(cfg.read_text(encoding='utf-8-sig'))
        except:return None

    def check_update(self):
        if self.busy:
            messagebox.showinfo('İşlem sürüyor','Short oluşturma bitince güncelleme yap.'); return
        cfg=self._read_update_config()
        if not cfg or not cfg.get('manifest_url'):
            messagebox.showinfo('Güncelleme','Güncelleme kanalı mevcut kurulumda tanımlı değil.'); return
        self.update_btn.config(state='disabled',text='Kontrol...')
        threading.Thread(target=self._update_worker,args=(cfg,),daemon=True).start()

    def _update_worker(self,cfg):
        try:
            req=urllib.request.Request(cfg['manifest_url'],headers={'User-Agent':'SolinajEditor'})
            with urllib.request.urlopen(req,timeout=15) as r:
                data=json.loads(r.read().decode('utf-8-sig'))
            remote=str(data.get('version','0'))
            if self._version_tuple(remote)<=self._version_tuple(APP_VERSION):
                self.after(0,lambda:messagebox.showinfo('Güncelleme',f'Program güncel.\nV{APP_VERSION}'))
                return
            files=data.get('files') or []
            if not files:raise RuntimeError('Manifest içinde files listesi yok.')
            ans=messagebox.askyesno('Güncelleme bulundu',f"Yeni sürüm V{remote} bulundu.\n\n{data.get('notes','')}\n\nŞimdi indirip kurulsun mu?")
            if not ans:return
            root=Path(__file__).resolve().parent
            stage=Path(tempfile.gettempdir())/f'SolinajEditor_Update_{remote}_{int(time.time())}'
            stage.mkdir(parents=True,exist_ok=True)
            entries=[]
            for i,item in enumerate(files,1):
                rel=str(item.get('path','')).replace('\\','/').lstrip('/')
                url=item.get('url'); sha=(item.get('sha256') or '').lower()
                if not rel or not url:raise RuntimeError('Manifest dosya kaydı eksik.')
                dst=stage/rel; dst.parent.mkdir(parents=True,exist_ok=True)
                self._ui_status(f'Güncelleme indiriliyor {i}/{len(files)} • {rel}',min(90,i/len(files)*90))
                req=urllib.request.Request(url,headers={'User-Agent':'SolinajEditor'})
                with urllib.request.urlopen(req,timeout=60) as r:blob=r.read()
                if sha and hashlib.sha256(blob).hexdigest().lower()!=sha:raise RuntimeError(f'SHA256 uyuşmadı: {rel}')
                dst.write_bytes(blob); entries.append({'path':rel,'source':str(dst)})
            plan={'version':remote,'install_dir':str(root),'files':entries,'launcher':str(root/'SolinajEditor_Launcher.vbs')}
            plan_path=stage/'update_plan.json'; plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
            helper=root/'AUTO_UPDATE_FILES_APPLY.ps1'
            if not helper.exists():raise RuntimeError('AUTO_UPDATE_FILES_APPLY.ps1 bulunamadı.')
            subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(helper),'-Plan',str(plan_path)],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.after(0,self.destroy)
        except Exception as e:
            self.after(0,lambda:messagebox.showerror('Güncelleme hatası',str(e)))
        finally:
            self.after(0,lambda:self.update_btn.config(state='normal',text='↻ Güncelle'))

    def _clean_exit(self):
        try:
            p=self.active_process
            if p and p.poll() is None:
                p.terminate()
                try:p.wait(timeout=1.5)
                except Exception:p.kill()
        except Exception:pass
        self.destroy()


if __name__=='__main__':
    ShortsMaker().mainloop()
