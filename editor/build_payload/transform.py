from pathlib import Path
import re, sys, shutil

root = Path(sys.argv[1])
app = root / "app.py"
text = app.read_text(encoding="utf-8-sig")

text = text.replace('APP_VERSION = "2.4.4"', 'APP_VERSION = "2.5.0"')
text = text.replace('APP_VERSION="2.4.4"', 'APP_VERSION="2.5.0"')
text = text.replace('self.geometry("1480x900")', 'self.geometry("1540x930")')
text = text.replace('self.minsize(1180, 760)', 'self.minsize(1220, 780)')
text = text.replace('timeline = tk.Frame(outer, bg=TIMELINE_BG, height=285)', 'timeline = tk.Frame(outer, bg=TIMELINE_BG, height=300)')
text = text.replace('outer.add(timeline, stretch="never", minsize=230)', 'outer.add(timeline, stretch="never", minsize=245)')
text = text.replace('media = tk.Frame(main, bg=PANEL, width=280)', 'media = tk.Frame(main, bg=PANEL, width=295)')
text = text.replace('preview = tk.Frame(main, bg="#0b0c10", width=760)', 'preview = tk.Frame(main, bg="#0b0c10", width=790)')
text = text.replace('inspector = tk.Frame(main, bg=PANEL, width=330)', 'inspector = tk.Frame(main, bg=PANEL, width=345)')
text = text.replace('main.add(media, minsize=230)', 'main.add(media, minsize=245)')
text = text.replace('main.add(preview, minsize=520)', 'main.add(preview, minsize=560)')
text = text.replace('main.add(inspector, minsize=290)', 'main.add(inspector, minsize=300)')

start = text.index("    def _build_titlebar(self):")
end = text.index("    def _build_main(self):", start)
text = text[:start] + '''    def _build_titlebar(self):
        bar = tk.Frame(self, bg="#111318", height=64, highlightthickness=1,
                       highlightbackground="#282c35")
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg="#111318")
        left.pack(side="left", fill="y", padx=(14, 0))

        logo_box = tk.Frame(left, bg=ACCENT, width=32, height=32)
        logo_box.pack(side="left", pady=15)
        logo_box.pack_propagate(False)
        tk.Label(logo_box, text="S", bg=ACCENT, fg="#07100f",
                 font=("Segoe UI", 14, "bold")).pack(expand=True)

        brand = tk.Frame(left, bg="#111318")
        brand.pack(side="left", padx=(9, 16), pady=10)
        tk.Label(brand, text="SOLINAJ EDITOR", bg="#111318", fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(brand, text=f"Video Studio  •  V{APP_VERSION}", bg="#111318",
                 fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")

        divider = tk.Frame(left, bg="#2b3039", width=1)
        divider.pack(side="left", fill="y", pady=12, padx=(0, 14))

        center = tk.Frame(bar, bg="#111318")
        center.pack(side="left", fill="y")
        title_actions = [
            ("DOSYA", self.import_media),
            ("DÜZENLE", self.split_clip),
            ("GÖRÜNÜM", self._refresh_view),
            ("YARDIM", self._show_help),
        ]
        for t, cmd in title_actions:
            tk.Button(center, text=t, command=cmd, bg="#111318", fg="#9ea6b3",
                      activebackground="#1c2027", activeforeground=TEXT,
                      relief="flat", bd=0, font=("Segoe UI", 8, "bold"),
                      padx=11, pady=21, cursor="hand2").pack(side="left")

        right = tk.Frame(bar, bg="#111318")
        right.pack(side="right", padx=14, fill="y")

        self.update_button = self._button(right, "↻  Güncelle", self.check_update)
        self.update_button.pack(side="left", padx=(0, 7), pady=13)

        export_btn = self._button(right, "DIŞA AKTAR  →", self.start_export, accent=True)
        export_btn.config(padx=18)
        export_btn.pack(side="left", pady=13)

''' + text[end:]

