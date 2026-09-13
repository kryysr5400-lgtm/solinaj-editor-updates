# -*- coding: utf-8 -*-
import ast
import re

TARGET_VERSION = "16.6"

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sınıfı bulunamadı.")

def _replace_method(source_text, method_name, new_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [n for n in app.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name]
    if not matches:
        raise RuntimeError(f"{method_name} metodu bulunamadı.")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    return "".join(lines[:start]) + new_source.strip("\n") + "\n" + "".join(lines[end:])

def _rename_effective_ui(source_text):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    methods = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == "_ui"]
    if not methods:
        raise RuntimeError("_ui metodu bulunamadı.")
    target = methods[-1]
    lines = source_text.splitlines(keepends=True)
    idx = target.lineno - 1
    lines[idx] = lines[idx].replace("def _ui(", "def _v166_core_ui(", 1)
    return "".join(lines)

def _append_methods_to_app(source_text, methods_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    insert_line = app.end_lineno
    lines = source_text.splitlines(keepends=True)
    return "".join(lines[:insert_line]) + "\n" + methods_source.strip("\n") + "\n" + "".join(lines[insert_line:])

def apply_update(source_text):
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', source_text)
    if not m:
        raise RuntimeError("Sürüm bilgisi bulunamadı.")
    current = m.group(1)
    if current not in ("16.4", "16.5"):
        raise RuntimeError("Bu güncelleme V16.4 veya V16.5 içindir. Mevcut: V" + current)

    source_text = _rename_effective_ui(source_text)

    for method_name in ("_draw_live_panel","_live_refresh"):
        try:
            source_text = _replace_method(
                source_text,
                method_name,
                "    def "+method_name+"(self):\n        return\n"
            )
        except Exception:
            pass

    methods = '''
    def _ui(self):
        self._v166_core_ui()
        self.after(120, self._v166_install_heartbeat)

    def _v166_find_sidebar(self):
        try:
            candidates=[]
            stack=[self]
            while stack:
                w=stack.pop()
                try:
                    children=w.winfo_children()
                except Exception:
                    children=[]
                stack.extend(children)
                try:
                    cls=w.winfo_class()
                    if cls=="Frame":
                        score=0
                        try:
                            width=int(w.cget("width") or 0)
                        except Exception:
                            width=0
                        try:
                            bg=str(w.cget("bg"))
                        except Exception:
                            bg=""
                        if width and width <= 280:
                            score += 2
                        if bg in ("#07121e","#07101b","#0c1a28"):
                            score += 2
                        btns=sum(1 for c in children if c.winfo_class()=="Button")
                        if btns >= 5:
                            score += 5
                        if score:
                            candidates.append((score,w))
                except Exception:
                    pass
            if candidates:
                candidates.sort(key=lambda x:x[0], reverse=True)
                return candidates[0][1]
        except Exception:
            pass
        return None

    def _v166_install_heartbeat(self):
        if getattr(self, "_v166_heartbeat_installed", False):
            return
        sidebar=self._v166_find_sidebar()
        if sidebar is None:
            self.after(400, self._v166_install_heartbeat)
            return

        try:
            box=tk.Frame(sidebar,bg="#07121e",highlightbackground="#17334a",highlightthickness=1)
            box.pack(side="bottom",fill="x",padx=12,pady=(4,10))

            tk.Label(box,text="SİSTEM DURUMU",bg="#07121e",fg="#9fb9cb",
                     font=("Segoe UI",8,"bold")).pack(anchor="w",padx=9,pady=(7,2))

            self.heartbeat_canvas=tk.Canvas(
                box,height=52,bg="#061019",highlightthickness=0,bd=0
            )
            self.heartbeat_canvas.pack(fill="x",padx=8,pady=(0,4))

            self.heartbeat_status=tk.StringVar(value="HAZIR • BEKLEMEDE")
            self.heartbeat_label=tk.Label(
                box,textvariable=self.heartbeat_status,bg="#07121e",
                fg="#22c55e",font=("Segoe UI",8,"bold")
            )
            self.heartbeat_label.pack(anchor="w",padx=9,pady=(0,7))

            self._v166_hb_phase=0
            self._v166_heartbeat_installed=True

            try:
                old_canvas=getattr(self,"canvas",None)
                if old_canvas is not None and old_canvas.winfo_exists():
                    old_parent=old_canvas.master
                    old_parent.pack_forget()
            except Exception:
                pass

            self.after(80,self._v166_heartbeat_tick)
        except Exception:
            self.after(500,self._v166_install_heartbeat)

    def _v166_heartbeat_busy(self):
        try:
            if bool(getattr(self,"running",False)):
                return True
        except Exception:
            pass
        try:
            action=str(getattr(self,"current_action","") or "").strip().lower()
            idle_words=("","hazır","beklemede","hazir","ready")
            return action not in idle_words
        except Exception:
            return False

    def _v166_heartbeat_tick(self):
        try:
            c=getattr(self,"heartbeat_canvas",None)
            if c is None or not c.winfo_exists():
                return

            w=max(80,int(c.winfo_width() or 180))
            h=max(40,int(c.winfo_height() or 52))
            mid=h//2
            busy=self._v166_heartbeat_busy()

            c.delete("all")

            if not busy:
                color="#22c55e"
                glow="#14532d"
                c.create_line(0,mid,w,mid,fill=glow,width=4)
                c.create_line(0,mid,w,mid,fill=color,width=2)
                self.heartbeat_status.set("HAZIR • BEKLEMEDE")
                try:
                    self.heartbeat_label.configure(fg=color)
                except Exception:
                    pass
            else:
                color="#ef4444"
                glow="#7f1d1d"
                phase=int(getattr(self,"_v166_hb_phase",0))
                shift=phase % 64
                points=[]
                x=-64-shift
                pattern=[
                    (0,0),(16,0),(23,-4),(29,8),(35,-20),
                    (41,19),(47,-8),(54,0),(64,0)
                ]
                while x < w+64:
                    for px,dy in pattern:
                        points.extend((x+px,mid+dy))
                    x += 64
                if len(points)>=4:
                    c.create_line(*points,fill=glow,width=5,smooth=False)
                    c.create_line(*points,fill=color,width=2,smooth=False)

                self.heartbeat_status.set("İŞLEM AKTİF")
                try:
                    self.heartbeat_label.configure(fg=color)
                except Exception:
                    pass
                self._v166_hb_phase=(phase+4)%100000

            self.after(85,self._v166_heartbeat_tick)
        except Exception:
            try:
                self.after(250,self._v166_heartbeat_tick)
            except Exception:
                pass
'''

    source_text = _append_methods_to_app(source_text, methods)

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V16.6"',
        source_text,
        count=1
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "16.6"',
        source_text,
        count=1
    )

    compile(source_text, "<solinaj_arsivleyici_v16_6>", "exec")
    return source_text
