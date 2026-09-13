import ast
import re

TARGET_VERSION = "16.0"

CLEAN_METHODS = {
    "start_scan",
    "stop_scan",
    "_pause_wait",
    "_archive_bar_ensure",
    "_archive_bar_draw",
    "_archive_bar_schedule",
    "_archive_bar_tick",
    "_copy_with_progress",
    "classify_target",
    "scan_worker",
    # eski yamalardan kalan yardımcılar
    "_windows_bar_ensure",
    "_windows_bar_draw",
    "_windows_bar_schedule",
    "_windows_bar_tick",
}

def _find_app(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            return node
    raise RuntimeError("App sinifi bulunamadi.")

def _replace_clean_block(source_text, block_source):
    tree = ast.parse(source_text)
    app = _find_app(tree)
    targets = [
        n for n in app.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name in CLEAN_METHODS
    ]
    if not targets:
        raise RuntimeError("Tarama/kopyalama metodlari bulunamadi.")

    lines = source_text.splitlines(keepends=True)
    ranges = sorted((n.lineno - 1, n.end_lineno) for n in targets)
    insert_at = min(a for a, _ in ranges)

    merged = []
    for a, b in ranges:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))

    remove = set()
    for a, b in merged:
        remove.update(range(a, b))

    indent = " " * 4
    replacement = "".join(
        indent + line + "\n"
        for line in block_source.strip("\n").splitlines()
    )

    out = []
    inserted = False
    for i, line in enumerate(lines):
        if i == insert_at and not inserted:
            out.append(replacement)
            inserted = True
        if i not in remove:
            out.append(line)

    if not inserted:
        out.append(replacement)
    return "".join(out)

