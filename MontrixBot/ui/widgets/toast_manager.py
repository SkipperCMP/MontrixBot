from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List
import tkinter as tk


@dataclass
class Toast:
    text: str
    ttl_ms: int = 3500
    kind: str = "info"  # info | warn | error


class ToastManager:
    """
    Неблокирующие toast-уведомления для Tkinter.

    - Не использует messagebox (не блокирует UI)
    - Очередь уведомлений
    - Автоскрытие по TTL
    - Можно встроить в любое окно (app_step9, main_app)
    """

    def __init__(self, root: tk.Misc):
        self.root = root
        self._queue: List[Toast] = []
        self._current: Optional[tk.Toplevel] = None
        self._hide_after_id: Optional[str] = None

    def show(self, text: str, *, ttl_ms: int = 3500, kind: str = "info") -> None:
        self._queue.append(Toast(text=text, ttl_ms=ttl_ms, kind=kind))
        if self._current is None:
            self._dequeue_and_show()

    def info(self, text: str, *, ttl_ms: int = 3500) -> None:
        self.show(text, ttl_ms=ttl_ms, kind="info")

    def warn(self, text: str, *, ttl_ms: int = 4500) -> None:
        self.show(text, ttl_ms=ttl_ms, kind="warn")

    def error(self, text: str, *, ttl_ms: int = 6500) -> None:
        self.show(text, ttl_ms=ttl_ms, kind="error")

    def _dequeue_and_show(self) -> None:
        if not self._queue:
            self._current = None
            return

        toast = self._queue.pop(0)

        w = tk.Toplevel(self.root)
        self._current = w
        w.overrideredirect(True)
        w.attributes("-topmost", True)

        # позиция: правый нижний угол root
        try:
            self.root.update_idletasks()
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
        except Exception:
            rx, ry, rw, rh = 100, 100, 900, 700

        width = 420
        height = 90
        pad = 18
        x = rx + max(0, rw - width - pad)
        y = ry + max(0, rh - height - pad)
        w.geometry(f"{width}x{height}+{x}+{y}")

        frame = tk.Frame(w, bd=1, relief="solid")
        frame.pack(fill="both", expand=True)

        title = "INFO"
        if toast.kind == "warn":
            title = "WARN"
        elif toast.kind == "error":
            title = "ERROR"

        lbl_title = tk.Label(frame, text=title, anchor="w", font=("Segoe UI", 10, "bold"))
        lbl_title.pack(fill="x", padx=12, pady=(10, 0))

        lbl_text = tk.Label(frame, text=toast.text, anchor="w", justify="left", wraplength=390)
        lbl_text.pack(fill="both", expand=True, padx=12, pady=(6, 10))

        # закрытие по клику
        for wdg in (frame, lbl_title, lbl_text):
            wdg.bind("<Button-1>", lambda _e: self._hide_current())

        # автозакрытие
        self._hide_after_id = self.root.after(toast.ttl_ms, self._hide_current)

    def _hide_current(self) -> None:
        if self._hide_after_id is not None:
            try:
                self.root.after_cancel(self._hide_after_id)
            except Exception:
                pass
            self._hide_after_id = None

        if self._current is not None:
            try:
                self._current.destroy()
            except Exception:
                pass
            self._current = None

        self.root.after(50, self._dequeue_and_show)
