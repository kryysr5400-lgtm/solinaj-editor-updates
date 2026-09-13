import ast
import re

TARGET_VERSION = "16.1"


def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sinifi bulunamadi.")


def _rename_effective_method(source_text, old_name, new_name):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [
        n for n in app.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == old_name
    ]
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
    # Sinifin son metodundan hemen sonra ekle. App sinifinin disina cikmaz.
    insert_line = app.end_lineno
    lines = source_text.splitlines(keepends=True)
    indent = " " * 4
    block = "".join(indent + ln + "\n" for ln in method_block.strip("\n").splitlines())
    return "".join(lines[:insert_line]) + "\n" + block + "".join(lines[insert_line:])


def apply_update(source_text):
    if "class App(tk.Tk):" not in source_text:
        raise RuntimeError("Bu kurulum Solinaj Arsivleyici yapisiyla uyumlu degil.")

    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', source_text)
    if not m:
        raise RuntimeError("Surum bilgisi bulunamadi.")
    current = m.group(1)
    if current not in {"15.8", "15.9", "16.0"}:
        raise RuntimeError(f"Bu guncelleme V15.8/V15.9/V16.0 icindir. Mevcut: {current}")

    # Mevcut calisan TARA/DURDUR mantigini aynen koru; sadece sarmala.
    source_text = _rename_effective_method(source_text, "start_scan", "_v161_core_start_scan")
    source_text = _rename_effective_method(source_text, "stop_scan", "_v161_core_stop_scan")

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V16.1"',
        source_text,
        count=1,
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "16.1"',
        source_text,
        count=1,
    )

    methods = r'''
def start_scan(self):
    result = self._v161_core_start_scan()
    try:
        if getattr(self, "running", False):
            self._transfer_panel_show()
    except Exception:
        pass
    return result

def stop_scan(self):
    result = self._v161_core_stop_scan()
    try:
        if getattr(self, "running", False):
            self._transfer_panel_show()
            self._transfer_panel_refresh()
    except Exception:
        pass
    return result

def _transfer_panel_ensure(self):
    try:
        if hasattr(self, "_transfer_panel") and self._transfer_panel.winfo_exists():
            return
    except Exception:
        pass

    # Eski ortadaki tek progress bar artik gorunmez.
    try:
        self.progress.stop()
    except Exception:
        pass
    try:
        self.progress.pack_forget()
    except Exception:
        pass

    parent = self.progress.master
    panel = tk.Frame(
        parent,
        bg="#f3f3f3",
        highlightbackground="#b8b8b8",
        highlightthickness=1,
        bd=0,
    )
    self._transfer_panel = panel

    top = tk.Frame(panel, bg="#f3f3f3")
    top.pack(fill="x", padx=14, pady=(12, 4))
    tk.Label(
        top,
        text="Dosyalar arşivleniyor",
        bg="#f3f3f3",
        fg="#202020",
        font=("Segoe UI", 12, "bold"),
    ).pack(side="left")
    self._transfer_percent_var = tk.StringVar(value="0%")
    tk.Label(
        top,
        textvariable=self._transfer_percent_var,
        bg="#f3f3f3",
        fg="#202020",
        font=("Segoe UI", 18),
    ).pack(side="right")

    self._transfer_action_var = tk.StringVar(value="Hazırlanıyor...")
    tk.Label(
        panel,
        textvariable=self._transfer_action_var,
        bg="#f3f3f3",
        fg="#404040",
        font=("Segoe UI", 9),
        anchor="w",
    ).pack(fill="x", padx=14, pady=(0, 6))

    self._transfer_canvas = tk.Canvas(
        panel,
        height=28,
        bg="#ffffff",
        highlightbackground="#bcbcbc",
        highlightthickness=1,
        bd=0,
    )
    self._transfer_canvas.pack(fill="x", padx=14, pady=(0, 9))

    self._transfer_file_var = tk.StringVar(value="Dosya: -")
    self._transfer_from_var = tk.StringVar(value="Kaynak: -")
    self._transfer_to_var = tk.StringVar(value="Hedef: -")
    self._transfer_speed_var = tk.StringVar(value="Hız: -")

    for var in (
        self._transfer_file_var,
        self._transfer_from_var,
        self._transfer_to_var,
        self._transfer_speed_var,
    ):
        tk.Label(
            panel,
            textvariable=var,
            bg="#f3f3f3",
            fg="#303030",
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=14, pady=1)

    buttons = tk.Frame(panel, bg="#f3f3f3")
    buttons.pack(fill="x", padx=14, pady=(8, 12))
    self._transfer_pause_btn = ttk.Button(
        buttons,
        text="⏸  DURAKLAT",
        command=self._transfer_panel_toggle_pause,
        style="Gray.TButton",
    )
    self._transfer_pause_btn.pack(side="right")

    self._transfer_panel_active = False
    self._transfer_panel_job = None
    self._transfer_panel_last_running = False
    self._transfer_panel_hide_job = None

def _transfer_panel_show(self):
    self._transfer_panel_ensure()
    try:
        if getattr(self, "_transfer_panel_hide_job", None):
            self.after_cancel(self._transfer_panel_hide_job)
            self._transfer_panel_hide_job = None
    except Exception:
        pass
    try:
        if not self._transfer_panel.winfo_manager():
            self._transfer_panel.pack(fill="x", padx=16, pady=(4, 14))
    except Exception:
        pass
    self._transfer_panel_active = True
    self._transfer_panel_last_running = bool(getattr(self, "running", False))
    self._transfer_panel_refresh()
    self._transfer_panel_schedule()

def _transfer_panel_hide(self):
    try:
        self._transfer_panel.pack_forget()
    except Exception:
        pass
    self._transfer_panel_active = False

def _transfer_panel_schedule(self):
    try:
        if getattr(self, "_transfer_panel_job", None):
            return
        self._transfer_panel_job = self.after(120, self._transfer_panel_tick)
    except Exception:
        pass

def _transfer_panel_tick(self):
    self._transfer_panel_job = None
    try:
        if not getattr(self, "_transfer_panel_active", False):
            return
        self._transfer_panel_refresh()
        running = bool(getattr(self, "running", False))
        if running:
            self._transfer_panel_last_running = True
            self._transfer_panel_schedule()
        elif getattr(self, "_transfer_panel_last_running", False):
            self._transfer_panel_last_running = False
            try:
                self._transfer_action_var.set("Arşivleme tamamlandı")
                self._transfer_percent_var.set("100%")
                self._transfer_draw_progress(1.0)
                self._transfer_pause_btn.configure(text="✓  TAMAMLANDI", state="disabled")
            except Exception:
                pass
            try:
                self._transfer_panel_hide_job = self.after(2500, self._transfer_panel_hide)
            except Exception:
                pass
    except Exception:
        pass

def _transfer_panel_toggle_pause(self):
    try:
        paused = hasattr(self, "pause_event") and self.pause_event.is_set()
        if paused:
            self.start_scan()
        else:
            self.stop_scan()
    except Exception:
        pass

def _transfer_short_path(self, value, limit=90):
    s = str(value or "-")
    if len(s) <= limit:
        return s
    return "…" + s[-(limit - 1):]

def _transfer_draw_progress(self, ratio):
    try:
        c = self._transfer_canvas
        c.update_idletasks()
        w = max(30, c.winfo_width())
        h = max(12, c.winfo_height())
        ratio = max(0.0, min(1.0, float(ratio)))
        c.delete("all")
        c.create_rectangle(0, 0, w, h, fill="#ffffff", outline="")
        fill_w = int(w * ratio)
        if fill_w > 0:
            c.create_rectangle(0, 0, fill_w, h, fill="#06b025", outline="")
            # Windows kopyalama penceresini andiran ince parlak ust cizgi.
            c.create_rectangle(0, 0, fill_w, 3, fill="#69db78", outline="")
    except Exception:
        pass

def _transfer_panel_refresh(self):
    try:
        self._transfer_panel_ensure()
        running = bool(getattr(self, "running", False))
        paused = bool(hasattr(self, "pause_event") and self.pause_event.is_set())

        total = max(0, int(getattr(self, "current_file_total", 0) or 0))
        done = max(0, int(getattr(self, "current_file_bytes", 0) or 0))
        if total > 0:
            ratio = max(0.0, min(1.0, done / total))
            pct = int(ratio * 100)
        else:
            # Dosya kopyasi başlamadan once ekran bos kalmasin.
            ratio = 0.0
            pct = 0

        action = str(getattr(self, "current_action", "Hazırlanıyor...") or "Hazırlanıyor...")
        if paused:
            action = "Duraklatıldı — DEVAM ET ile aynı yerden sürdür"
        elif running and total <= 0:
            action = action if action not in {"-", "Hazır"} else "Dosyalar taranıyor..."

        self._transfer_action_var.set(action)
        self._transfer_percent_var.set(f"{pct}%" if total > 0 else "—")
        self._transfer_file_var.set("Dosya: " + self._transfer_short_path(getattr(self, "current_file", "-"), 85))
        self._transfer_from_var.set("Kaynak: " + self._transfer_short_path(getattr(self, "current_source", "-"), 100))
        self._transfer_to_var.set("Hedef: " + self._transfer_short_path(getattr(self, "current_target", "-"), 100))

        speed = float(getattr(self, "current_speed_bps", 0.0) or 0.0)
        if paused:
            speed_text = "Duraklatıldı"
        elif speed >= 1024 * 1024:
            speed_text = f"{speed / (1024*1024):.1f} MB/sn"
        elif speed >= 1024:
            speed_text = f"{speed / 1024:.1f} KB/sn"
        elif speed > 0:
            speed_text = f"{speed:.0f} B/sn"
        else:
            speed_text = "-"
        self._transfer_speed_var.set("Hız: " + speed_text)
        self._transfer_draw_progress(ratio)

        if running:
            self._transfer_pause_btn.configure(
                text=("▶  DEVAM ET" if paused else "⏸  DURAKLAT"),
                state="normal",
            )
    except Exception:
        pass
'''

    source_text = _append_app_methods(source_text, methods)

    # Yeni ekran kullanilir; eski orta progress bar kaynakta kalsa bile ilk TARA'da gizlenir.
    compile(source_text, "<solinaj_arsivleyici_v16_1>", "exec")
    return source_text
