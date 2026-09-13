import ast
import re

TARGET_VERSION = "15.4"


def _replace_method(source_text, method_name, new_method_source):
    tree = ast.parse(source_text)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            target = node
            break
    if target is None:
        raise RuntimeError(f"{method_name} metodu bulunamadı.")

    lines = source_text.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    indent = " " * target.col_offset
    replacement = "".join(indent + line + "\n" for line in new_method_source.strip("\n").splitlines())
    return "".join(lines[:start]) + replacement + "".join(lines[end:])


def apply_update(source_text):
    source_text = re.sub(
        r'APP_NAME\s*=\s*"Solinaj Arşivleyici V[^"]+"',
        'APP_NAME = "Solinaj Arşivleyici V15.4"',
        source_text,
        count=1,
    )
    source_text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "15.4"',
        source_text,
        count=1,
    )

    classify_method = '''
def classify_target(self,p):
    cloud=Path(self.config_data["cloud_root"])
    ext=p.suffix.lower()

    # Eski video / Shorts sistemi aynen korunur.
    if ext in VIDEO_EXT:
        self._stat("Video")
        low=str(p).lower()
        game="Bilinmeyen Oyun"
        for g,keys in GAME_KEYWORDS.items():
            if any(k in low for k in keys):
                game=g
                break
        target=cloud/"Videolar"/safe_name(game)
        try:
            if p.stat().st_size <= int(self.config_data.get("short_max_mb",150))*1024*1024:
                target=cloud/"Shorts"/safe_name(game)
                self._stat("Short")
        except Exception:
            pass
        return target

    # Eski oyun resmi / aile resmi sistemi aynen korunur.
    if ext in IMAGE_EXT:
        low=str(p).lower()
        fam=False
        for f in self.config_data.get("family_folders",[]):
            try:
                if str(p.resolve()).lower().startswith(str(Path(f).resolve()).lower()):
                    fam=True
                    break
            except Exception:
                pass
        if fam:
            self._stat("Aile Resmi")
            return cloud/"Resimler"/"Aile"

        game="Diger"
        for g,keys in GAME_KEYWORDS.items():
            if any(k in low for k in keys):
                game=g
                break
        self._stat("Oyun Resmi")
        return cloud/"Resimler"/"Oyun"/safe_name(game)

    groups = {
        "Belgeler": {
            ".pdf":"PDF", ".doc":"Word", ".docx":"Word", ".odt":"Word",
            ".xls":"Excel", ".xlsx":"Excel", ".xlsm":"Excel", ".ods":"Excel",
            ".ppt":"PowerPoint", ".pptx":"PowerPoint", ".odp":"PowerPoint",
            ".txt":"Metin", ".rtf":"Metin", ".md":"Metin",
            ".csv":"Tablo", ".tsv":"Tablo",
        },
        "Sesler": {
            ".mp3":"MP3", ".wav":"WAV", ".flac":"FLAC", ".aac":"AAC",
            ".ogg":"OGG", ".m4a":"M4A", ".wma":"WMA",
        },
        "Arsivler": {
            ".zip":"ZIP", ".rar":"RAR", ".7z":"7Z", ".tar":"TAR",
            ".gz":"GZ", ".bz2":"BZ2", ".xz":"XZ",
        },
        "Programlar": {
            ".exe":"EXE", ".msi":"MSI", ".msix":"MSIX", ".appx":"APPX",
            ".apk":"APK", ".bat":"BAT", ".cmd":"CMD", ".ps1":"PowerShell",
        },
        "Projeler": {
            ".py":"Python", ".pyw":"Python", ".js":"JavaScript", ".ts":"TypeScript",
            ".html":"Web", ".htm":"Web", ".css":"Web", ".scss":"Web",
            ".json":"JSON", ".xml":"XML", ".yaml":"YAML", ".yml":"YAML",
            ".sql":"SQL", ".cs":"CSharp", ".cpp":"CPP", ".c":"C", ".h":"Header",
            ".java":"Java", ".php":"PHP",
        },
        "Veriler": {
            ".db":"Veritabani", ".sqlite":"Veritabani", ".sqlite3":"Veritabani",
            ".log":"Log", ".ini":"Ayar", ".cfg":"Ayar", ".conf":"Ayar",
            ".reg":"Kayit", ".dat":"Veri",
        },
        "Tasarim": {
            ".psd":"Photoshop", ".ai":"Illustrator", ".svg":"SVG",
            ".blend":"Blender", ".obj":"3D", ".fbx":"3D", ".stl":"3D",
        },
        "Fontlar": {
            ".ttf":"TTF", ".otf":"OTF", ".woff":"WOFF", ".woff2":"WOFF2",
        },
    }

    for ana_klasor, ext_map in groups.items():
        if ext in ext_map:
            return cloud/ana_klasor/ext_map[ext]

    if ext:
        return cloud/"Diger Dosyalar"/safe_name(ext.lstrip(".").upper())
    return cloud/"Diger Dosyalar"/"Uzantisiz"
'''

    scan_method = '''
def _scan_worker(self):
    try:
        cloud=Path(self.config_data["cloud_root"])
        cloud.mkdir(parents=True,exist_ok=True)
        files=[]

        for folder in self.config_data.get("watch_folders",[]):
            root=Path(folder)
            if not root.exists():
                continue

            for p in root.rglob("*"):
                if self.stop_event.is_set():
                    break
                if not p.is_file():
                    continue

                try:
                    if str(p.resolve()).lower().startswith(str(cloud.resolve()).lower()):
                        continue
                except Exception:
                    pass

                files.append(p)

        total=len(files)
        self.after(0,lambda:self.progress.configure(maximum=max(1,total),value=0))

        for i,p in enumerate(files,1):
            if self.stop_event.is_set():
                break

            self._stat("Taranan")
            fp=self._fingerprint(p)

            if fp in self.history:
                self.after(0,lambda i=i:self.progress.configure(maximum=max(1,total),value=i))
                continue

            if not is_file_stable(p):
                self.add_log_ui(f"ATLANDI (dosya kullanımda/yeni): {p.name}")
                continue

            try:
                targetdir=self.classify_target(p)
                targetdir.mkdir(parents=True,exist_ok=True)
                dst=unique_target(targetdir/p.name)
                self.add_log_ui(f"KOPYALANIYOR: {p.name} -> {targetdir}")

                if self.config_data.get("copy_mode",True):
                    self._copy_with_progress(p,dst)
                else:
                    shutil.move(str(p),str(dst))

                self.history[fp]={"source":str(p),"target":str(dst),"time":time.time()}
                save_history(self.history)

                self.after(
                    0,
                    lambda p=p,dst=dst:self.tree.insert(
                        "",0,values=(p.name,p.suffix.lower() or "uzantisiz",str(dst.parent))
                    )
                )
            except Exception as e:
                self._stat("Hata")
                self.add_log_ui(f"HATA: {p.name} | {e}")

            self.after(0,lambda i=i:self.progress.configure(maximum=max(1,total),value=i))

        self.after(
            0,
            lambda:self.status.set(
                "Tarama tamamlandı" if not self.stop_event.is_set() else "Tarama durduruldu"
            )
        )
    finally:
        self.running=False
'''

    source_text = _replace_method(source_text, "classify_target", classify_method)
    source_text = _replace_method(source_text, "_scan_worker", scan_method)
    compile(source_text, "<solinaj_arsivleyici_v15_4>", "exec")
    if 'APP_VERSION = "15.4"' not in source_text:
        raise RuntimeError("Sürüm bilgisi güncellenemedi.")
    return source_text
