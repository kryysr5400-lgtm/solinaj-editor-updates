import ast
import re

TARGET_VERSION = "16.4"

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sinifi bulunamadi.")

def _replace_method(source_text, method_name, new_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [n for n in app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name]
    if not matches:
        raise RuntimeError(f"{method_name} metodu bulunamadi.")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    block = new_source.strip("\n") + "\n"
    return "".join(lines[:start]) + block + "".join(lines[end:])

def apply_update(source_text):
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', source_text)
    if not m:
        raise RuntimeError("Surum bilgisi bulunamadi.")
    if m.group(1) != "16.3":
        raise RuntimeError("Bu duzeltme yalnizca V16.3 icindir. Mevcut: " + m.group(1))

    ui_method = '''    def _ui(self):
        self._v163_core_ui()
'''
    source_text = _replace_method(source_text, "_ui", ui_method)

    old = '''        # Çalışma / ilerleme paneli
        work=tk.Frame(dash,bg="#0d1b29",highlightbackground="#1e435d",highlightthickness=1)
        work.pack(fill="x",padx=24,pady=(0,10))
        worktop=tk.Frame(work,bg="#0d1b29"); worktop.pack(fill="x",padx=16,pady=(13,4))
        tk.Label(worktop,text="▰",bg="#0d1b29",fg="#75e331",font=("Segoe UI Symbol",20,"bold")).pack(side="left")
        wt=tk.Frame(worktop,bg="#0d1b29"); wt.pack(side="left",padx=10)
        tk.Label(wt,text="Arşivleme Devam Ediyor...",bg="#0d1b29",fg="#ffffff",font=("Segoe UI",12,"bold")).pack(anchor="w")
        self.status=tk.StringVar(value="Hazır")
        tk.Label(wt,textvariable=self.status,bg="#0d1b29",fg="#a4bbca",font=("Segoe UI",9)).pack(anchor="w")
        self.progress_text=tk.StringVar(value="0 / 0")
        tk.Label(worktop,textvariable=self.progress_text,bg="#0d1b29",fg="#eaf7ff",font=("Segoe UI",12,"bold")).pack(side="right")
        self.progress=ttk.Progressbar(work,mode="determinate",maximum=100,style="Neon.Horizontal.TProgressbar")
        self.progress.pack(fill="x",padx=16,pady=(4,14),ipady=5)
'''

    new = '''        # Çalışma / ilerleme paneli — V16.4 Windows tarzı canlı işlem görünümü
        work=tk.Frame(dash,bg="#0d1b29",highlightbackground="#31536b",highlightthickness=1)
        work.pack(fill="x",padx=24,pady=(0,10))

        head=tk.Frame(work,bg="#0d1b29")
        head.pack(fill="x",padx=16,pady=(14,5))
        tk.Label(head,text="ARŞİVLEME İŞLEMİ",bg="#0d1b29",fg="#ffffff",
                 font=("Segoe UI",12,"bold")).pack(side="left")
        self.progress_text=tk.StringVar(value="0%")
        tk.Label(head,textvariable=self.progress_text,bg="#0d1b29",fg="#ffffff",
                 font=("Segoe UI",18,"bold")).pack(side="right")

        self.status=tk.StringVar(value="Hazır")
        tk.Label(work,textvariable=self.status,bg="#0d1b29",fg="#9fb7c7",
                 font=("Segoe UI",9),anchor="w").pack(fill="x",padx=16,pady=(0,8))

        self.progress=ttk.Progressbar(work,mode="determinate",maximum=100,
                                     style="Neon.Horizontal.TProgressbar")
        self.progress.pack(fill="x",padx=16,pady=(0,10),ipady=6)

        info=tk.Frame(work,bg="#0d1b29")
        info.pack(fill="x",padx=16,pady=(0,12))
        left_info=tk.Frame(info,bg="#0d1b29")
        left_info.pack(side="left",fill="x",expand=True)
        right_info=tk.Frame(info,bg="#0d1b29")
        right_info.pack(side="right")

        self.v164_file_var=tk.StringVar(value="Dosya: -")
        self.v164_source_var=tk.StringVar(value="Kaynak: -")
        self.v164_target_var=tk.StringVar(value="Hedef: -")
        self.v164_speed_var=tk.StringVar(value="Hız: -")
        self.v164_count_var=tk.StringVar(value="Dosya: 0 / 0")
        self.v164_eta_var=tk.StringVar(value="Kalan süre: -")

        for var in (self.v164_file_var,self.v164_source_var,self.v164_target_var):
            tk.Label(left_info,textvariable=var,bg="#0d1b29",fg="#dce9f5",
                     font=("Segoe UI",9),anchor="w",justify="left").pack(fill="x",pady=1)

        for var in (self.v164_count_var,self.v164_speed_var,self.v164_eta_var):
            tk.Label(right_info,textvariable=var,bg="#0d1b29",fg="#dce9f5",
                     font=("Segoe UI",9),anchor="e",justify="right").pack(fill="x",pady=1)
'''

    if old not in source_text:
        raise RuntimeError("V16.3 ana arşivleme paneli bulunamadı. Program değiştirilmedi.")

    source_text = source_text.replace(old, new, 1)

    marker = '''    def _draw_live_panel(self):'''
    if marker in source_text and 'def _v164_refresh_transfer_panel' not in source_text:
        helper = r'''
    def _v164_short_path(self, value, limit=78):
        s=str(value or "-")
        if len(s)<=limit:
            return s
        return "…" + s[-(limit-1):]

    def _v164_refresh_transfer_panel(self):
        try:
            total=max(1,float(self.progress["maximum"] or 1))
            done=float(self.progress["value"] or 0)
            ratio=max(0.0,min(1.0,done/total))
            self.progress_text.set(f"{int(ratio*100)}%")

            self.v164_file_var.set("Dosya: "+self._v164_short_path(getattr(self,"current_file","-"),78))
            self.v164_source_var.set("Kaynak: "+self._v164_short_path(getattr(self,"current_source","-"),88))
            self.v164_target_var.set("Hedef: "+self._v164_short_path(getattr(self,"current_target","-"),88))

            self.v164_count_var.set(f"Dosya: {int(done)} / {int(total)}")

            speed=float(getattr(self,"current_speed_bps",0.0) or 0.0)
            if speed>=1024*1024:
                st=f"{speed/(1024*1024):.1f} MB/sn"
            elif speed>=1024:
                st=f"{speed/1024:.1f} KB/sn"
            elif speed>0:
                st=f"{speed:.0f} B/sn"
            else:
                st="-"
            self.v164_speed_var.set("Hız: "+st)

            total_b=int(getattr(self,"current_file_total",0) or 0)
            done_b=int(getattr(self,"current_file_bytes",0) or 0)
            if total_b>done_b and speed>0:
                sec=max(0,int((total_b-done_b)/speed))
                if sec<60:
                    eta=f"{sec} sn"
                elif sec<3600:
                    eta=f"{sec//60} dk {sec%60:02d} sn"
                else:
                    eta=f"{sec//3600} sa {(sec%3600)//60:02d} dk"
            else:
                eta="-"
            self.v164_eta_var.set("Kalan süre: "+eta)
        except Exception:
            pass

'''
        source_text = source_text.replace(marker, helper + marker, 1)

    if 'self._v164_refresh_transfer_panel()' not in source_text:
        live_marker = '    def _live_refresh(self):'
        if live_marker in source_text:
            tree = ast.parse(source_text)
            app = _find_app(tree)
            matches = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == "_live_refresh"]
            if matches:
                target = matches[-1]
                lines = source_text.splitlines(keepends=True)
                idx = target.lineno
                lines.insert(idx, '        self._v164_refresh_transfer_panel()\n')
                source_text = ''.join(lines)

    source_text = re.sub(r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
                         'APP_NAME = "Solinaj Arşivleyici V16.4"', source_text, count=1)
    source_text = re.sub(r'APP_VERSION\s*=\s*"[^"]+"',
                         'APP_VERSION = "16.4"', source_text, count=1)

    compile(source_text, "<solinaj_arsivleyici_v16_4>", "exec")
    return source_text
