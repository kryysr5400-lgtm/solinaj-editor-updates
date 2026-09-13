import ast
import re

TARGET_VERSION = "16.2"


def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sinifi bulunamadi.")


def _replace_method(source_text, method_name, new_method_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    matches = [
        n for n in app.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method_name
    ]
    if not matches:
        raise RuntimeError(f"{method_name} metodu bulunamadi; guncelleme durduruldu.")
    target = matches[-1]
    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    block = new_method_source.strip("\n") + "\n"
    return "".join(lines[:start]) + block + "".join(lines[end:])


def apply_update(source_text):
    if "class App(tk.Tk):" not in source_text:
        raise RuntimeError("Bu kurulum Solinaj Arsivleyici yapisiyla uyumlu degil.")

    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', source_text)
    if not m:
        raise RuntimeError("Surum bilgisi bulunamadi.")
    if m.group(1) != "16.1":
        raise RuntimeError("Bu guncelleme yalnizca V16.1 icindir. Mevcut: " + m.group(1))

    required = [
        "_transfer_panel_ensure",
        "_transfer_panel_tick",
        "_transfer_panel_refresh",
        "_transfer_draw_progress",
    ]
    tree = ast.parse(source_text)
    app = _find_app(tree)
    names = {n.name for n in app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    missing = [x for x in required if x not in names]
    if missing:
        raise RuntimeError(
            "V16.1 Windows panel yapisi eksik: " + ", ".join(missing) +
            ". Program degistirilmedi."
        )

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V16.2"',
        source_text,
        count=1,
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "16.2"',
        source_text,
        count=1,
    )

    ensure_method = '''    def _transfer_panel_ensure(self):
        try:
            if hasattr(self, "_transfer_panel") and self._transfer_panel.winfo_exists():
                return
        except Exception:
            pass

        try:
            parent = self.progress.master
        except Exception:
            raise RuntimeError("Arsivleme panelinin ana alani bulunamadi.")

        try:
            for child in list(parent.winfo_children()):
                try:
                    child.pack_forget()
                except Exception:
                    try:
                        child.grid_remove()
                    except Exception:
                        try:
                            child.place_forget()
                        except Exception:
                            pass
        except Exception:
            pass

        panel = tk.Frame(
            parent,
            bg="#111827",
            highlightbackground="#374151",
            highlightthickness=1,
            bd=0,
        )
        self._transfer_panel = panel

        top = tk.Frame(panel, bg="#111827")
        top.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(
            top,
            text="Arşivleme İşlemi",
            bg="#111827",
            fg="#f9fafb",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")

        self._transfer_percent_var = tk.StringVar(value="—")
        tk.Label(
            top,
            textvariable=self._transfer_percent_var,
            bg="#111827",
            fg="#f9fafb",
            font=("Segoe UI", 18, "bold"),
        ).pack(side="right")

        self._transfer_action_var = tk.StringVar(value="Hazır")
        tk.Label(
            panel,
            textvariable=self._transfer_action_var,
            bg="#111827",
            fg="#cbd5e1",
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 7))

        self._transfer_canvas = tk.Canvas(
            panel,
            height=28,
            bg="#0b1220",
            highlightbackground="#4b5563",
            highlightthickness=1,
            bd=0,
        )
        self._transfer_canvas.pack(fill="x", padx=14, pady=(0, 10))

        self._transfer_file_var = tk.StringVar(value="Dosya: -")
        self._transfer_from_var = tk.StringVar(value="Kaynak: -")
        self._transfer_to_var = tk.StringVar(value="Hedef: -")
        self._transfer_speed_var = tk.StringVar(value="Hız: -")
        self._transfer_count_var = tk.StringVar(value="0 / 0 dosya")
        self._transfer_eta_var = tk.StringVar(value="Kalan: -")

        for var in (
            self._transfer_file_var,
            self._transfer_from_var,
            self._transfer_to_var,
            self._transfer_speed_var,
            self._transfer_count_var,
            self._transfer_eta_var,
        ):
            tk.Label(
                panel,
                textvariable=var,
                bg="#111827",
                fg="#e5e7eb",
                font=("Segoe UI", 9),
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=14, pady=1)

        buttons = tk.Frame(panel, bg="#111827")
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
'''

    draw_method = '''    def _transfer_draw_progress(self, ratio):
        try:
            c = self._transfer_canvas
            c.update_idletasks()
            w = max(30, c.winfo_width())
            h = max(12, c.winfo_height())
            ratio = max(0.0, min(1.0, float(ratio)))
            c.delete("all")
            c.create_rectangle(0, 0, w, h, fill="#0b1220", outline="")
            fill_w = int(w * ratio)
            if fill_w > 0:
                c.create_rectangle(0, 0, fill_w, h, fill="#16a34a", outline="")
                c.create_rectangle(0, 0, fill_w, 3, fill="#4ade80", outline="")
        except Exception:
            pass
'''

    tick_method = '''    def _transfer_panel_tick(self):
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
                    self._transfer_panel_active = True
                except Exception:
                    pass
        except Exception:
            pass
'''

    refresh_method = '''    def _transfer_panel_refresh(self):
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
                ratio = 0.0
                pct = 0

            action = str(getattr(self, "current_action", "Hazır") or "Hazır")
            if paused:
                action = "Duraklatıldı — DEVAM ET ile aynı yerden sürdür"
            elif running and total <= 0 and action in {"-", "Hazır"}:
                action = "Dosyalar taranıyor..."

            self._transfer_action_var.set(action)
            self._transfer_percent_var.set(f"{pct}%" if total > 0 else "—")
            self._transfer_file_var.set(
                "Dosya: " + self._transfer_short_path(getattr(self, "current_file", "-"), 85)
            )
            self._transfer_from_var.set(
                "Kaynak: " + self._transfer_short_path(getattr(self, "current_source", "-"), 100)
            )
            self._transfer_to_var.set(
                "Hedef: " + self._transfer_short_path(getattr(self, "current_target", "-"), 100)
            )

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

            try:
                scan_done = int(float(self.progress["value"] or 0))
                scan_total = int(float(self.progress["maximum"] or 0))
            except Exception:
                scan_done, scan_total = 0, 0
            self._transfer_count_var.set(f"{scan_done} / {scan_total} dosya")

            if paused:
                eta = "-"
            elif total > done and speed > 0:
                sec = max(0, int((total - done) / speed))
                if sec < 60:
                    eta = f"{sec} sn"
                elif sec < 3600:
                    eta = f"{sec // 60} dk {sec % 60:02d} sn"
                else:
                    eta = f"{sec // 3600} sa {(sec % 3600) // 60:02d} dk"
            else:
                eta = "-"
            self._transfer_eta_var.set("Kalan: " + eta)
            self._transfer_draw_progress(ratio)

            if running:
                self._transfer_pause_btn.configure(
                    text=("▶  DEVAM ET" if paused else "⏸  DURAKLAT"),
                    state="normal",
                )
        except Exception:
            pass
'''

    source_text = _replace_method(source_text, "_transfer_panel_ensure", ensure_method)
    source_text = _replace_method(source_text, "_transfer_draw_progress", draw_method)
    source_text = _replace_method(source_text, "_transfer_panel_tick", tick_method)
    source_text = _replace_method(source_text, "_transfer_panel_refresh", refresh_method)

    compile(source_text, "<solinaj_arsivleyici_v16_2>", "exec")
    return source_text
