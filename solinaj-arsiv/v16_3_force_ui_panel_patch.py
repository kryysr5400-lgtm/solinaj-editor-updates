import ast
import re

TARGET_VERSION = "16.3"

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sinifi bulunamadi.")

def _rename_effective_method(source_text, old_name, new_name):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [n for n in app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == old_name]
    if not matches:
        raise RuntimeError(f"{old_name} metodu bulunamadi.")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    idx = target.lineno - 1
    line = lines[idx]
    needle = f"def {old_name}("
    if needle not in line:
        raise RuntimeError(f"{old_name} tanimi beklenen bicimde degil.")
    lines[idx] = line.replace(needle, f"def {new_name}(", 1)
    return "".join(lines)

def _append_app_methods(source_text, method_block):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    insert_line = app.end_lineno
    lines = source_text.splitlines(keepends=True)
    block = "".join("    " + ln + "\n" for ln in method_block.strip("\n").splitlines())
    return "".join(lines[:insert_line]) + "\n" + block + "".join(lines[insert_line:])

def apply_update(source_text):
    if "class App(tk.Tk):" not in source_text:
        raise RuntimeError("Bu kurulum Solinaj Arsivleyici yapisiyla uyumlu degil.")

    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', source_text)
    if not m:
        raise RuntimeError("Surum bilgisi bulunamadi.")
    current = m.group(1)
    if current not in {"16.1", "16.2"}:
        raise RuntimeError("Bu guncelleme V16.1/V16.2 icindir. Mevcut: " + current)

    if "def _v163_core_ui(" in source_text:
        raise RuntimeError("V16.3 arayuz yamasi zaten uygulanmis.")

    source_text = _rename_effective_method(source_text, "_ui", "_v163_core_ui")

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V16.3"',
        source_text,
        count=1,
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "16.3"',
        source_text,
        count=1,
    )

    methods = r'''
def _ui(self):
    self._v163_core_ui()
    self.after(250, self._v163_install_windows_panel)

def _v163_walk_widgets(self, widget):
    out = []
    try:
        kids = list(widget.winfo_children())
    except Exception:
        return out
    for child in kids:
        out.append(child)
        out.extend(self._v163_walk_widgets(child))
    return out

def _v163_install_windows_panel(self):
    try:
        target_label = None
        for w in self._v163_walk_widgets(self):
            try:
                txt = str(w.cget("text"))
            except Exception:
                continue
            if "Arşivleme Devam Ediyor" in txt or "Arsivleme Devam Ediyor" in txt:
                target_label = w
                break

        if target_label is None:
            try:
                work = self.progress.master
            except Exception:
                return
        else:
            try:
                work = target_label.master.master.master
            except Exception:
                try:
                    work = target_label.master.master
                except Exception:
                    work = target_label.master

        for child in list(work.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        try:
            work.configure(bg="#0d1b29", highlightbackground="#1e435d", highlightthickness=1)
        except Exception:
            pass

        self._v163_panel = tk.Frame(work, bg="#0d1b29", bd=0)
        self._v163_panel.pack(fill="x", padx=14, pady=12)

        top = tk.Frame(self._v163_panel, bg="#0d1b29")
        top.pack(fill="x")

        tk.Label(
            top, text="Dosya arşivleme işlemi",
            bg="#0d1b29", fg="#ffffff",
            font=("Segoe UI", 12, "bold")
        ).pack(side="left")

        self._v163_pct = tk.StringVar(value="0%")
        tk.Label(
            top, textvariable=self._v163_pct,
            bg="#0d1b29", fg="#ffffff",
            font=("Segoe UI", 18, "bold")
        ).pack(side="right")

        self._v163_status = tk.StringVar(value="Hazır")
        tk.Label(
            self._v163_panel, textvariable=self._v163_status,
            bg="#0d1b29", fg="#a4bbca",
            font=("Segoe UI", 9), anchor="w"
        ).pack(fill="x", pady=(2, 7))

        self._v163_canvas = tk.Canvas(
            self._v163_panel, height=30,
            bg="#081522", highlightbackground="#31536b",
            highlightthickness=1, bd=0
        )
        self._v163_canvas.pack(fill="x", pady=(0, 9))

        info = tk.Frame(self._v163_panel, bg="#0d1b29")
        info.pack(fill="x")

        self._v163_file = tk.StringVar(value="Dosya: -")
        self._v163_count = tk.StringVar(value="Dosya sayısı: 0 / 0")
        self._v163_speed = tk.StringVar(value="Hız: -")
        self._v163_eta = tk.StringVar(value="Kalan süre: -")
        self._v163_source = tk.StringVar(value="Kaynak: -")
        self._v163_target = tk.StringVar(value="Hedef: -")

        left = tk.Frame(info, bg="#0d1b29")
        left.pack(side="left", fill="x", expand=True)
        right = tk.Frame(info, bg="#0d1b29")
        right.pack(side="right")

        for var in (self._v163_file, self._v163_source, self._v163_target):
            tk.Label(
                left, textvariable=var, bg="#0d1b29", fg="#dce9f5",
                font=("Segoe UI", 9), anchor="w"
            ).pack(fill="x", pady=1)

        for var in (self._v163_count, self._v163_speed, self._v163_eta):
            tk.Label(
                right, textvariable=var, bg="#0d1b29", fg="#dce9f5",
                font=("Segoe UI", 9), anchor="e"
            ).pack(fill="x", pady=1)

        self._v163_refresh_panel()
    except Exception:
        pass

def _v163_short(self, value, limit=80):
    s = str(value or "-")
    if len(s) <= limit:
        return s
    return "…" + s[-(limit-1):]

def _v163_draw_bar(self, ratio):
    try:
        c = self._v163_canvas
        c.update_idletasks()
        w = max(20, c.winfo_width())
        h = max(10, c.winfo_height())
        ratio = max(0.0, min(1.0, float(ratio)))
        c.delete("all")
        c.create_rectangle(0, 0, w, h, fill="#081522", outline="")
        fw = int(w * ratio)
        if fw > 0:
            c.create_rectangle(0, 0, fw, h, fill="#0aa8f5", outline="")
            c.create_rectangle(0, 0, fw, 3, fill="#61d4ff", outline="")
    except Exception:
        pass

def _v163_refresh_panel(self):
    try:
        running = bool(getattr(self, "running", False))
        total_bytes = int(getattr(self, "current_file_total", 0) or 0)
        done_bytes = int(getattr(self, "current_file_bytes", 0) or 0)
        speed = float(getattr(self, "current_speed_bps", 0.0) or 0.0)

        if total_bytes > 0:
            ratio = max(0.0, min(1.0, done_bytes / total_bytes))
        else:
            try:
                pmax = float(self.progress["maximum"] or 1)
                pval = float(self.progress["value"] or 0)
                ratio = max(0.0, min(1.0, pval / max(1.0, pmax)))
            except Exception:
                ratio = 0.0

        self._v163_pct.set(f"{int(ratio*100)}%")
        action = str(getattr(self, "current_action", "") or "")
        if not action or action == "-":
            action = "Arşivleme devam ediyor..." if running else "Hazır"
        self._v163_status.set(action)

        self._v163_file.set("Dosya: " + self._v163_short(getattr(self, "current_file", "-"), 85))
        self._v163_source.set("Kaynak: " + self._v163_short(getattr(self, "current_source", "-"), 95))
        self._v163_target.set("Hedef: " + self._v163_short(getattr(self, "current_target", "-"), 95))

        try:
            done_count = int(float(self.progress["value"] or 0))
            total_count = int(float(self.progress["maximum"] or 0))
        except Exception:
            done_count, total_count = 0, 0
        self._v163_count.set(f"Dosya sayısı: {done_count} / {total_count}")

        if speed >= 1024*1024:
            speed_text = f"{speed/(1024*1024):.1f} MB/sn"
        elif speed >= 1024:
            speed_text = f"{speed/1024:.1f} KB/sn"
        elif speed > 0:
            speed_text = f"{speed:.0f} B/sn"
        else:
            speed_text = "-"
        self._v163_speed.set("Hız: " + speed_text)

        if total_bytes > done_bytes and speed > 0:
            sec = int((total_bytes-done_bytes)/speed)
            if sec < 60:
                eta = f"{sec} sn"
            elif sec < 3600:
                eta = f"{sec//60} dk {sec%60:02d} sn"
            else:
                eta = f"{sec//3600} sa {(sec%3600)//60:02d} dk"
        else:
            eta = "-"
        self._v163_eta.set("Kalan süre: " + eta)

        self._v163_draw_bar(ratio)
    except Exception:
        pass
    try:
        self.after(150, self._v163_refresh_panel)
    except Exception:
        pass
'''
    source_text = _append_app_methods(source_text, methods)
    compile(source_text, "<solinaj_arsivleyici_v16_3>", "exec")
    return source_text
