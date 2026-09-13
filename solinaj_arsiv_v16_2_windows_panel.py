# Solinaj Arsiv V16.2 - Windows tarzı işlem paneli
# Bu modül, mevcut V16.1 arşivleme motoruna bağlanacak şekilde hazırlanmış UI bileşenidir.

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

try:
    import customtkinter as ctk
except ImportError:
    ctk = None


@dataclass
class TransferState:
    current_file: str = "Hazır"
    processed_files: int = 0
    total_files: int = 0
    processed_bytes: int = 0
    total_bytes: int = 0
    speed_bps: float = 0.0
    eta_seconds: Optional[float] = None
    status: str = "Hazır"

    @property
    def percent(self) -> float:
        if self.total_bytes > 0:
            return max(0.0, min(100.0, self.processed_bytes / self.total_bytes * 100.0))
        if self.total_files > 0:
            return max(0.0, min(100.0, self.processed_files / self.total_files * 100.0))
        return 0.0


def _human_bytes(value: float) -> str:
    value = float(max(0.0, value))
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024.0
        idx += 1
    return f"{value:.1f} {units[idx]}"


def _human_eta(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "Hesaplanıyor..."
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} sn"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} dk {sec} sn"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} sa {minutes} dk"


class WindowsTransferPanel(ctk.CTkFrame if ctk else object):
    """V16.1 ana sayfadaki 'Arşivleme Devam Ediyor' alanının yerine kullanılacak panel."""

    def __init__(self, master, on_pause=None, on_cancel=None, **kwargs):
        if ctk is None:
            raise RuntimeError("customtkinter gerekli: pip install customtkinter")

        super().__init__(master, fg_color="#172536", corner_radius=8, border_width=1, border_color="#2A78A6", **kwargs)
        self.on_pause = on_pause
        self.on_cancel = on_cancel
        self.paused = False
        self._last_bytes = 0
        self._last_time = time.monotonic()

        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            top,
            text="Dosyalar arşivleniyor",
            anchor="w",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.percent_label = ctk.CTkLabel(
            top,
            text="0%",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.percent_label.grid(row=0, column=1, padx=(8, 0), sticky="e")

        self.file_label = ctk.CTkLabel(self, text="Hazır", anchor="w")
        self.file_label.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")

        self.progress = ctk.CTkProgressBar(self, height=16, corner_radius=3, progress_color="#18D7E8")
        self.progress.grid(row=2, column=0, padx=16, pady=4, sticky="ew")
        self.progress.set(0)

        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.grid(row=3, column=0, padx=16, pady=(6, 6), sticky="ew")
        for col in range(3):
            stats.grid_columnconfigure(col, weight=1)

        self.files_label = ctk.CTkLabel(stats, text="Dosya: 0 / 0", anchor="w")
        self.files_label.grid(row=0, column=0, sticky="w")
        self.speed_label = ctk.CTkLabel(stats, text="Hız: 0 B/sn")
        self.speed_label.grid(row=0, column=1)
        self.eta_label = ctk.CTkLabel(stats, text="Kalan: —", anchor="e")
        self.eta_label.grid(row=0, column=2, sticky="e")

        self.bytes_label = ctk.CTkLabel(self, text="0 B / 0 B", anchor="w", text_color="#A7B5C5")
        self.bytes_label.grid(row=4, column=0, padx=16, pady=(0, 6), sticky="ew")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=5, column=0, padx=16, pady=(2, 12), sticky="e")

        self.pause_button = ctk.CTkButton(buttons, text="Duraklat", width=100, command=self._pause_clicked)
        self.pause_button.pack(side="left", padx=(0, 8))
        self.cancel_button = ctk.CTkButton(buttons, text="İptal", width=90, fg_color="#C94155", hover_color="#A83446", command=self._cancel_clicked)
        self.cancel_button.pack(side="left")

    def _pause_clicked(self):
        self.paused = not self.paused
        self.pause_button.configure(text="Devam Et" if self.paused else "Duraklat")
        if callable(self.on_pause):
            self.on_pause(self.paused)

    def _cancel_clicked(self):
        if callable(self.on_cancel):
            self.on_cancel()

    def update_state(self, state: TransferState):
        now = time.monotonic()
        elapsed = max(0.001, now - self._last_time)

        speed = state.speed_bps
        if speed <= 0 and state.processed_bytes >= self._last_bytes:
            speed = (state.processed_bytes - self._last_bytes) / elapsed

        remaining = max(0, state.total_bytes - state.processed_bytes)
        eta = state.eta_seconds
        if eta is None and speed > 0 and state.total_bytes > 0:
            eta = remaining / speed

        pct = state.percent
        self.progress.set(pct / 100.0)
        self.percent_label.configure(text=f"{pct:.0f}%")
        self.file_label.configure(text=state.current_file or state.status)
        self.files_label.configure(text=f"Dosya: {state.processed_files} / {state.total_files}")
        self.speed_label.configure(text=f"Hız: {_human_bytes(speed)}/sn")
        self.eta_label.configure(text=f"Kalan: {_human_eta(eta)}")
        self.bytes_label.configure(text=f"{_human_bytes(state.processed_bytes)} / {_human_bytes(state.total_bytes)}")
        self.title_label.configure(text=state.status or "Dosyalar arşivleniyor")

        self._last_bytes = state.processed_bytes
        self._last_time = now

    def set_idle(self):
        self.update_state(TransferState())
        self.title_label.configure(text="Arşivleme hazır")
        self.file_label.configure(text="Tarama başlatıldığında işlem ayrıntıları burada görünecek")
        self.eta_label.configure(text="Kalan: —")


# V16.1 entegrasyon örneği:
#
# self.transfer_panel = WindowsTransferPanel(
#     parent_frame,
#     on_pause=self._on_archive_pause,
#     on_cancel=self._on_archive_cancel,
# )
# self.transfer_panel.pack(fill="x", padx=12, pady=8)
#
# Arşivleme döngüsünde her dosya/progress güncellemesinde:
# self.transfer_panel.update_state(TransferState(
#     current_file=current_path.name,
#     processed_files=index,
#     total_files=len(files),
#     processed_bytes=done_bytes,
#     total_bytes=total_bytes,
#     status="Arşivleme devam ediyor",
# ))
