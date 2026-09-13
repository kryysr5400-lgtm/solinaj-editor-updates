import re

TARGET_VERSION = "16.2"

def _must_replace(text, old, new, label):
    if old not in text:
        raise RuntimeError(label + " bulunamadi; guncelleme durduruldu.")
    return text.replace(old, new, 1)

def apply_update(source_text):
    if "class App(tk.Tk):" not in source_text:
        raise RuntimeError("Bu kurulum Solinaj Arsivleyici yapisiyla uyumlu degil.")

    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', source_text)
    if not m:
        raise RuntimeError("Surum bilgisi bulunamadi.")
    if m.group(1) != "16.1":
        raise RuntimeError("Bu guncelleme yalnizca V16.1 icindir. Mevcut: " + m.group(1))

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

    marker = '        show_page("home")'
    if 'self.after(250, self._transfer_panel_show)' not in source_text:
        source_text = _must_replace(
            source_text,
            marker,
            marker + '\n        self.after(250, self._transfer_panel_show)',
            "Ana sayfa acilis noktasi",
        )

    old = '    parent = self.progress.master\n    panel = tk.Frame('
    new = '''    parent = self.progress.master
    try:
        for _child in parent.winfo_children():
            try:
                _child.pack_forget()
            except Exception:
                try:
                    _child.grid_remove()
                except Exception:
                    try:
                        _child.place_forget()
                    except Exception:
                        pass
    except Exception:
        pass
    panel = tk.Frame('''
    source_text = _must_replace(
        source_text, old, new, "Windows panel ana kapsayicisi"
    )

    source_text = source_text.replace('text="Dosyalar arşivleniyor"', 'text="Arşivleme İşlemi"', 1)
    source_text = source_text.replace('bg="#f3f3f3"', 'bg="#111827"')
    source_text = source_text.replace('fg="#202020"', 'fg="#f9fafb"')
    source_text = source_text.replace('fg="#404040"', 'fg="#cbd5e1"')
    source_text = source_text.replace('fg="#303030"', 'fg="#e5e7eb"')
    source_text = source_text.replace('bg="#ffffff"', 'bg="#0b1220"')
    source_text = source_text.replace('highlightbackground="#b8b8b8"', 'highlightbackground="#374151"')
    source_text = source_text.replace('highlightbackground="#bcbcbc"', 'highlightbackground="#4b5563"')
    source_text = source_text.replace('fill="#ffffff"', 'fill="#0b1220"')
    source_text = source_text.replace('fill="#06b025"', 'fill="#16a34a"')
    source_text = source_text.replace('fill="#69db78"', 'fill="#4ade80"')

    anchor = '    self._transfer_speed_var = tk.StringVar(value="Hız: -")\n'
    addition = '''    self._transfer_count_var = tk.StringVar(value="0 / 0 dosya")
    self._transfer_eta_var = tk.StringVar(value="Kalan: -")
'''
    source_text = _must_replace(
        source_text, anchor, anchor + addition, "Panel bilgi degiskenleri"
    )

    tuple_old = '''        self._transfer_to_var,
        self._transfer_speed_var,
    ):'''
    tuple_new = '''        self._transfer_to_var,
        self._transfer_speed_var,
        self._transfer_count_var,
        self._transfer_eta_var,
    ):'''
    source_text = _must_replace(
        source_text, tuple_old, tuple_new, "Panel bilgi satirlari"
    )

    refresh_anchor = '        self._transfer_speed_var.set("Hız: " + speed_text)\n        self._transfer_draw_progress(ratio)'
    refresh_new = '''        self._transfer_speed_var.set("Hız: " + speed_text)

        try:
            _scan_done = int(float(self.progress["value"] or 0))
            _scan_total = int(float(self.progress["maximum"] or 0))
        except Exception:
            _scan_done, _scan_total = 0, 0
        self._transfer_count_var.set(f"{_scan_done} / {_scan_total} dosya")

        if paused:
            _eta = "-"
        elif total > done and speed > 0:
            _sec = max(0, int((total - done) / speed))
            if _sec < 60:
                _eta = f"{_sec} sn"
            elif _sec < 3600:
                _eta = f"{_sec // 60} dk {_sec % 60:02d} sn"
            else:
                _eta = f"{_sec // 3600} sa {(_sec % 3600) // 60:02d} dk"
        else:
            _eta = "-"
        self._transfer_eta_var.set("Kalan: " + _eta)
        self._transfer_draw_progress(ratio)'''
    source_text = _must_replace(
        source_text, refresh_anchor, refresh_new, "Panel canli bilgi guncellemesi"
    )

    hide_block = '''            try:
                self._transfer_panel_hide_job = self.after(2500, self._transfer_panel_hide)
            except Exception:
                pass'''
    keep_block = '''            try:
                self._transfer_panel_active = True
            except Exception:
                pass'''
    source_text = _must_replace(
        source_text, hide_block, keep_block, "Panel tamamlama davranisi"
    )

    compile(source_text, "<solinaj_arsivleyici_v16_2>", "exec")
    return source_text