def apply_update(source_text):
    if "class App(tk.Tk):" not in source_text:
        raise RuntimeError("Bu kurulum Solinaj Arsivleyici yapisiyla uyumlu degil.")

    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', source_text)
    if not m:
        raise RuntimeError("Surum bilgisi bulunamadi.")
    current = m.group(1)
    if current not in {"15.8", "15.9", "16.0"}:
        raise RuntimeError(f"Bu temiz guncelleme V15.8/V15.9 icindir. Mevcut: {current}")

    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Ar[sş]ivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V16.0"',
        source_text,
        count=1,
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "16.0"',
        source_text,
        count=1,
    )

    clean_block = r"""
def start_scan(self):
    if not hasattr(self, "pause_event"):
        self.pause_event = threading.Event()

    # Calisan islem duraklatildiysa yeni thread acma: ayni thread'i uyandir.
    if self.running:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.status.set("Devam ediyor...")
            try:
                self.progress_text.set(getattr(self, "_paused_progress_text", self.progress_text.get()))
            except Exception:
                pass
            self._set_live(action="Devam ediyor", event="TARA - kaldigi yerden devam")
            self.add_log_ui("TARA: mevcut islem kaldigi yerden devam ediyor.")
            self._archive_bar_running = True
            self._archive_bar_schedule()
        else:
            self.status.set("Tarama zaten calisiyor")
        return

    if not self.config_data.get("watch_folders"):
        messagebox.showwarning(APP_NAME, "Once Ayarlar bolumunden taranacak klasor ekleyin.")
        return

    if not self.config_data.get("cloud_root"):
        messagebox.showwarning(APP_NAME, "Once Ayarlar bolumunden bulut klasorunu secin.")
        return

    self.stop_event.clear()
    self.pause_event.clear()
    self.running = True
    self.scan_started_at = time.time()
    self._archive_bar_value = 0.0
    self._archive_bar_phase = 0.0
    self._archive_bar_dir = 1
    self._archive_bar_discovery = True
    self._archive_bar_running = True

    self.status.set("Dosyalar araniyor...")
    self.progress_text.set("Dosyalar araniyor...")
    self._set_live(
        action="Dosyalar araniyor",
        done_bytes=0,
        total_bytes=0,
        speed_bps=0,
        event="Tarama baslatildi",
    )

    self._archive_bar_ensure()
    self._archive_bar_draw()
    self._archive_bar_schedule()
    threading.Thread(target=self.scan_worker, daemon=True).start()

def stop_scan(self):
    if not self.running:
        self.status.set("Hazir - calisan tarama yok")
        return

    if not hasattr(self, "pause_event"):
        self.pause_event = threading.Event()

    if self.pause_event.is_set():
        self.status.set("Zaten duraklatildi - TARA ile devam et")
        return

    # IPTAL ETME. Sadece worker thread'i beklet.
    self.pause_event.set()
    try:
        self._paused_progress_text = self.progress_text.get()
    except Exception:
        self._paused_progress_text = "Duraklatildi"

    self.status.set("Duraklatildi - TARA ile devam et")
    self.progress_text.set("Duraklatildi")
    self._set_live(action="Duraklatildi", event="DURDUR - beklemede")
    self.add_log_ui("DURDUR: islem duraklatildi; dosya ve konum korunuyor.")

    # Barin fazini/sayisal degerini degistirme. Oldugu yerde donsun.
    self._archive_bar_running = False
    self._archive_bar_draw()

def _pause_wait(self):
    if not hasattr(self, "pause_event"):
        self.pause_event = threading.Event()
    while self.pause_event.is_set():
        time.sleep(0.05)

def _archive_bar_ensure(self):
    try:
        if hasattr(self, "_archive_bar") and self._archive_bar.winfo_exists():
            return
    except Exception:
        pass

    try:
        self._archive_bar = tk.Canvas(
            self.progress,
            height=18,
            bg="#202020",
            highlightthickness=0,
            bd=0,
        )
        self._archive_bar.place(x=0, y=0, relwidth=1, relheight=1)
        self._archive_bar.lift()
    except Exception:
        return

def _archive_bar_draw(self):
    try:
        self._archive_bar_ensure()
        c = self._archive_bar
        c.update_idletasks()
        w = max(60, c.winfo_width())
        h = max(10, c.winfo_height())
        c.delete("all")
        c.create_rectangle(0, 0, w, h, fill="#202020", outline="")

        discovery = bool(getattr(self, "_archive_bar_discovery", False))
        phase = float(getattr(self, "_archive_bar_phase", 0.0))

        if discovery:
            block = max(42, int(w * 0.22))
            usable = max(1, w - block)
            x = int((phase / 100.0) * usable)
            c.create_rectangle(x, 1, min(w, x + block), h - 1, fill="#0078D4", outline="")
            shine = max(8, int(block * 0.18))
            sx = min(w, x + int(block * 0.58))
            c.create_rectangle(sx, 1, min(w, sx + shine), h - 1, fill="#58C7FF", outline="")
        else:
            value = max(0.0, min(100.0, float(getattr(self, "_archive_bar_value", 0.0))))
            fill_w = int(w * value / 100.0)
            if fill_w > 0:
                c.create_rectangle(0, 1, fill_w, h - 1, fill="#0078D4", outline="")
                pulse_w = max(10, int(w * 0.045))
                px = int((phase / 100.0) * max(1, fill_w))
                left = max(0, min(fill_w - 1, px))
                right = min(fill_w, left + pulse_w)
                if right > left:
                    c.create_rectangle(left, 1, right, h - 1, fill="#58C7FF", outline="")
    except Exception:
        pass

def _archive_bar_schedule(self):
    try:
        if getattr(self, "_archive_bar_job", None):
            return
        self._archive_bar_job = self.after(35, self._archive_bar_tick)
    except Exception:
        pass

def _archive_bar_tick(self):
    self._archive_bar_job = None
    try:
        if not getattr(self, "_archive_bar_running", False):
            self._archive_bar_draw()
            return

        # DURDUR basildiysa hicbir konumu degistirme.
        if hasattr(self, "pause_event") and self.pause_event.is_set():
            self._archive_bar_running = False
            self._archive_bar_draw()
            return

        phase = float(getattr(self, "_archive_bar_phase", 0.0))
        direction = int(getattr(self, "_archive_bar_dir", 1))
        phase += 2.0 * direction
        if phase >= 100.0:
            phase = 100.0
            direction = -1
        elif phase <= 0.0:
            phase = 0.0
            direction = 1
        self._archive_bar_phase = phase
        self._archive_bar_dir = direction
        self._archive_bar_draw()
        self._archive_bar_schedule()
    except Exception:
        pass

def _copy_with_progress(self, src, dst):
    total = max(1, src.stat().st_size)
    done = 0
    started_active = time.time()
    paused_total = 0.0
    pause_started = None

    dst.parent.mkdir(parents=True, exist_ok=True)
    self._set_live(done_bytes=0, total_bytes=total, speed_bps=0)

    # Dosya acik kalir. DURDUR'da thread bekler; offset kaybolmaz.
    with src.open("rb") as rf, dst.open("wb") as wf:
        while True:
            if hasattr(self, "pause_event") and self.pause_event.is_set():
                if pause_started is None:
                    pause_started = time.time()
                self._pause_wait()
                if pause_started is not None:
                    paused_total += max(0.0, time.time() - pause_started)
                    pause_started = None

            chunk = rf.read(512 * 1024)
            if not chunk:
                break

            wf.write(chunk)
            wf.flush()
            done += len(chunk)

            elapsed = max(0.001, time.time() - started_active - paused_total)
            self._set_live(
                done_bytes=done,
                total_bytes=total,
                speed_bps=done / elapsed,
            )

    try:
        shutil.copystat(src, dst)
    except Exception:
        pass

    self._set_live(done_bytes=total, total_bytes=total, speed_bps=0)

def classify_target(self, p):
    cloud = Path(self.config_data["cloud_root"])
    ext = p.suffix.lower()

    if ext in VIDEO_EXT:
        self._stat("Video")
        mb = p.stat().st_size / (1024 * 1024)
        game = safe_name(detect_game(p))
        if mb <= int(self.config_data.get("short_max_mb", 150)):
            self._stat("Short")
            return cloud / "Videolar" / "Shorts" / game / p.name
        return cloud / "Videolar" / game / p.name

    if ext in IMAGE_EXT:
        if is_family(p, self.config_data.get("family_folders", [])):
            self._stat("Aile Resmi")
            return cloud / "Resimler" / "Aile" / p.name
        game = safe_name(detect_game(p))
        self._stat("Oyun Resmi")
        return cloud / "Resimler" / "Oyunlar" / game / p.name

    groups = {
        "Belgeler": {
            "PDF": {".pdf"},
            "Word": {".doc", ".docx", ".odt", ".rtf"},
            "Excel": {".xls", ".xlsx", ".ods"},
            "PowerPoint": {".ppt", ".pptx", ".odp"},
            "Metin": {".txt", ".md"},
            "Tablo": {".csv", ".tsv"},
        },
        "Sesler": {
            "Ses": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
        },
        "Arsivler": {
            "Arsiv": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
        },
        "Programlar": {
            "Program": {".exe", ".msi", ".msix", ".appx", ".apk", ".bat", ".cmd", ".ps1"},
        },
        "Projeler": {
            "Python": {".py", ".pyw"},
            "JavaScript": {".js", ".jsx"},
            "TypeScript": {".ts", ".tsx"},
            "Web": {".html", ".htm", ".css"},
            "JSON": {".json"},
            "XML": {".xml"},
            "YAML": {".yml", ".yaml"},
            "SQL": {".sql"},
            "CSharp": {".cs"},
            "CPP": {".cpp", ".cc", ".cxx"},
            "C": {".c"},
            "Header": {".h", ".hpp"},
            "Java": {".java"},
            "PHP": {".php"},
        },
        "Veriler": {
            "Veri": {".db", ".sqlite", ".sqlite3", ".log", ".ini", ".cfg", ".conf", ".dat", ".sav"},
        },
        "Tasarim": {
            "Tasarim": {".psd", ".ai", ".svg", ".blend", ".fbx", ".obj", ".stl"},
        },
        "Fontlar": {
            "Font": {".ttf", ".otf", ".woff", ".woff2"},
        },
    }

    for top, subs in groups.items():
        for sub, exts in subs.items():
            if ext in exts:
                return cloud / top / sub / p.name

    if ext:
        return cloud / "Diger Dosyalar" / ext.lstrip(".").upper() / p.name
    return cloud / "Diger Dosyalar" / "Uzantisiz" / p.name

def scan_worker(self):
    try:
        files = []
        cloud = Path(self.config_data["cloud_root"]).resolve()

        # 1) Kesif: toplam dosya bilinmiyor, bar Windows tarzi hareket eder.
        self._archive_bar_discovery = True
        self._archive_bar_running = True
        self.after(0, self._archive_bar_schedule)

        for root in self.config_data.get("watch_folders", []):
            self._pause_wait()
            rp = Path(root)
            if not rp.exists():
                self.add_log_ui(f"YOK: {rp}")
                continue

            for p in rp.rglob("*"):
                self._pause_wait()
                if not p.is_file():
                    continue
                try:
                    if str(p.resolve()).lower().startswith(str(cloud).lower()):
                        continue
                except Exception:
                    pass
                files.append(p)

        total = len(files)

        # 2) Isleme: bar artik gercek genel ilerlemeyi gosterir.
        self._archive_bar_discovery = False
        self._archive_bar_value = 0.0
        self.after(0, self._archive_bar_draw)
        self.after(0, lambda: self.progress_text.set(f"0 / {total}"))

        processed_window = 0

        for i, p in enumerate(files, 1):
            self._pause_wait()
            self._stat("Taranan")

            try:
                ext = p.suffix.lower()
                family = ext in IMAGE_EXT and is_family(
                    p, self.config_data.get("family_folders", [])
                )
                game = (
                    detect_game(p)
                    if ext in VIDEO_EXT or (ext in IMAGE_EXT and not family)
                    else "-"
                )
                if ext in VIDEO_EXT:
                    kind = "Video"
                elif family:
                    kind = "Aile Resmi"
                elif ext in IMAGE_EXT:
                    kind = "Oyun Resmi"
                else:
                    kind = ext.lstrip(".").upper() or "Uzantisiz Dosya"

                self._set_live(
                    action="Dosya analiz ediliyor",
                    file=p.name,
                    source=str(p),
                    target="-",
                    game=game,
                    kind=kind,
                    done_bytes=0,
                    total_bytes=0,
                    speed_bps=0,
                    event=f"Analiz: {p.name}",
                )

                self._pause_wait()

                if not file_age_stable(p):
                    self.add_log_ui(f"ATLANDI (dosya hala yaziliyor olabilir): {p}")
                else:
                    fingerprint = file_fingerprint(p)
                    old = self.history.get(fingerprint)

                    if old:
                        self.add_log_ui(
                            f"DAHA ONCE ARSIVLENDI, ATLANDI: {p} -> {old.get('target', '')}"
                        )
                    else:
                        dst = self.classify_target(p)
                        dst.parent.mkdir(parents=True, exist_ok=True)

                        if dst.exists() and dst.stat().st_size == p.stat().st_size:
                            pass
                        else:
                            if dst.exists():
                                dst = unique_target(dst)

                            self._set_live(
                                action="Buluta kopyalaniyor",
                                target=str(dst),
                                done_bytes=0,
                                total_bytes=p.stat().st_size,
                                speed_bps=0,
                            )
                            self._copy_with_progress(p, dst)

                            if not dst.exists() or dst.stat().st_size != p.stat().st_size:
                                raise IOError("Kopyalama dogrulamasi basarisiz")

                        self.history[fingerprint] = {
                            "source": str(p),
                            "target": str(dst),
                            "size": p.stat().st_size,
                            "archived_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        save_history(self.history)
                        self.add_log_ui(f"KOPYALANDI: {p.name} -> {dst.parent}")

                processed_window += 1

            except Exception as e:
                self._stat("Hata")
                self.add_log_ui(f"HATA: {p} | {e}")

            self._pause_wait()
            self._archive_bar_value = (i / max(1, total)) * 100.0
            self.after(0, self._archive_bar_draw)
            self.after(0, lambda v=i, t=total: self.progress_text.set(f"{v} / {t}"))

            if i % 5 == 0:
                self.update_graph(processed_window)
                processed_window = 0

        self.update_graph(processed_window)
        self._archive_bar_value = 100.0
        self._archive_bar_running = False
        self.after(0, self._archive_bar_draw)
        self.after(0, lambda: self.status.set("Tarama tamamlandi"))
        self.after(0, lambda: self.progress_text.set(f"{total} / {total}"))
        self._set_live(action="Tarama tamamlandi", event="Tarama tamamlandi")

    finally:
        self.running = False
        try:
            self.pause_event.clear()
        except Exception:
            pass
        self._archive_bar_running = False
"""

    source_text = _replace_clean_block(source_text, clean_block)
    compile(source_text, "<solinaj_arsivleyici_v16_0>", "exec")
    return source_text