text = text.replace('tk.Label(hdr, text="Medya", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")', 'tk.Label(hdr, text="MEDYA", bg=PANEL, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(side="left")')
text = text.replace('self._button(hdr, "+ İçe Aktar", self.import_media, accent=True).pack(side="right")', 'self._button(hdr, "+  İçe Aktar", self.import_media, accent=True).pack(side="right")')
text = text.replace('("Yerel", lambda: self.status.set("Yerel medya")),', '("Medya", lambda: self.status.set("Yerel medya")),')
text = text.replace('("Geçiş", lambda: self.status.set("Geçişler sonraki sürüm için hazırlanıyor.")),', '("Geçiş", lambda: self.status.set("Geçişler geliştirme aşamasında.")),')
text = text.replace('("Efekt", lambda: self.status.set("Efektler sonraki sürüm için hazırlanıyor.")),', '("Efekt", lambda: self.status.set("Efektler geliştirme aşamasında.")),')
text = text.replace('search.insert(0, "  Medyada ara")', 'search.insert(0, "  🔎  Medyada ara...")')
text = text.replace('"＋ Timeline\'a Ekle"', '"＋  Timeline\'a Ekle"')
text = text.replace('tk.Label(top, text="Player", bg="#0b0c10", fg=MUTED, font=("Segoe UI", 9)).pack(side="left")', 'tk.Label(top, text="ÖNİZLEME", bg="#0b0c10", fg="#aab2bf", font=("Segoe UI", 8, "bold")).pack(side="left")')
text = text.replace('self.preview_format = tk.Label(top, text="16:9", bg="#0b0c10", fg=MUTED, font=("Segoe UI", 9))', 'self.preview_format = tk.Label(top, text="16:9", bg="#20242c", fg="#dfe4ec", font=("Segoe UI", 8, "bold"), padx=9, pady=4)')
text = text.replace('self.stage = tk.Canvas(stage_wrap, bg="#050608", highlightthickness=1, highlightbackground="#202229")', 'self.stage = tk.Canvas(stage_wrap, bg="#050608", highlightthickness=1, highlightbackground="#2a2f39")')
text = text.replace('tk.Label(hdr, text="Özellikler", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")', 'tk.Label(hdr, text="ÖZELLİKLER", bg=PANEL, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(side="left")')
text = text.replace('"🎵 Ses / Müzikni Aç"', '"♫  Ses / Müzik Kütüphanesi"')

old = '''    def _inspector_section(self, parent, title):
        tk.Label(parent, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", padx=14, pady=(14,5))
'''
new = '''    def _inspector_section(self, parent, title):
        wrap = tk.Frame(parent, bg=PANEL)
        wrap.pack(fill="x", padx=14, pady=(15, 7))
        tk.Label(wrap, text=title.upper(), bg=PANEL, fg="#d7dce5",
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(side="left")
        tk.Frame(wrap, bg="#2a2f38", height=1).pack(side="left", fill="x", expand=True, padx=(9, 0))
'''
text = text.replace(old, new)
text = text.replace('tool = tk.Frame(parent, bg="#17191f", height=44)', 'tool = tk.Frame(parent, bg="#15181e", height=48)')
text = text.replace('tk.Label(right, text="Timeline", bg="#17191f", fg=MUTED, font=("Segoe UI", 9)).pack(side="left")', 'tk.Label(right, text="TIMELINE  •  Yakınlaştır", bg="#17191f", fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")')

s = text.index("    def _build_statusbar(self):")
e = text.index("    def _draw_preview_placeholder", s)
text = text[:s] + '''    def _build_statusbar(self):
        bar = tk.Frame(self, bg="#101217", height=36, highlightthickness=1,
                       highlightbackground="#282c35")
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg="#101217")
        left.pack(side="left", fill="y", padx=12)
        tk.Label(left, text="●", bg="#101217", fg="#67d391",
                 font=("Segoe UI", 8)).pack(side="left", pady=10)
        tk.Label(left, textvariable=self.status, bg="#101217", fg="#a8b0bd",
                 font=("Segoe UI", 8)).pack(side="left", padx=(6, 0))

        right = tk.Frame(bar, bg="#101217")
        right.pack(side="right", fill="y", padx=12)
        tk.Label(right, text="FFmpeg Engine", bg="#101217", fg="#6f7785",
                 font=("Segoe UI", 8)).pack(side="right", padx=(10, 0), pady=10)
        ttk.Progressbar(right, variable=self.progress, maximum=100,
                        style="Horizontal.TProgressbar", length=210).pack(
                            side="right", pady=10)

''' + text[e:]

text = text.replace('root.option_add("*Button.Background", "#242730")', 'root.option_add("*Button.Background", "#22262e")')
text = text.replace('root.option_add("*Entry.Background", "#20232b")', 'root.option_add("*Entry.Background", "#171a20")')
text = text.replace('root.option_add("*Listbox.Background", "#15171c")', 'root.option_add("*Listbox.Background", "#13161b")')
app.write_text(text, encoding="utf-8")

vp = root / "modules" / "versioning.py"
if vp.exists():
    v = vp.read_text(encoding="utf-8-sig")
    v = re.sub(r'APP_VERSION\s*=\s*"[^"]+"', 'APP_VERSION = "2.5.0"', v)
    vp.write_text(v, encoding="utf-8")

for p in list(root.rglob("__pycache__")):
    shutil.rmtree(p, ignore_errors=True)
