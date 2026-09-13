# -*- coding: utf-8 -*-
import ast
import re

TARGET_VERSION = "17.0.1"

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sınıfı bulunamadı.")

def _replace_method(source_text, method_name, new_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [n for n in app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name]
    if not matches:
        raise RuntimeError(f"{method_name} metodu bulunamadı.")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    return "".join(lines[:target.lineno-1]) + new_source.strip("\n") + "\n" + "".join(lines[target.end_lineno:])

def _rename_effective_ui(source_text, new_name):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    methods = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == "_ui"]
    if not methods:
        raise RuntimeError("_ui metodu bulunamadı.")
    target = methods[-1]
    lines = source_text.splitlines(keepends=True)
    idx = target.lineno - 1
    lines[idx] = lines[idx].replace("def _ui(", f"def {new_name}(", 1)
    return "".join(lines)

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
    current = m.group(1)
    if current != "16.9.1":
        raise RuntimeError("Bu güncelleme V16.9.1 içindir. Mevcut: V" + current)

    wrapper = "    def _ui(self):\n        self._v166_core_ui()\n        self.after(140, self._v170_install_heartbeat)\n"
    if "def _v166_core_ui(" in source_text:
        try:
            source_text = _replace_method(source_text, "_ui", wrapper)
        except Exception:
            pass
    else:
        source_text = _rename_effective_ui(source_text, "_v170_core_ui")
        wrapper2 = "    def _ui(self):\n        self._v170_core_ui()\n        self.after(140, self._v170_install_heartbeat)\n"
        source_text = _append_methods_to_app(source_text, wrapper2)

    for method_name in ("_draw_live_panel", "_live_refresh"):
        try:
            source_text = _replace_method(
                source_text,
                method_name,
                "    def " + method_name + "(self):\n        return\n"
            )
        except Exception:
            pass

    methods = """
    def _v170_find_sidebar(self):
        wanted=("ana sayfa","otomatik arşiv","oyun tanıma","dosya ayrıştırma",
                "bulut senkronizasyon","arşiv geçmişi","ayarlar","güncelleme","hakkında")
        best=None
        best_score=-1
        stack=[self]
        while stack:
            w=stack.pop()
            try:
                children=w.winfo_children()
            except Exception:
                children=[]
            stack.extend(children)
            try:
                if w.winfo_class()!="Frame":
                    continue
                texts=[]
                for c in children:
                    try:
                        if c.winfo_class()=="Button":
                            texts.append(str(c.cget("text") or "").strip().lower())
                    except Exception:
                        pass
                hits=sum(1 for t in texts if any(x in t for x in wanted))
                score=hits*10
                try:
                    width=int(w.cget("width") or 0)
                    if 140 <= width <= 320:
                        score+=3
                except Exception:
                    pass
                try:
                    bg=str(w.cget("bg") or "")
                    if bg in ("#07121e","#07101b","#0c1a28","#08131f"):
                        score+=2
                except Exception:
                    pass
                if score>best_score:
                    best_score=score
                    best=w
            except Exception:
                pass
        return best if best_score>=20 else None

    def _v170_hide_old_live_center(self):
        try:
            old_canvas=getattr(self,"canvas",None)
            if old_canvas is not None and old_canvas.winfo_exists():
                parent=old_canvas.master
                try:
                    parent.pack_forget()
                except Exception:
                    try:
                        parent.grid_remove()
                    except Exception:
                        pass
        except Exception:
            pass

    def _v170_install_heartbeat(self):
        if getattr(self,"_v170_heartbeat_installed",False):
            return

        sidebar=self._v170_find_sidebar()
        if sidebar is None:
            self.after(400,self._v170_install_heartbeat)
            return

        try:
            box=tk.Frame(
                sidebar,bg="#07121e",
                highlightbackground="#17334a",
                highlightthickness=1
            )
            box.pack(side="bottom",fill="x",padx=12,pady=(4,10))

            tk.Label(
                box,text="SİSTEM DURUMU",
                bg="#07121e",fg="#9fb9cb",
                font=("Segoe UI",8,"bold")
            ).pack(anchor="w",padx=9,pady=(7,2))

            self.heartbeat_canvas=tk.Canvas(
                box,height=56,bg="#061019",
                highlightthickness=0,bd=0
            )
            self.heartbeat_canvas.pack(fill="x",padx=8,pady=(0,4))

            self.heartbeat_status=tk.StringVar(value="HAZIR • BEKLEMEDE")
            self.heartbeat_label=tk.Label(
                box,textvariable=self.heartbeat_status,
                bg="#07121e",fg="#22c55e",
                font=("Segoe UI",8,"bold")
            )
            self.heartbeat_label.pack(anchor="w",padx=9,pady=(0,7))

            self._v170_hb_phase=0
            self._v170_heartbeat_installed=True
            self._v170_hide_old_live_center()
            self.after(80,self._v170_heartbeat_tick)
        except Exception:
            self.after(500,self._v170_install_heartbeat)

    def _v170_heartbeat_busy(self):
        # DUR komutu verildiyse işlem işçisi kapanmayı tamamlarken bile
        # heartbeat bekleme durumuna döner. Yeni taramada stop_event temizlenir.
        try:
            ev=getattr(self,"stop_event",None)
            if ev is not None and ev.is_set():
                return False
        except Exception:
            pass

        try:
            if bool(getattr(self,"running",False)):
                return True
        except Exception:
            pass

        try:
            action=str(getattr(self,"current_action","") or "").strip().lower()
            idle=("", "hazır", "hazir", "beklemede", "ready", "tamamlandı", "tamamlandi")
            if action not in idle:
                return True
        except Exception:
            pass

        try:
            total=float(getattr(self,"current_file_total",0) or 0)
            done=float(getattr(self,"current_file_bytes",0) or 0)
            if total>0 and done<total:
                return True
        except Exception:
            pass

        return False

    def _v170_heartbeat_tick(self):
        try:
            c=getattr(self,"heartbeat_canvas",None)
            if c is None or not c.winfo_exists():
                return

            w=max(120,int(c.winfo_width() or 180))
            h=max(44,int(c.winfo_height() or 56))
            mid=h//2
            busy=self._v170_heartbeat_busy()
            phase=int(getattr(self,"_v170_hb_phase",0))

            c.delete("all")

            for yy in (mid-14,mid,mid+14):
                c.create_line(0,yy,w,yy,fill="#0d2230",width=1)

            if not busy:
                base="#22c55e"
                glow="#14532d"
                c.create_line(0,mid,w,mid,fill=glow,width=4)
                c.create_line(0,mid,w,mid,fill=base,width=2)
                seg=32
                x=(phase % (w+seg))-seg
                c.create_line(x,mid,min(w,x+seg),mid,fill="#86efac",width=3)
                self.heartbeat_status.set("HAZIR • BEKLEMEDE")
                try:
                    self.heartbeat_label.configure(fg=base)
                except Exception:
                    pass
            else:
                base="#ef4444"
                glow="#7f1d1d"
                pattern=[
                    (0,0),(18,0),(25,-3),(31,7),(37,-20),
                    (43,20),(49,-9),(56,0),(72,0)
                ]
                period=72
                shift=phase % period
                pts=[]
                x=-period-shift
                while x<w+period:
                    for px,dy in pattern:
                        pts.extend((x+px,mid+dy))
                    x+=period

                if len(pts)>=4:
                    c.create_line(*pts,fill=glow,width=5,smooth=False)
                    c.create_line(*pts,fill=base,width=2,smooth=False)

                self.heartbeat_status.set("İŞLEM AKTİF")
                try:
                    self.heartbeat_label.configure(fg=base)
                except Exception:
                    pass

            self._v170_hb_phase=(phase+4)%100000
            self.after(85,self._v170_heartbeat_tick)
        except Exception:
            try:
                self.after(250,self._v170_heartbeat_tick)
            except Exception:
                pass
"""

    source_text = _append_methods_to_app(source_text, methods)

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V17.0.1"',
        source_text, count=1
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "17.0.1"',
        source_text, count=1
    )

    compile(source_text, "<solinaj_arsivleyici_v17_0_1>", "exec")
    return source_text
