# MontrixBot
# UI-лаунчер с:
#  - Buy/Close/Panic через scripts/real_*_market.py
#  - SAFE-индикатором
#  - просмотром журнала / runtime-папки
#  - статическим и LIVE-чартом (Price + RSI + MACD)
#  - простыми сигналами по RSI+MACD (core.signals.simple_rsi_macd_signal)

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple, Optional

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# --- ensure project root is on sys.path ---
try:
    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
except Exception:
    pass

# Dark-тема вынесена в отдельный модуль (Step 1.2.8)
try:
    from .theme_dark import apply_neutral_dark
except Exception:
    try:
        from ui.theme_dark import apply_neutral_dark
    except Exception:
        apply_neutral_dark = None  # type: ignore[assignment]

from tools.formatting import fmt_price, fmt_pnl

# ---------------------------------------------------------------------------
#  Универсальные импорты ChartPanel / indicators / signals
# ---------------------------------------------------------------------------

def _try_import_chartpanel():
    last_error = None
    # 1) запуск как пакет: python -m ui.app_step8
    try:
        from .widgets.chart_panel import ChartPanel as _CP  # type: ignore
        return _CP, None
    except Exception as e:  # noqa: BLE001
        last_error = e

    # 2) запуск как скрипт: python ui/app_step8.py
    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from ui.widgets.chart_panel import ChartPanel as _CP  # type: ignore
        return _CP, None
    except Exception as e:  # noqa: BLE001
        last_error = e

    return None, last_error


def _try_import_uiapi():
    last_error = None
    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from core.ui_api import UIAPI as _UI  # type: ignore
        return _UI, None
    except Exception as e:  # noqa: BLE001
        last_error = e
    return None, last_error


def _try_import_statusbar():
    last_error = None
    # 1) запуск как пакет: python -m ui.app_step9
    try:
        from .widgets.status_bar import StatusBar as _SB  # type: ignore
        return _SB, None
    except Exception as e:  # noqa: BLE001
        last_error = e

    # 2) запуск как скрипт: python ui/app_step9.py
    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from ui.widgets.status_bar import StatusBar as _SB  # type: ignore
        return _SB, None
    except Exception as e:  # noqa: BLE001
        last_error = e

    return None, last_error


def _try_import_dealsjournal():
    last_error = None
    # 1) запуск как пакет: python -m ui.app_step8
    try:
        from .widgets.deals_journal import DealsJournal as _DJ  # type: ignore
        return _DJ, None
    except Exception as e:  # noqa: BLE001
        last_error = e

    # 2) запуск как скрипт: python ui/app_step8.py
    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from ui.widgets.deals_journal import DealsJournal as _DJ  # type: ignore
        return _DJ, None
    except Exception as e:  # noqa: BLE001
        last_error = e

    return None, last_error


def _try_import_indicators():
    last_error = None
    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from core import indicators as INDICATORS  # type: ignore
        return INDICATORS, None
    except Exception as e:  # noqa: BLE001
        last_error = e
    return None, last_error


def _try_import_signals():
    last_error = None
    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from core import signals as SIGNALS  # type: ignore
        return SIGNALS, None
    except Exception as e:  # noqa: BLE001
        last_error = e
    return None, last_error


def _try_import_advisor():
    last_error = None
    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from core import advisor as ADVISOR  # type: ignore
        return ADVISOR, None
    except Exception as e:  # noqa: BLE001
        last_error = e
    return None, last_error


def _try_import_autosim():
    last_error = None
    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from core.sim.auto_from_signals import AutoSimFromSignals, AutoSimConfig  # type: ignore
        return (AutoSimFromSignals, AutoSimConfig), None
    except Exception as e:  # noqa: BLE001
        last_error = e
    return None, last_error


# --- runtime bootstrap helper (Step2) ---
try:
    from tools.runtime_bootstrap import ensure_ticks_bootstrap
except Exception:  # fallback: no-op
    def ensure_ticks_bootstrap(
        symbol: str,
        max_points: int = 300,
        interval: str = "1m",
        min_points: int = 50,
    ) -> int:
        return 0

ChartPanel, _CHART_ERR = _try_import_chartpanel()
StatusBar, _STATUS_ERR = _try_import_statusbar()
DealsJournal, _JOURNAL_ERR = _try_import_dealsjournal()
INDICATORS, _IND_ERR = _try_import_indicators()
SIGNALS, _SIG_ERR = _try_import_signals()
ADVISOR, _ADV_ERR = _try_import_advisor()
UIAPI, _UI_ERR = _try_import_uiapi()
AUTOSIM_FACTORY, _AUTOSIM_ERR = _try_import_autosim()

# ---------------------------------------------------------------------------
#  Константы путей
# ---------------------------------------------------------------------------

APP_TITLE = "MontrixBot — UI Step9 (dark theme + widgets)"
ROOT_DIR = Path(__file__).resolve().parent.parent
SAFE_FILE = ROOT_DIR / "SAFE_MODE"
RUNTIME_DIR = ROOT_DIR / "runtime"
SCRIPTS_DIR = ROOT_DIR / "scripts"
JOURNAL_FILE = RUNTIME_DIR / "trades.jsonl"
TICKS_FILE = RUNTIME_DIR / "ticks_stream.jsonl"
SIGNALS_FILE = RUNTIME_DIR / "signals.jsonl"

DEFAULT_SYMBOLS = ["ADAUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title(APP_TITLE)
        self.configure(bg="#1c1f24")
        self.geometry("1120x640")
        self.minsize(980, 540)

        self.var_symbol = tk.StringVar(value=DEFAULT_SYMBOLS[0])
        self.var_qty = tk.StringVar(value="9")
        self.safe_on: bool = False
        self._mode: str = "SIM"

        # UI-флаг для Dry-Run бейджа (пока влияет только на внешний вид и логи)
        self.dry_run_ui_on: bool = True

        # настройки лога (ограничение длины и дешёвые обновления)
        self._log_max_lines: int = 3000
        self._log_trim_chunk: int = 500
        self._log_trim_every: int = 20
        self._log_lines_added: int = 0

        # кэш последнего текста для Active positions, чтобы не перерисовывать без нужды
        self._last_active_text: str = ""

        # состояние сигналов
        self._last_signal_side: Optional[str] = None

        # состояние авто-SIM
        self._autosim = None
        self._sim_log_state = None  # (equity, open_positions)
        self._sim_symbol: Optional[str] = None
        # ссылка на виджет журнала сделок (для router-обновления)
        self._deals_journal_widget = None


        if AUTOSIM_FACTORY is not None:
            try:
                AutoSimFromSignals, AutoSimConfig = AUTOSIM_FACTORY
                self._autosim = AutoSimFromSignals(config=AutoSimConfig())
            except Exception:
                self._autosim = None

        self._build_styles()
        self._build_topbar()
        self._build_paths()
        self._build_activepos()
        self._build_log()
        self._load_sim_state_from_file()

        # режим по умолчанию — SIM (через UIAPI)
        self._set_mode("SIM")
        
        # NEW: если UIAPI уже был создан, синхронизируем режим и там
        api = getattr(self, "_uiapi", None)
        if api is not None:
            try:
                api.set_mode("SIM")
            except Exception:
                pass

        self._log_diag_startup()

        self._refresh_safe_badge()
        self.after(1000, self._periodic_refresh)

    # ------------------------------------------------------------------ UI --
    def _build_styles(self) -> None:
        """
        Step 1.2.8:
        - вместо локальной простенькой темы используем ui.theme_dark.apply_neutral_dark
        - оставляем fallback на старые стили, если модуль недоступен
        """
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Пытаемся применить общую dark-тему
        palette_bg = None
        if apply_neutral_dark is not None:
            try:
                palette = apply_neutral_dark(style)
                if isinstance(palette, dict):
                    palette_bg = palette.get("bg")
            except Exception:
                palette_bg = None

        # Fallback на старую схему, если тема не применилась
        if palette_bg is None:
            # старые значения из app_step9 (ранее app_step8)
            bg = "#1c1f24"
            fg = "#e6e6e6"
            muted = "#9aa0a6"

            style.configure("Dark.TFrame", background=bg)
            style.configure("Dark.TLabel", background=bg, foreground=fg)
            style.configure("Muted.TLabel", background=bg, foreground=muted)
            style.configure(
                "BadgeSafe.TLabel",
                background="#26a269",
                foreground="#0b0b0b",
                padding=(8, 2),
            )
            style.configure(
                "BadgeWarn.TLabel",
                background="#d0b343",
                foreground="#0b0b0b",
                padding=(8, 2),
            )
            style.configure(
                "BadgeDanger.TLabel",
                background="#e01b24",
                foreground="#0b0b0b",
                padding=(8, 2),
            )
        else:
            # если тема отдала палитру — подстраиваем фон окна под неё
            try:
                self.configure(bg=palette_bg)
            except Exception:
                pass

        # Общие стили кнопок / полей
        style.configure("Dark.TButton", padding=6)
        style.map("Dark.TButton", background=[("active", "#2a2f36")])

        style.configure("Log.TFrame", background="#121417")
        style.configure(
            "EntryDark.TEntry",
            fieldbackground="#121417",
            foreground="#e6e6e6",
        )
        style.configure(
            "ComboDark.TCombobox",
            fieldbackground="#121417",
            foreground="#e6e6e6",
        )

    def _build_topbar(self) -> None:
        """Построение верхней панели вынесено в ui.widgets.controls_bar."""
        try:
            from .widgets.controls_bar import build_topbar_ui  # type: ignore
        except Exception:
            # запуск как скрипт: python ui/app_step9.py
            root = Path(__file__).resolve().parent.parent
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from ui.widgets.controls_bar import build_topbar_ui  # type: ignore

        build_topbar_ui(self, DEFAULT_SYMBOLS)

    def _build_paths(self) -> None:
        """Строка с кнопками журналов/графиков — вынесена в ui.widgets.controls_bar."""
        try:
            from .widgets.controls_bar import build_paths_ui  # type: ignore
        except Exception:
            # запуск как скрипт: python ui/app_step8.py
            root = Path(__file__).resolve().parent.parent
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from ui.widgets.controls_bar import build_paths_ui  # type: ignore

        build_paths_ui(self, JOURNAL_FILE, RUNTIME_DIR)

    def _build_activepos(self) -> None:
        """Панель активной позиции вынесена в ui.widgets.positions_panel."""
        try:
            from .widgets.positions_panel import build_activepos_ui  # type: ignore
        except Exception:
            # запуск как скрипт: python ui/app_step8.py
            root = Path(__file__).resolve().parent.parent
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from ui.widgets.positions_panel import build_activepos_ui  # type: ignore

        build_activepos_ui(self)

    def _build_log(self) -> None:
        """Лог-панель вынесена в ui.widgets.log_panel."""
        try:
            from .widgets.log_panel import build_log_ui  # type: ignore
        except Exception:
            # запуск как скрипт: python ui/app_step8.py
            root = Path(__file__).resolve().parent.parent
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from ui.widgets.log_panel import build_log_ui  # type: ignore

        build_log_ui(self, StatusBar)

    # ------------------------------------------------------------- helpers --
    def _load_sim_state_from_file(self) -> None:
        """Пробуем подхватить последний снимок SIM из sim_state.json при старте."""
        try:
            sim_state_path = RUNTIME_DIR / "sim_state.json"
            if not sim_state_path.exists():
                return
            txt = sim_state_path.read_text(encoding="utf-8")
            if not txt.strip():
                return
            snapshot = json.loads(txt)
        except Exception as e:
            # Логируем, но не роняем UI
            try:
                self._log(f"[SIM] failed to load sim_state.json: {e}")
            except Exception:
                pass
            return

        try:
            # Уже существующий метод, который красиво рисует таблицу Active position (SIM)
            self._update_active_from_sim(snapshot)
        except Exception:
            # Если формат файла изменился/битый — просто молча игнорируем
            pass
    
    def _set_active_text(self, text: str) -> None:
        """
        Заполняет панель Active positions и подсвечивает:
        - pnl_pos / pnl_neg: PnL% (зелёный/красный)
        - side_long / side_short: колонка Side (LONG / SHORT)

        Формат строк задаётся _update_active_from_sim:
            header -> "Symbol Side Qty Entry Last Value Pnl% TP SL Hold Trend"
            далее строки с теми же колонками.
        """
        box = getattr(self, "active_box", None)
        if box is None:
            return

        # кэшируем последний текст, чтобы не перерисовывать панель без изменений
        new_text = text or ""
        try:
            last_text = getattr(self, "_last_active_text", "")
        except Exception:
            last_text = ""
        if new_text == last_text:
            return
        try:
            self._last_active_text = new_text
        except Exception:
            # если не удалось сохранить кэш — продолжаем без оптимизации
            pass

        lines = new_text.splitlines()

        try:
            box.configure(state="normal")
            box.delete("1.0", "end")

            if not lines:
                box.insert("end", "— no active positions —")
                box.configure(state="disabled")
                return

            # Пишем построчно, чтобы знать индексы для тегов
            for row_idx, line in enumerate(lines, start=1):
                box.insert(f"{row_idx}.0", line + ("\n" if row_idx < len(lines) else ""))

            # Если нет заголовка с 'Pnl%' — нечего раскрашивать
            if not any("Pnl%" in ln for ln in lines):
                box.configure(state="disabled")
                return

            # Начиная с 3-й строки (после header и разделителя) раскрашиваем Side и PnL
            for row_idx, line in enumerate(lines, start=1):
                if row_idx <= 2:
                    continue  # header + "----"

                try:
                    parts = line.split()
                    # 0:Symbol 1:Side 2:Qty 3:Entry 4:Last 5:Value 6:Pnl% ...
                except Exception:
                    continue

                # --- подсветка Side ---
                try:
                    side_token = parts[1]
                    side_u = side_token.upper()
                    side_tag = None
                    if side_u.startswith("LONG") or side_u.startswith("BUY"):
                        side_tag = "side_long"
                    elif side_u.startswith("SHORT") or side_u.startswith("SELL"):
                        side_tag = "side_short"

                    if side_tag:
                        col_start = line.find(side_token)
                        if col_start >= 0:
                            col_end = col_start + len(side_token)
                            try:
                                box.tag_add(
                                    side_tag,
                                    f"{row_idx}.{col_start}",
                                    f"{row_idx}.{col_end}",
                                )
                            except Exception:
                                pass
                except Exception:
                    pass

                # --- подсветка PnL% ---
                try:
                    pnl_token = parts[6]
                except Exception:
                    continue

                # чистим от процентов и плюсиков
                raw = pnl_token.replace("%", "").replace("+", "").strip()
                try:
                    pnl_val = float(raw)
                except Exception:
                    continue

                if pnl_val > 0.0:
                    tag = "pnl_pos"
                elif pnl_val < 0.0:
                    tag = "pnl_neg"
                else:
                    continue

                col_start = line.find(pnl_token)
                if col_start < 0:
                    continue
                col_end = col_start + len(pnl_token)

                try:
                    box.tag_add(
                        tag,
                        f"{row_idx}.{col_start}",
                        f"{row_idx}.{col_end}",
                    )
                except Exception:
                    pass
                # --- маркер тренда в последней колонке ---
                try:
                    trend_token = parts[-1]
                    col_start = line.rfind(trend_token)
                    if col_start >= 0:
                        col_end = col_start + len(trend_token)
                        if pnl_val > 0.0:
                            ttag = "trend_up"
                        elif pnl_val < 0.0:
                            ttag = "trend_down"
                        else:
                            ttag = "trend_flat"
                        try:
                            box.tag_add(
                                ttag,
                                f"{row_idx}.{col_start}",
                                f"{row_idx}.{col_end}",
                            )
                        except Exception:
                            pass
                except Exception:
                    pass

            box.configure(state="disabled")
        except tk.TclError:
            # окно/виджет уже уничтожено — игнорируем обновление панели
            return

    def _update_active_from_sim(self, snapshot: dict) -> None:
        """Update Active position panel.

        1) Пытаемся взять позиции из ядра (UIAPI.get_state_snapshot -> positions + ticks).
        2) Если там пусто/ошибка — используем snapshot["active"] от AUTOSIM, как раньше.
        """

        # --- базовый active от AUTOSIM (старое поведение) ---
        try:
            autosim_active = snapshot.get("active") or []
        except Exception:
            autosim_active = []

        # --- пробуем собрать active из ядра (TPSL + StateEngine) ---
        core_active = []
        try:
            api = self._ensure_uiapi()
            if api is not None and hasattr(api, "get_state_snapshot"):
                se_snap = api.get_state_snapshot() or {}
                positions = se_snap.get("positions") or {}
                ticks = se_snap.get("ticks") or {}

                for sym, pos in positions.items():
                    try:
                        sym_u = str(sym or "").upper()
                        side = str(pos.get("side", "") or "")
                        qty = float(pos.get("qty", 0.0) or 0.0)
                        entry = float(pos.get("entry", 0.0) or 0.0)

                        tick = ticks.get(sym_u, {}) or {}
                        last_raw = tick.get("last", entry)
                        try:
                            last = float(last_raw)
                        except Exception:
                            last = entry

                        # считаем PnL% по side
                        pnl_pct = 0.0
                        if entry > 0.0 and last > 0.0:
                            side_u = side.upper()
                            if side_u.startswith("LONG") or side_u == "BUY":
                                pnl_pct = (last - entry) / entry * 100.0
                            elif side_u.startswith("SHORT") or side_u == "SELL":
                                pnl_pct = (entry - last) / entry * 100.0

                        core_active.append(
                            {
                                "symbol": sym_u,
                                "side": side,
                                "qty": qty,
                                "entry_price": entry,
                                "current_price": last,
                                "unrealized_pnl_pct": pnl_pct,
                                "tp": float(pos.get("tp", 0.0) or 0.0),
                                "sl": float(pos.get("sl", 0.0) or 0.0),
                                # hold_days пока не считаем для TPSL-позиций
                                "hold_days": float(0.0),
                            }
                        )
                    except Exception:
                        continue
        except Exception:
            core_active = []

        # --- выбираем источник: ядро > AUTOSIM ---
        if core_active:
            active = core_active
        else:
            active = autosim_active

        if not active:
            self._set_active_text("— no active positions —")
            return

        def _format_hold(hold_days: float) -> str:
            """Преобразовать количество дней в человекочитаемый формат."""
            try:
                total_minutes = int(float(hold_days) * 24 * 60)
            except Exception:
                return "--:--"

            if total_minutes < 0:
                total_minutes = 0

            days = total_minutes // (24 * 60)
            rem = total_minutes % (24 * 60)
            hours = rem // 60
            minutes = rem % 60

            if days <= 0:
                # только часы:минуты
                return f"{hours:02d}:{minutes:02d}"
            # дни + часы:минуты
            return f"{days}d {hours:02d}:{minutes:02d}"

        lines: list[str] = []
        header = "{:<10} {:<6} {:>9} {:>10} {:>10} {:>10} {:>7} {:>10} {:>10} {:>9} {:>5}".format(
            "Symbol",
            "Side",
            "Qty",
            "Entry",
            "Last",
            "Value",
            "Pnl%",
            "TP",
            "SL",
            "Hold",
            "Trend",
        )
        lines.append(header)
        lines.append("-" * len(header))

        for pos in active:
            symbol = str(pos.get("symbol", ""))
            side = str(pos.get("side", ""))[:6]
            qty = float(pos.get("qty", 0.0) or 0.0)
            entry = float(pos.get("entry_price", 0.0) or 0.0)
            last = float(pos.get("current_price", 0.0) or 0.0)

            # базовый PnL% из снапшота (если есть)
            try:
                pnl_pct = float(pos.get("unrealized_pnl_pct", 0.0) or 0.0)
            except Exception:
                pnl_pct = 0.0

            # если движок не посчитал PnL%, считаем сами
            if entry > 0.0 and last > 0.0:
                try:
                    if abs(pnl_pct) < 0.0001:
                        side_u = side.upper()
                        if side_u.startswith("LONG") or side_u == "BUY":
                            pnl_pct = (last - entry) / entry * 100.0
                        elif side_u.startswith("SHORT") or side_u == "SELL":
                            pnl_pct = (entry - last) / entry * 100.0
                except Exception:
                    pass

            # стоимость позиции
            try:
                value = qty * last
            except Exception:
                value = 0.0

            tp = float(pos.get("tp", 0.0) or 0.0)
            sl = float(pos.get("sl", 0.0) or 0.0)
            hold_days = float(pos.get("hold_days", 0.0) or 0.0)
            hold_str = _format_hold(hold_days)
            
            # маркер тренда по знаку PnL% (используем пули, цвет задаётся тегами)
            if pnl_pct > 0.1:
                trend_mark = "●"
            elif pnl_pct < -0.1:
                trend_mark = "●"
            else:
                trend_mark = "·"
            line = (
                "{:<10} {:<6} {:>9.4f} {:>10.4f} {:>10.4f} {:>10.2f} "
                "{:>7.2f} {:>10.4f} {:>10.4f} {:>9} {:>5}"
            ).format(
                symbol,
                side,
                qty,
                entry,
                last,
                value,
                pnl_pct,
                tp,
                sl,
                hold_str,
                trend_mark,
            )
            lines.append(line)

        self._set_active_text("\n".join(lines))

    def _update_equity_bar(self, snapshot: dict) -> None:
        """Обновляет мини-панель Equity на верхней панели.

        Формат (компактный, читаемый):
            Eqt 1 000.00   D +0.31%   P +7.86/+0.79%   L 102.44   E[t123 v45 U]
        """
        # если по какой-то причине var_equity ещё не создана — тихо выходим
        if not hasattr(self, "var_equity"):
            return

        snapshot = snapshot or {}

        # аккуратно достаём портфель из снапшота
        try:
            portfolio = snapshot.get("portfolio") or {}
        except Exception:
            self.var_equity.set("Eqt —")
            return

        eq = portfolio.get("equity")
        if eq is None:
            self.var_equity.set("Eqt —")
            return

        try:
            eq_f = float(eq)
        except Exception:
            self.var_equity.set("Eqt —")
            return

        # --- общий PnL (в процентах) ---
        total_pct = None
        try:
            total_pct_val = portfolio.get("pnl_total_pct", None)
            if total_pct_val is not None:
                total_pct = float(total_pct_val)
        except Exception:
            total_pct = None

        # дифф по equity (если есть общий PnL и equity)
        total_diff = None
        if total_pct is not None:
            try:
                total_diff = eq_f * float(total_pct) / 100.0
            except Exception:
                total_diff = None

        # --- дневной PnL ---
        day_pct = None
        try:
            day_val = portfolio.get("pnl_day_pct", None)
            if day_val is not None:
                day_pct = float(day_val)
        except Exception:
            day_pct = None

        # --- last price из StateEngine / UIAPI ---
        last_price = None
        try:
            api = self._ensure_uiapi()
            if api is not None and hasattr(api, "get_last_price"):
                # symbol берётся из UIAPI.current_symbol, который мы синхронизируем
                last_price = api.get_last_price()
        except Exception:
            last_price = None

        # --- mini engine status из снапшота ядра ---
        eng_ticks = None
        eng_ver = None
        eng_trend = None
        try:
            api2 = self._ensure_uiapi()
            if api2 is not None and hasattr(api2, "get_state_snapshot"):
                eng_snap = api2.get_state_snapshot() or {}
                ticks_dict = eng_snap.get("ticks") or {}
                try:
                    eng_ticks = len(ticks_dict)
                except Exception:
                    eng_ticks = None
                eng_ver = eng_snap.get("version")
                eng_trend = eng_snap.get("trend")
        except Exception:
            pass

        # --- формируем строку (компактную и читабельную) ---
        parts: list[str] = []

        # Equity (с разделителями тысяч)
        try:
            parts.append(f"Eqt {fmt_price(eq_f)}")
        except Exception:
            parts.append(f"Eqt {eq_f:.2f}")

        # Day PnL (если есть) — иначе ставим плейсхолдер, чтобы выровнять строку
        if day_pct is not None:
            try:
                parts.append(f"D {fmt_pnl(day_pct)}%")
            except Exception:
                parts.append(f"D {day_pct:+.2f}%")
        else:
            parts.append("D —%")

        # Total PnL (если есть) — иначе плейсхолдер
        if total_pct is not None:
            try:
                if total_diff is not None:
                    parts.append(f"P {fmt_pnl(total_diff)}/{fmt_pnl(total_pct)}%")
                else:
                    parts.append(f"P {fmt_pnl(total_pct)}%")
            except Exception:
                if total_diff is not None:
                    parts.append(f"P {total_diff:+.2f}/{total_pct:+.2f}%")
                else:
                    parts.append(f"P {total_pct:+.2f}%")
        else:
            parts.append("P —%")

        # Mode (SIM/REAL) и SAFE ON/OFF — компактный блок после PnL
        try:
            mode = None
            try:
                # сначала пробуем взять режим из снапшота (UIAPI/state_engine)
                mode = snapshot.get("mode")
            except Exception:
                mode = None
            if not mode:
                # fallback: внутреннее поле UI
                mode = getattr(self, "_mode", "SIM")
            mode_str = str(mode).upper()
            parts.append(f"M:{mode_str}")
        except Exception:
            pass

        try:
            # SAFE-индикатор берём из флага UI
            safe_on = bool(getattr(self, "safe_on", False))
            safe_text = "SAFE:ON" if safe_on else "SAFE:OFF"
            parts.append(safe_text)
        except Exception:
            pass

        # Last price
        if last_price is not None:
            try:
                parts.append(f"L {fmt_price(last_price)}")
            except Exception:
                try:
                    parts.append(f"L {float(last_price):.2f}")
                except Exception:
                    pass

        # Engine compact format
        try:
            t = f"t{eng_ticks}" if eng_ticks is not None else ""
            v = f"v{eng_ver}" if eng_ver is not None else ""
            tr = eng_trend[0].upper() if isinstance(eng_trend, str) and eng_trend else ""
            eng = " ".join(s for s in (t, v, tr) if s).strip()
            if eng:
                parts.append(f"E[{eng}]")
        except Exception:
            pass

        text = "   ".join(parts) if parts else "Eqt —"
        # избегаем лишних перерисовок и ловим TclError, если окно уже закрыто
        try:
            current = self.var_equity.get()
        except Exception:
            current = None
        if current == text:
            return
        try:
            self.var_equity.set(text)
        except tk.TclError:
            # виджет уже уничтожен — просто выходим
            return

    def _append_equity_history(self, snapshot: dict) -> None:
        """Дописывает точку equity в runtime/equity_history.csv (best-effort)."""
        try:
            portfolio = snapshot.get("portfolio") or {}
            eq = portfolio.get("equity")
            if eq is None:
                return

            try:
                eq_f = float(eq)
            except Exception:
                return

            ts = snapshot.get("ts") or int(time.time())
            # PnL-метрики (могут отсутствовать)
            day_pct = portfolio.get("pnl_day_pct", None)
            total_pct = portfolio.get("pnl_total_pct", None)

            try:
                day_pct_f = float(day_pct) if day_pct is not None else None
            except Exception:
                day_pct_f = None
            try:
                total_pct_f = float(total_pct) if total_pct is not None else None
            except Exception:
                total_pct_f = None

            path = RUNTIME_DIR / "equity_history.csv"
            is_new = not path.exists()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                if is_new:
                    f.write("ts,equity,pnl_day_pct,pnl_total_pct,mode\n")
                # mode: SIM / REAL и т.п.
                mode = getattr(self, "_mode", "SIM")
                day_str = f"{day_pct_f:.4f}" if day_pct_f is not None else ""
                total_str = f"{total_pct_f:.4f}" if total_pct_f is not None else ""
                f.write(f"{int(ts)},{eq_f:.4f},{day_str},{total_str},{mode}\n")
        except Exception:
            # не даём ошибкам логгера ломать основной цикл
            return
            
    def _update_equity_bar(self, snapshot: dict | None) -> None:
        """Обновляет мини-панель портфеля по snapshot['portfolio']."""
        me = getattr(self, "mini_equity", None)
        if me is None:
            return

        snapshot = snapshot or {}
        portfolio = snapshot.get("portfolio")
        if not isinstance(portfolio, dict):
            portfolio = {}

        try:
            me.update(portfolio)
        except Exception:
            # ошибки mini-панели не должны ломать основной UI
            return
            
    def _update_status_bar(self, snapshot: dict | None) -> None:
        """Обновляет StatusBar: режим, lag, health и последнюю сделку."""
        # сначала пробуем обновить мини-панель портфеля
        try:
            self._update_equity_bar(snapshot)
        except Exception:
            pass

        sb = getattr(self, "status_bar", None)
        if sb is None:
            return

        snapshot = snapshot or {}

        # --- MODE ---
        try:
            mode = getattr(self, "_mode", "SIM") or "SIM"
            sb.set_mode(mode)
        except Exception:
            pass

        # --- HEALTH + LAG ---
        health = {}
        raw_health = snapshot.get("health")
        if isinstance(raw_health, dict):
            health = raw_health

        lag_sec = 0
        try:
            # если есть latency_ms в health — используем его
            latency_ms = health.get("latency_ms")
            if latency_ms is not None:
                lag_sec = max(0, int(float(latency_ms) / 1000.0))
            else:
                # иначе считаем lag по ts снапшота
                ts = snapshot.get("ts")
                if ts is not None:
                    try:
                        ts_f = float(ts)
                    except Exception:
                        ts_f = float(time.time())
                    lag_sec = max(0, int(time.time() - ts_f))
        except Exception:
            lag_sec = 0

        try:
            sb.set_lag(lag_sec)
        except Exception:
            pass

        try:
            sb.set_health(health)
        except Exception:
            pass

        # --- LAST DEAL ---
        try:
            last_deal = None
            rows = snapshot.get("trades_recent")
            if isinstance(rows, list) and rows:
                # берём самую свежую запись
                last_deal = rows[-1]
            sb.set_last_deal(last_deal)
        except Exception:
            # не ломаем UI при странном формате снапшота
            pass

    def _on_reset_sim(self) -> None:
        """Reset SIM engine (best-effort) and clear Active position."""
        try:
            if self._autosim is not None:
                if AUTOSIM_FACTORY is not None:
                    try:
                        AutoSimFromSignals, AutoSimConfig = AUTOSIM_FACTORY
                        self._autosim = AutoSimFromSignals(config=AutoSimConfig())
                    except Exception:
                        try:
                            engine = getattr(self._autosim, "engine", None)
                            if engine is not None:
                                engine.active_positions.clear()
                                engine.closed_trades.clear()
                        except Exception:
                            pass
            self._sim_log_state = None
            self._sim_symbol = None
            try:
                sim_state_path = RUNTIME_DIR / "sim_state.json"
                if sim_state_path.exists():
                    sim_state_path.unlink()
            except Exception:
                pass
            self._set_active_text("— no active positions —")
            self._log("[SIM] reset requested")
        except Exception as e:
            try:
                self._log(f"[SIM] reset error: {e}")
            except Exception:
                pass

    def _log(self, line: str) -> None:
        """Добавляет строку в лог с ограничением длины и защитой от TclError."""
        text = (line or "").rstrip("\n")
        # не добавляем пустые строки
        if not text.strip():
            return

        try:
            self.log.insert("end", text + "\n")
            self.log.see("end")
        except tk.TclError:
            # окно уже уничтожено — игнорируем
            return

        # счётчик вставок, чтобы не считать строки каждый раз
        try:
            self._log_lines_added += 1
        except Exception:
            # на всякий случай инициализируем, если не успели в __init__
            self._log_lines_added = 1

        try:
            trim_every = int(getattr(self, "_log_trim_every", 20) or 0)
            max_lines = int(getattr(self, "_log_max_lines", 3000) or 0)
            trim_chunk = int(getattr(self, "_log_trim_chunk", 500) or 0)
        except Exception:
            trim_every, max_lines, trim_chunk = 20, 3000, 500

        if trim_every > 0 and max_lines > 0 and trim_chunk > 0:
            if self._log_lines_added % trim_every == 0:
                # мягкая проверка длины лога
                try:
                    end_index = self.log.index("end-1c")
                    num_lines = int(str(end_index).split(".")[0])
                except Exception:
                    num_lines = 0

                if num_lines > max_lines:
                    try:
                        self.log.delete("1.0", f"{trim_chunk}.0")
                    except tk.TclError:
                        # если виджет уже уничтожен — просто выходим
                        return

    def clear_log(self) -> None:
        """Полная очистка лога с мягким сбросом счётчика."""
        try:
            self.log.delete("1.0", "end")
        except tk.TclError:
            return
        except Exception:
            # другие ошибки тоже не должны ломать UI
            return
        # сбрасываем счётчик вставок
        try:
            self._log_lines_added = 0
        except Exception:
            pass

    def _open_path(self, p: Path) -> None:
        p = Path(p)
        if p.is_file() or p.is_dir():
            try:
                if os.name == "nt":
                    os.startfile(str(p))  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["xdg-open", str(p)])
            except Exception as e:
                messagebox.showwarning("Open", f"Failed to open: {e}")
        else:
            messagebox.showinfo("Open", f"Path not found: {p}")

    def _safe_is_on(self) -> bool:
        try:
            return SAFE_FILE.exists()
        except Exception:
            return False

    def _refresh_safe_badge(self) -> None:
        self.safe_on = self._safe_is_on()
        if self.safe_on:
            self.badge_safe.configure(text="SAFE", style="BadgeSafe.TLabel")
        else:
            self.badge_safe.configure(text="SAFE OFF", style="BadgeDanger.TLabel")

        # SAFE блокирует только REAL-закрытие
        mode = getattr(self, "_mode", "SIM")
        if mode == "REAL":
            self.btn_close.configure(state="disabled" if self.safe_on else "normal")
        else:
            self.btn_close.configure(state="normal")

    def _toggle_safe(self) -> None:
        """Переключение SAFE_MODE по клику на бейдже."""
        try:
            if SAFE_FILE.exists():
                # выключаем SAFE
                try:
                    SAFE_FILE.unlink()
                except FileNotFoundError:
                    pass
                self._log("[SAFE] SAFE_MODE disabled via UI (REAL close allowed)")
            else:
                SAFE_FILE.touch()
                self._log("[SAFE] SAFE_MODE enabled via UI (REAL close blocked)")
        except Exception as e:  # noqa: BLE001
            try:
                self._log(f"[SAFE][ERR] cannot toggle SAFE_MODE: {e!r}")
            except Exception:
                pass
        # обновляем бейдж и состояние кнопки Close
        try:
            self._refresh_safe_badge()
        except Exception:
            pass

    def _refresh_dry_badge(self) -> None:
        """Обновляет внешний вид бейджа Dry-Run по self.dry_run_ui_on."""
        # если бейдж ещё не создан (ранний вызов) — просто выходим
        badge = getattr(self, "badge_dry", None)
        if badge is None:
            return

        try:
            val = bool(getattr(self, "dry_run_ui_on", True))
        except Exception:
            val = True
        self.dry_run_ui_on = val

        text = "Dry-Run" if val else "REAL CLI"
        style = "BadgeWarn.TLabel" if val else "BadgeDanger.TLabel"

        try:
            badge.configure(text=text, style=style)
        except tk.TclError:
            return

    def _toggle_dry(self) -> None:
        """Переключение Dry-Run бейджа (пока влияет только на UI и логи)."""
        try:
            current = bool(getattr(self, "dry_run_ui_on", True))
        except Exception:
            current = True
        self.dry_run_ui_on = not current

        state = "ON" if self.dry_run_ui_on else "OFF"
        try:
            self._log(f"[DRY] Dry-Run badge toggled to {state} (UI only, CLI still uses --ask)")
        except Exception:
            pass

        try:
            self._refresh_dry_badge()
        except Exception:
            pass

    def _set_mode(self, mode: str) -> None:
        """Переключение режима UI: SIM или REAL."""
        mode = (mode or "SIM").upper()
        self._mode = mode
        if hasattr(self, "var_mode"):
            self.var_mode.set(f"Mode: {mode}")

        # Перепривязываем команды кнопок в зависимости от режима
        if mode == "SIM":
            self.btn_buy.configure(command=self.on_buy_sim)
            self.btn_close.configure(command=self.on_close_sim)
        else:
            self.btn_buy.configure(command=self.on_buy_real)
            self.btn_close.configure(command=self.on_close_real)

        # После смены режима обновим SAFE-индикацию
        try:
            self._refresh_safe_badge()
        except Exception:
            pass

    def _toggle_mode(self) -> None:
        new_mode = "REAL" if getattr(self, "_mode", "SIM") == "SIM" else "SIM"
        self._set_mode(new_mode)
        
        # NEW: если UIAPI уже создан, обновляем режим и в ядре
        
        api = getattr(self, "_uiapi", None)
        if api is not None:
            try:
                api.set_mode(new_mode)
            except Exception:
                pass
                
        self._log(f"[UI] switched mode to {new_mode}")

    def _set_status(self, text: str) -> None:
        self.title(f"{APP_TITLE} — {text}" if text else APP_TITLE)

    def _log_diag_startup(self) -> None:
        self._log(f"[DIAG] python={sys.executable}")

        if ChartPanel is None:
            self._log("[DIAG] ChartPanel=None")
            if _CHART_ERR is not None:
                self._log(f"[DIAG] ChartPanel import error: {_CHART_ERR!r}")
        else:
            self._log(f"[DIAG] ChartPanel={ChartPanel}")
        # Diagnostics: ui_api
        try:
            if UIAPI is None:
                self._log("[DIAG] ui_api unavailable (core.ui_api.UIAPI not imported)")
                if _UI_ERR is not None:
                    self._log(f"[DIAG] ui_api import error: {_UI_ERR!r}")
            else:
                self._log("[DIAG] ui_api OK (core.ui_api.UIAPI)")
        except Exception:
            pass


        try:
            import matplotlib  # type: ignore

            self._log(f"[DIAG] matplotlib={matplotlib.__version__}")
        except Exception:
            self._log("[DIAG] matplotlib not available")

        if INDICATORS is None:
            self._log("[DIAG] indicators not available (core.indicators)")
            if _IND_ERR is not None:
                self._log(f"[DIAG] indicators import error: {_IND_ERR!r}")
        else:
            self._log("[DIAG] indicators OK (core.indicators)")

        if SIGNALS is None:
            self._log("[DIAG] signals not available (core.signals)")
            if _SIG_ERR is not None:
                self._log(f"[DIAG] signals import error: {_SIG_ERR!r}")
        else:
            self._log("[DIAG] signals OK (core.signals)")

        if ADVISOR is None:
            self._log("[DIAG] advisor not available (core.advisor)")
            if _ADV_ERR is not None:
                self._log(f"[DIAG] advisor import error: {_ADV_ERR!r}")
        else:
            self._log("[DIAG] advisor OK (core.advisor)")

    # ----------------------------------------------------- periodic tasks --
    
    def _periodic_refresh(self) -> None:
        """Периодический апдейт SAFE, Dry-Run, индикаторов, сигналов и мини-панелей (раз в ~1 c)."""
        try:
            # SAFE-индикатор
            self._refresh_safe_badge()

            # Dry-Run бейдж (пока чисто UI)
            self._refresh_dry_badge()

            # индикаторы + сигналы + AUTOSIM
            self._refresh_indicators_and_signal()

            # синхронизируем текущий символ в ядро (UIAPI)
            self._push_current_symbol_to_uiapi()

            # НОВОЕ: подтягиваем снапшот из StateEngine/UIAPI
            # и обновляем мини-equity + статус-бар
            self._refresh_from_core_snapshot()
        except Exception as e:  # noqa: BLE001
            try:
                self._log(f"[DIAG] periodic error: {e!r}")
            except Exception:
                pass
        finally:
            self.after(1000, self._periodic_refresh)
  
    def _push_current_symbol_to_uiapi(self) -> None:
        """Отправить текущий символ из UI в UIAPI."""
        try:
            api = self._ensure_uiapi()
            if api is None or not hasattr(api, "set_current_symbol"):
                return
            sym = ""
            try:
                sym = self.var_symbol.get().strip()
            except Exception:
                pass
            api.set_current_symbol(sym)
        except Exception:
            # не ломаем UI, если что-то пошло не так
            pass

    def _refresh_from_core_snapshot(self) -> None:
        """Обновление мини-панелей (equity + статус-бар) из ядра (UIAPI/StateEngine)."""
        try:
            api = self._ensure_uiapi()
            if api is None or not hasattr(api, "get_state_snapshot"):
                return

            snapshot = api.get_state_snapshot()
            if not isinstance(snapshot, dict):
                return
        except Exception:
            return

        # 1) equity обновляем только если в snapshot['portfolio'] есть корректное значение
        try:
            portfolio = snapshot.get("portfolio") or {}
            eq = portfolio.get("equity")
        except Exception:
            eq = None

        if eq is not None:
            try:
                self._update_equity_bar(snapshot)
            except Exception:
                pass

        # 2) статус-бар обновляем всегда (там важен lag/режим)
        try:
            self._update_status_bar(snapshot)
        except Exception:
            pass
            
        # 3) журнал сделок (если зарегистрирован)
        try:
            dj = getattr(self, "_deals_journal_widget", None)
            if dj is not None and hasattr(dj, "update_from_snapshot"):
                dj.update_from_snapshot(snapshot)
        except Exception:
            pass

    # ----------------------------------------------------- indicators I/O --
    def _load_chart_prices(self, max_points: int = 300) -> Tuple[List[int], List[float]]:
        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]
        times: List[int] = []
        prices: List[float] = []

        # лёгкий bootstrap: если поток тиков пустой или короткий, попробуем подкачать историю с Binance
        boot_created = 0
        try:
            boot_created = ensure_ticks_bootstrap(sym, max_points=max_points, min_points=50)
        except Exception:
            boot_created = 0
        if boot_created > 0:
            try:
                self._log(f"[BOOTSTRAP] seeded {boot_created} ticks for {sym} from Binance REST")
            except Exception:
                pass

        path = TICKS_FILE
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    lines = f.readlines()[-max_points:]
                for line in lines:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if obj.get("symbol") and obj.get("symbol").upper() != sym.upper():
                        continue
                    price = obj.get("price") or obj.get("p") or obj.get("close")
                    if price is None:
                        continue
                    try:
                        price_f = float(price)
                    except Exception:
                        continue
                    prices.append(price_f)
                    times.append(len(times))
            except Exception:
                prices = []
                times = []

        return times, prices

    def _compute_last_indicators(
        self, prices: List[float]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if INDICATORS is None or len(prices) < 30:
            return None, None, None

        try:
            rsi_vals = INDICATORS.rsi(prices, period=14)
            macd_vals, signal_vals = INDICATORS.macd(prices)
            if not rsi_vals or not macd_vals or not signal_vals:
                return None, None, None
            return rsi_vals[-1], macd_vals[-1], signal_vals[-1]
        except Exception as e:  # noqa: BLE001
            self._log(f"[DIAG] indicators error: {e!r}")
            return None, None, None


    def _refresh_indicators_and_signal(self) -> None:
        """Recompute indicators, signal, advisor and SIM snapshot."""
        last_snapshot: dict | None = None
        times, prices = self._load_chart_prices(max_points=300)
        # синхронизируем текущий символ с UIAPI
        self._push_current_symbol_to_uiapi()
        rsi_last, macd_last, macd_signal_last = self._compute_last_indicators(prices)

        # --- update RSI / MACD labels ---
        if rsi_last is None:
            self.label_rsi.configure(text="RSI: n/a")
        else:
            self.label_rsi.configure(text=f"RSI: {rsi_last:4.1f}")

        if macd_last is None or macd_signal_last is None:
            self.label_macd.configure(text="MACD: n/a")
        else:
            self.label_macd.configure(text=f"MACD: {macd_last:+.4f}")

        # --- compute EMA20 / EMA50 for filters ---
        ema_fast_last = None
        ema_slow_last = None
        price_last = None

        if prices:
            try:
                price_last = float(prices[-1])
            except Exception:
                price_last = None

        if INDICATORS is not None and prices:
            try:
                ema_fast_series = INDICATORS.ema(prices, period=20)
                ema_slow_series = INDICATORS.ema(prices, period=50)
                if ema_fast_series:
                    ema_fast_last = float(ema_fast_series[-1])
                if ema_slow_series:
                    ema_slow_last = float(ema_slow_series[-1])
            except Exception as e:  # noqa: BLE001
                self._log(f"[DIAG] EMA error: {e!r}")

        # --- reset signal / recommendation labels ---
        try:
            self.label_signal.configure(text="Signal: n/a")
        except Exception:
            pass
        try:
            self.label_reco.configure(text="Recommendation: n/a")
        except Exception:
            pass

        if SIGNALS is None or rsi_last is None:
            return

        # --- base RSI+MACD signal ---
        try:
            sym = (self.var_symbol.get() or "").strip()
        except Exception:
            sym = ""
        sig = SIGNALS.simple_rsi_macd_signal(
            rsi_last,
            macd_last,
            macd_signal_last,
            symbol=sym,
            ema_fast_last=ema_fast_last,
            ema_slow_last=ema_slow_last,
            price_last=price_last,
        )
        if sig is None:
            return

        d = sig.as_dict()
        strength = float(d.get("strength", 0.0) or 0.0)

        # --- signal label text ---
        label_text = f"Signal: {d.get('side', 'n/a')}"
        if strength > 0.0:
            label_text += f" [{strength:.2f}]"
        reason = d.get("reason") or ""
        if reason:
            label_text += f" ({reason})"
        try:
            self.label_signal.configure(text=label_text)
        except Exception:
            pass

        # --- LastSig mini-panel (signal-level summary) ---
        try:
            side = str(d.get("side", "n/a")).upper()
            arrow = "•"
            if side == "BUY":
                arrow = "↑"
            elif side == "SELL":
                arrow = "↓"
            last_sig_text = f"LastSig: {side} {arrow}"
            if strength > 0.0:
                last_sig_text += f"  strength={strength:.2f}"
            reason = d.get("reason") or ""
            if reason:
                last_sig_text += f"  {reason}"
            if getattr(self, "label_last_sig", None) is not None:
                self.label_last_sig.configure(text=last_sig_text)
        except Exception:
            pass

        # --- advisor recommendation (сначала посчитаем reco!) ---
        reco = None
        if ADVISOR is not None:
            try:
                reco = ADVISOR.compute_recommendation(
                    d.get("side", "HOLD"),
                    d.get("rsi"),
                    d.get("macd"),
                    d.get("macd_signal"),
                    prices,
                )
                r_side = str(reco.get("side", "HOLD"))
                r_strength = float(reco.get("strength", 0.0))
                r_reason = reco.get("reason", "")
                arrow = "•"
                if r_side == "BUY":
                    arrow = "↑"
                elif r_side == "SELL":
                    arrow = "↓"
                # компактный текст рекомендации для шапки
                text = f"Rec: {r_side} {arrow} {r_strength:.2f}"
                if r_reason:
                    short_reason = str(r_reason)
                    if len(short_reason) > 40:
                        short_reason = short_reason[:37] + "..."
                    text += f" | {short_reason}"
                try:
                    self.label_reco.configure(text=text)
                except Exception:
                    pass

                    
                # NEW: передаём сигнал + рекомендацию + тренд в ядро (UIAPI)
                try:
                    api = self._ensure_uiapi()
                    if api is not None and hasattr(api, "update_advisor_snapshot"):
                        # d — это dict со side/rsi/macd/macd_signal, дополним symbol
                        meta = dict(d)
                        try:
                            meta["symbol"] = (self.var_symbol.get() or "").upper()
                        except Exception:
                            pass
                        api.update_advisor_snapshot(sig, reco, meta)
                except Exception:
                    # любые проблемы с ядром не должны ломать UI
                    pass
                    
            except Exception:
                reco = None

        # --- log + append to signals.jsonl only when side changes ---
        if sig.side != self._last_signal_side:
            self._last_signal_side = sig.side
            self._log(
                "[SIGNAL] side={side} rsi={rsi:.1f} macd={macd:+.4f} "
                "macd_sig={macd_signal:+.4f} reason={reason}".format(**d)
            )
            try:
                if prices:
                    last_idx = len(prices) - 1
                else:
                    last_idx = None

                rec = {
                    "ts": int(time.time()),
                    "symbol": (self.var_symbol.get() or "").upper(),
                    "index": last_idx,
                    "side": d.get("side"),
                    "rsi": d.get("rsi"),
                    "macd": d.get("macd"),
                    "macd_signal": d.get("macd_signal"),
                    "reason": d.get("reason"),
                    "signal_strength": float(d.get("strength", 0.0) or 0.0),
                }

                # если есть рекомендация — добавляем поля advisor’а
                if isinstance(reco, dict):
                    rec["recommendation_side"] = str(reco.get("side", "HOLD"))
                    rec["recommendation_strength"] = float(
                        reco.get("strength", 0.0) or 0.0
                    )
                    rec["recommendation_trend"] = str(reco.get("trend", "FLAT"))
                    rec["recommendation_score"] = float(
                        reco.get(
                            "score",
                            rec.get("recommendation_strength", 0.0),
                        )
                        or 0.0
                    )
                # --- NEW 1.2.1: ReplaceLogic decision ---
                try:
                    from core.replace_logic import decide_from_signal_and_reco

                    decision = decide_from_signal_and_reco(d, reco)

                    rec["action"] = decision.action
                    rec["decision_side"] = decision.side
                    rec["decision_confidence"] = float(
                        getattr(decision, "confidence", 0.0) or 0.0
                )
                    rec["decision_reason"] = str(getattr(decision, "reason", ""))

                except Exception:
                    # Любые ошибки ReplaceLogic не должны ломать UI
                    pass

                # NEW: добавляем сигнал в буфер UIAPI (recent_signals)
                try:
                    api2 = self._ensure_uiapi()
                    if api2 is not None and hasattr(api2, "append_recent_signal"):
                        api2.append_recent_signal(rec)
                except Exception:
                    pass

                SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
                with SIGNALS_FILE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception:
                pass

        # --- auto-SIM: shadow execution from signal + recommendation ---
        if self._autosim is not None and prices and reco is not None:
            try:
                symbol = (self.var_symbol.get() or "").upper()

                # reset SIM if user changed symbol
                if self._sim_symbol is not None and symbol != self._sim_symbol:
                    try:
                        self._on_reset_sim()
                    except Exception:
                        pass
                self._sim_symbol = symbol

                last_price = float(prices[-1])
                
                # NEW: пробрасываем последний тик в UIAPI/StateEngine
                try:
                    api = self._ensure_uiapi()
                    if api is not None and hasattr(api, "on_price"):
                        api.on_price(symbol, last_price)
                except Exception:
                    # любые проблемы с ядром не должны ломать AUTOSIM
                    pass

                snapshot = self._autosim.process(
                    symbol=symbol,
                    last_price=last_price,
                    simple_signal=sig,
                    recommendation=reco,
                )
                last_snapshot = snapshot
                
                # === LOG AUTOSIM TRADES INTO trades.jsonl ===
                try:
                    trades = snapshot.get("trades") or []
                    if trades:
                        JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
                        with JOURNAL_FILE.open("a", encoding="utf-8") as f:
                            for tr in trades:
                                rec = {
                                    "type": "ORDER",
                                    "mode": "SIM",
                                    "symbol": tr.get("symbol"),
                                    "side": tr.get("side"),
                                    "qty": tr.get("qty"),
                                    "price": tr.get("price"),
                                    "status": tr.get("status", "FILLED"),
                                    "ts": tr.get("ts", int(time.time())),
                                    "source": "AUTOSIM",
                                }
                                # дополнительные метрики, если autosim их передал
                                if "pnl_cash" in tr:
                                    rec["pnl_cash"] = tr.get("pnl_cash")
                                if "pnl_pct" in tr:
                                    rec["pnl_pct"] = tr.get("pnl_pct")
                                if "reason" in tr:
                                    rec["reason"] = tr.get("reason")
                                if "hold_seconds" in tr:
                                    rec["hold_seconds"] = tr.get("hold_seconds")
                                # NEW: добавляем сделку в буфер UIAPI (recent_trades)
                                try:
                                    api2 = self._ensure_uiapi()
                                    if api2 is not None and hasattr(api2, "append_recent_trade"):
                                        ts_val = rec.get("ts")
                                        if isinstance(ts_val, (int, float)):
                                            try:
                                                time_str = time.strftime(
                                                    "%Y-%m-%d %H:%M:%S",
                                                    time.localtime(ts_val),
                                                )
                                            except Exception:
                                                time_str = str(ts_val)
                                        else:
                                            time_str = str(ts_val or "")

                                        row = {
                                            "time": time_str,
                                            "symbol": rec.get("symbol"),
                                            "tier": "-",  # tier пока не считаем
                                            "action": rec.get("side") or rec.get("status") or "",
                                            "tp": None,
                                            "sl": None,
                                            "pnl_pct": rec.get("pnl_pct"),
                                            "pnl_abs": rec.get("pnl_cash"),
                                            "qty": rec.get("qty"),
                                            "entry": None,
                                            "exit": rec.get("price"),
                                        }
                                        api2.append_recent_trade(row)
                                except Exception:
                                    pass
                                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                except Exception as e:
                    self._log(f"[AUTOSIM] write trades error: {e}")

                # persist snapshot for debug / future UI
                try:
                    sim_state_path = RUNTIME_DIR / "sim_state.json"
                    sim_state_path.write_text(
                        json.dumps(snapshot, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass

                # update Active position panel + equity bar
                try:
                    self._update_active_from_sim(snapshot)
                    self._update_equity_bar(snapshot)
                except Exception:
                    pass

                # debounced SIM log: only when changed
                portfolio = snapshot.get("portfolio") or {}
                eq = portfolio.get("equity")
                open_cnt = portfolio.get("open_positions_count")
                if eq is not None and open_cnt is not None:
                    should_log = False
                    try:
                        eq_f = float(eq)
                        open_i = int(open_cnt)
                        prev = self._sim_log_state
                        if prev is None:
                            should_log = True
                        else:
                            prev_eq, prev_open = prev
                            if int(prev_open) != open_i:
                                should_log = True
                            elif abs(eq_f - float(prev_eq)) >= 0.1:
                                should_log = True
                    except Exception:
                        should_log = True

                    if should_log:
                        self._log(f"[SIM] equity={float(eq):.2f} open_positions={open_cnt}")
                        self._sim_log_state = (float(eq), int(open_cnt))
                        # логируем equity в history.csv для будущих графиков
                        try:
                            self._append_equity_history(snapshot)
                        except Exception:
                            pass
                            
                        # обновляем статус-бар (режим + lag) после обработки сигнала и AUTOSIM
                        try:
                            self._update_status_bar(last_snapshot)
                        except Exception:
                            pass                          
                            
            except Exception as e:
                self._log(f"[SIM] error: {e}")


    def _open_rsi_chart(self) -> None:
        if ChartPanel is None:
            messagebox.showwarning("RSI Chart", "ChartPanel / matplotlib недоступны.")
            return

        win = tk.Toplevel(self)
        win.title("MontrixBot — RSI Chart (demo 1.1)")
        win.geometry("800x500")

        panel = ChartPanel(win)
        panel.pack(fill="both", expand=True)

        try:
            times, prices = self._load_chart_prices(max_points=300)
            if times and prices:
                panel.plot_series(times, prices)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("RSI Chart", f"Не удалось построить график: {e}")

    def _open_rsi_live_chart(self) -> None:
        if ChartPanel is None:
            messagebox.showwarning("LIVE Chart", "ChartPanel / matplotlib недоступны.")
            return

        win = tk.Toplevel(self)
        win.title("MontrixBot — LIVE Chart (ticks=300)")
        win.geometry("800x500")

        panel = ChartPanel(win)
        panel.pack(fill="both", expand=True)

        def refresh() -> None:
            if not win.winfo_exists():
                return
            try:
                times, prices = self._load_chart_prices(max_points=300)
                if times and prices:
                    panel.plot_series(times, prices)
            except Exception:
                pass
            win.after(500, refresh)

        refresh()
    
    def _cmd_open_signals(self) -> None:
        """Открыть окно с историей сигналов из runtime/signals.jsonl.

        Показывает последние ~500 записей. В этой версии добавлен
        лёгкий heatmap-режим по RSI, чтобы глазами ловить экстремумы.
        """

        if not SIGNALS_FILE.exists():
            messagebox.showinfo(
                "Signals",
                f"No signals file found at:\n{SIGNALS_FILE}",
            )
            return

        try:
            with SIGNALS_FILE.open("r", encoding="utf-8") as f:
                # берём только последний хвост, чтобы окно не разрасталось
                lines = f.readlines()[-500:]
        except Exception as exc:
            messagebox.showerror(
                "Signals", f"Failed to read signals file:\n{exc}"
            )
            return

        records: list[dict] = []
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            if isinstance(obj, dict):
                records.append(obj)

        if not records:
            messagebox.showinfo("Signals", "No signals to display yet.")
            return

        win = tk.Toplevel(self)
        win.title("MontrixBot — Signals history")
        win.geometry("900x400")
        try:
            win.configure(bg="#0f1216")  # тёмный фон окна
        except Exception:
            pass

        cols = ("ts", "symbol", "side", "rsi", "macd", "macd_sig", "reason")
        headers = {
            "ts": "Time",
            "symbol": "Symbol",
            "side": "Side",
            "rsi": "RSI",
            "macd": "MACD",
            "macd_sig": "MACD sig",
            "reason": "Reason",
        }
        widths = {
            "ts": 150,
            "symbol": 80,
            "side": 70,
            "rsi": 60,
            "macd": 80,
            "macd_sig": 80,
            "reason": 380,
        }

        # локальный стиль под тёмную тему
        style = ttk.Style(win)
        try:
            style.configure(
                "Signals.Treeview",
                background="#171B21",
                fieldbackground="#171B21",
                foreground="#E6EAF2",
                rowheight=20,
                font=("Segoe UI", 9),
            )
            style.configure(
                "Signals.Treeview.Heading",
                background="#111827",
                foreground="#E6EAF2",
                font=("Segoe UI", 9, "bold"),
            )
        except Exception:
            # если что-то не поддерживается — просто остаёмся на дефолтном стиле
            pass

        # верхняя панель: заголовок + чекбокс heatmap
        top = ttk.Frame(win)
        top.pack(side="top", fill="x")

        ttk.Label(
            top,
            text=f"Signals (last {len(records)} records)",
        ).pack(side="left", padx=(10, 0), pady=4)

        heatmap_var = tk.IntVar(value=0)
        ttk.Checkbutton(
            top,
            text="Heatmap RSI",
            variable=heatmap_var,
        ).pack(side="right", padx=(0, 12), pady=4)

        # основное дерево
        tree = ttk.Treeview(
            win,
            columns=cols,
            show="headings",
            style="Signals.Treeview",
        )
        tree.pack(fill="both", expand=True, side="left")

        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        numeric_right = {"rsi", "macd", "macd_sig"}
        center_cols = {"symbol", "side"}

        for cid in cols:
            heading_text = headers.get(cid, cid.upper())
            tree.heading(cid, text=heading_text)

            if cid in numeric_right:
                anchor = "e"       # числа вправо
            elif cid in center_cols:
                anchor = "center"  # символ/сторона по центру
            else:
                anchor = "w"       # время и reason влево

            tree.column(
                cid,
                width=widths.get(cid, 80),
                anchor=anchor,
                stretch=True,
            )

        def _fmt_float(val: object, pattern: str = "{:.4f}") -> str:
            try:
                return pattern.format(float(val))
            except Exception:
                return ""

        def _to_float(val: object) -> float | None:
            try:
                return float(val)
            except Exception:
                return None

        # палитры, согласованные с журналом сделок
        colors_pos = [
            "#052e16",
            "#064e3b",
            "#047857",
            "#059669",
            "#10b981",
            "#34d399",
            "#6ee7b7",
        ]
        colors_neg = [
            "#3b0d0c",
            "#5c1a15",
            "#7f2318",
            "#a52a1f",
            "#cc3d2b",
            "#e2583b",
            "#ff7043",
        ]
        heatmap_tags: dict[str, str] = {}

        def _ensure_heatmap_tag_from_rsi(rsi_val: float | None) -> str | None:
            """Подбирает/создаёт тег heatmap по RSI.

            • RSI < 30  — зона перепроданности (зелёная шкала)
            • RSI > 70  — зона перекупленности (красная шкала)
            • иначе     — без подсветки
            """
            if not heatmap_var.get():
                return None
            if rsi_val is None:
                return None

            if rsi_val < 30.0:
                palette = colors_pos
                delta = 30.0 - rsi_val
                key_prefix = "rsi_low"
            elif rsi_val > 70.0:
                palette = colors_neg
                delta = rsi_val - 70.0
                key_prefix = "rsi_high"
            else:
                return None

            bounds = [1, 2, 4, 7, 10, 15, 25]
            idx = 0
            while idx < len(bounds) and delta > bounds[idx]:
                idx += 1
            if idx >= len(bounds):
                idx = len(bounds) - 1

            key = f"{key_prefix}_{idx}"
            if key in heatmap_tags:
                return key

            color = palette[idx]
            try:
                tree.tag_configure(key, background=color)
                heatmap_tags[key] = color
                return key
            except Exception:
                return None

        def _apply_heatmap_to_all() -> None:
            """Пересчитать heatmap-теги для всех строк."""
            for item_id in tree.get_children(""):
                item = tree.item(item_id)
                values = item.get("values") or []
                tags: list[str] = []
                rsi_str = values[3] if len(values) > 3 else ""
                rsi_val = _to_float(rsi_str)
                tag = _ensure_heatmap_tag_from_rsi(rsi_val)
                if tag:
                    tags.append(tag)
                tree.item(item_id, tags=tuple(tags))

        # привязка чекбокса к пересчёту heatmap
        def _on_heatmap_toggle() -> None:
            _apply_heatmap_to_all()

        heatmap_var.trace_add("write", lambda *_: _on_heatmap_toggle())

        # свежие записи показываем сверху
        for obj in reversed(records):
            ts = obj.get("ts")
            if isinstance(ts, (int, float)):
                ts_str = time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(ts),
                )
            else:
                ts_str = str(ts or "")

            rsi_val = _to_float(obj.get("rsi"))
            rsi_str = _fmt_float(rsi_val, "{:.1f}") if rsi_val is not None else ""
            macd_str = _fmt_float(obj.get("macd"))
            macd_sig_str = _fmt_float(obj.get("macd_signal"))

            tags: list[str] = []
            tag = _ensure_heatmap_tag_from_rsi(rsi_val)
            if tag:
                tags.append(tag)

            tree.insert(
                "",
                "end",
                values=(
                    ts_str,
                    obj.get("symbol", ""),
                    obj.get("side", ""),
                    rsi_str,
                    macd_str,
                    macd_sig_str,
                    obj.get("reason", ""),
                ),
                tags=tuple(tags),
            )

    def _cmd_open_trades(self) -> None:
        """Открыть окно с историей сделок.

        При наличии DealsJournal используем новый виджет с router-обновлением
        из снапшота UIAPI/StateEngine. Если импорт не удался — падаем обратно
        на легаси Treeview-представление из trades.jsonl.
        """
        # --- Новый режим: DealsJournal + snapshot router ---
        if DealsJournal is not None:
            try:
                win = tk.Toplevel(self)
                win.title("Deals journal (SIM/REAL)")
                try:
                    win.configure(bg="#1c1f24")
                except Exception:
                    pass
                win.geometry("980x540")

                journal = DealsJournal(win)
                journal.frame.pack(fill="both", expand=True)

                # Регистрация для _refresh_from_core_snapshot
                try:
                    self.register_deals_journal(journal)
                except Exception:
                    pass

                # При закрытии окна убираем ссылку из router-а
                def _on_close() -> None:
                    try:
                        if getattr(self, "_deals_journal_widget", None) is journal:
                            self._deals_journal_widget = None
                    except Exception:
                        pass
                    try:
                        win.destroy()
                    except Exception:
                        pass

                win.protocol("WM_DELETE_WINDOW", _on_close)

                # 1) Первичная загрузка из снапшота (trades_recent)
                try:
                    api = self._ensure_uiapi()
                    if api is not None and hasattr(api, "get_state_snapshot"):
                        snap = api.get_state_snapshot()
                        if isinstance(snap, dict) and hasattr(journal, "update_from_snapshot"):
                            journal.update_from_snapshot(snap)
                except Exception:
                    # не критично — просто не будет первичной загрузки
                    pass

                # 2) Fallback: подхватываем хвост из trades.jsonl, если он есть
                try:
                    if JOURNAL_FILE.exists():
                        with JOURNAL_FILE.open("r", encoding="utf-8") as f:
                            lines = f.readlines()[-500:]  # последние 500 записей
                        rows = []
                        for ln in lines:
                            try:
                                rec = json.loads(ln)
                            except Exception:
                                continue

                            ts_val = rec.get("ts")
                            if isinstance(ts_val, (int, float)):
                                try:
                                    time_str = time.strftime(
                                        "%Y-%m-%d %H:%M:%S",
                                        time.localtime(ts_val),
                                    )
                                except Exception:
                                    time_str = str(ts_val)
                            else:
                                time_str = str(ts_val or "")

                            row = {
                                "time": time_str,
                                "symbol": rec.get("symbol"),
                                "tier": "-",  # tier пока не считаем
                                "action": rec.get("side") or rec.get("status") or "",
                                "tp": None,
                                "sl": None,
                                "pnl_pct": rec.get("pnl_pct"),
                                "pnl_abs": rec.get("pnl_cash"),
                                "qty": rec.get("qty"),
                                "entry": None,
                                "exit": rec.get("price"),
                            }
                            rows.append(row)

                        if rows and hasattr(journal, "update"):
                            journal.update(rows)
                except Exception:
                    # журнал всё равно останется живым за счёт router-а
                    pass

                return
            except Exception as exc:  # noqa: BLE001
                try:
                    self._log(f"[UI] DealsJournal failed, fallback to legacy viewer: {exc!r}")
                except Exception:
                    pass
                # и ниже пойдём по старому пути

        # --- Легаси-режим: простой Treeview на основе trades.jsonl ---
        if not JOURNAL_FILE.exists():
            messagebox.showinfo(
                "Trades",
                f"No trades file found at:\n{JOURNAL_FILE}",
            )
            return

        try:
            with JOURNAL_FILE.open("r", encoding="utf-8") as f:
                lines = f.readlines()[-500:]  # последние 500 записей
        except Exception as exc:
            messagebox.showerror(
                "Trades", f"Failed to read trades file:\n{exc}"
            )
            return

        try:
            import json as _json
        except Exception:
            _json = json

        # Берём последний успешный парс
        rows = []
        for ln in lines:
            try:
                obj = _json.loads(ln)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                continue

        if not rows:
            messagebox.showinfo("Trades", "No valid JSON entries found in trades file.")
            return

        # Строим окно с Treeview (как раньше)
        win = tk.Toplevel(self)
        win.title("Trades journal (raw)")
        win.geometry("960x520")

        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            frm,
            columns=("ts", "mode", "symbol", "side", "qty", "price", "status", "source"),
            show="headings",
        )
        tree.pack(fill="both", expand=True, side="left")

        vsb = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
        vsb.pack(side="right", fill="y")
        tree.configure(yscrollcommand=vsb.set)

        headers = {
            "ts": "Time",
            "mode": "Mode",
            "symbol": "Symbol",
            "side": "Side",
            "qty": "Qty",
            "price": "Price",
            "status": "Status",
            "source": "Source / Info",
        }
        widths = {
            "ts": 140,
            "mode": 60,
            "symbol": 80,
            "side": 60,
            "qty": 80,
            "price": 80,
            "status": 80,
            "source": 260,
        }
        for cid in headers:
            tree.heading(cid, text=headers[cid])
            tree.column(cid, width=widths.get(cid, 80), anchor="w")

        def _fmt_float(val, pattern: str = "{:.4f}") -> str:
            try:
                return pattern.format(float(val))
            except Exception:
                return ""

        def _extract_ts(obj: dict) -> str:
            ts = obj.get("ts")
            if ts is None:
                ts = obj.get("transactTime")
                if isinstance(ts, (int, float)):
                    try:
                        return time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(ts / 1000.0),
                        )
                    except Exception:
                        return str(ts)
                return str(ts or "")
            if isinstance(ts, (int, float)):
                try:
                    return time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(ts),
                    )
                except Exception:
                    return str(ts)
            return str(ts)

        for obj in rows:
            mode = obj.get("mode") or "?"
            symbol = obj.get("symbol") or "?"
            side = obj.get("side") or "?"
            qty = _fmt_float(obj.get("qty"))
            price = _fmt_float(obj.get("price"))
            status = obj.get("status") or ""
            base_source = obj.get("source") or obj.get("info") or ""

            pnl_pct = obj.get("pnl_pct")
            pnl_cash = obj.get("pnl_cash")
            if pnl_pct is not None or pnl_cash is not None:
                parts = [base_source] if base_source else []
                try:
                    if pnl_pct is not None:
                        parts.append(f"PnL%: {float(pnl_pct):+.2f}%")
                except Exception:
                    pass
                try:
                    if pnl_cash is not None:
                        parts.append(f"PnL: {float(pnl_cash):+.2f}")
                except Exception:
                    pass
                source = " | ".join(parts) if parts else base_source
            else:
                source = base_source

            tree.insert(
                "",
                "end",
                values=(
                    _extract_ts(obj),
                    mode,
                    symbol,
                    side,
                    qty,
                    price,
                    status,
                    source,
                ),
            )

    # ----------------------------------------------------- journal router --
    def register_deals_journal(self, journal) -> None:
        """Регистрирует DealsJournal widget для router-обновления из снапшота
        и настраивает callback фокуса символа из журнала.
        """
        self._deals_journal_widget = journal
        try:
            if hasattr(journal, "set_focus_callback"):
                journal.set_focus_callback(self._on_journal_focus_symbol)
        except Exception:
            # не даём падать из-за проблем в виджете журнала
            pass

    def _on_journal_focus_symbol(self, symbol: str) -> None:
        """Колбэк из DealsJournal при клике по строке.

        Обновляет выбранный символ в комбобоксе и пишет строку в лог.
        Добавлен лёгкий дебаунс, чтобы не спамить лог при множественных кликах.
        """
        try:
            sym = (symbol or "").strip().upper()
            if not sym:
                return

            now = time.time()
            last_sym = getattr(self, "_last_journal_focus_symbol", None)
            last_ts = getattr(self, "_last_journal_focus_ts", 0.0)

            # если тот же символ приходит чаще, чем раз в 0.3 секунды — игнорируем
            if sym == last_sym and (now - last_ts) < 0.3:
                return

            self._last_journal_focus_symbol = sym
            self._last_journal_focus_ts = now

            # обновляем var_symbol и комбобокс
            try:
                self.var_symbol.set(sym)
            except Exception:
                pass
            combo = getattr(self, "combo", None)
            if combo is not None:
                try:
                    combo.set(sym)
                except Exception:
                    pass

            # диагностическая запись в лог
            try:
                self._log(f"[UI] focus symbol from journal: {sym}")
            except Exception:
                pass
        except Exception:
            # защита от любых сбоев в UI-колбэке
            return

    # -------------------------------------------------------------- actions --
    
    def _ensure_uiapi(self):
        """Lazily construct UIAPI + core state/executor for SIM actions.
        REAL-пути через scripts остаются нетронутыми.
        """
        if getattr(self, "_uiapi", None) is not None:
            return self._uiapi
        try:
            if UIAPI is None:
                self._log("[DIAG] ui_api not available for SIM bridge")
                self._uiapi = None
                return None
        except Exception:
            self._uiapi = None
            return None

        try:
            from core.state_engine import StateEngine
            from core.executor import OrderExecutor
            from core.tpsl import TPSLManager, TPSSLConfig
        except Exception as e:  # noqa: BLE001
            try:
                self._log(f"[DIAG] ui bridge import error: {e!r}")
            except Exception:
                pass
            self._uiapi = None
            return None

        try:
            state = StateEngine(enable_tpsl=True)
            # В этом UI-степе SIM-ордеры пишутся только из AUTOSIM,
            # поэтому для UIAPI используем особый режим без журнала.
            executor = OrderExecutor(mode="SIM", state=state)
            tpsl_cfg = TPSSLConfig()
            tpsl = TPSLManager(executor, tpsl_cfg)
            state.attach_tpsl(tpsl)
            self._uiapi = UIAPI(state, executor, tpsl=tpsl)
            self._log("[DIAG] ui bridge: UIAPI + StateEngine ready")
            
            # NEW: передаём текущий режим UI в UIAPI
            
            try:
                self._uiapi.set_mode(self._mode)
            except Exception:
                pass                
                
            return self._uiapi
        except Exception as e:  # noqa: BLE001
            try:
                self._log(f"[DIAG] ui bridge init failed: {e!r}")
            except Exception:
                pass
            self._uiapi = None
            return None

    def on_preview(self) -> None:
        """Preview через UIAPI (SIM), REAL не трогаем."""
        api = self._ensure_uiapi()
        if api is None:
            messagebox.showwarning("Preview", "UI bridge (UIAPI) недоступен")
            return

        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]
        qty_str = self.var_qty.get().strip() or "0"
        try:
            qty = float(qty_str)
        except Exception:
            messagebox.showwarning("Preview", "Qty must be a number")
            return

        # 1) пробуем взять last price из ticks_stream.jsonl через _load_chart_prices
        last_price: Optional[float] = None
        try:
            _times, prices = self._load_chart_prices(max_points=300)
            if prices:
                last_price = float(prices[-1])
        except Exception:
            last_price = None

        # 2) если по каким-то причинам не удалось — пробуем через UIAPI.get_last_price
        if last_price is None:
            try:
                last_price = api.get_last_price(sym)
            except Exception:
                last_price = None

        pv = api.preview(sym, "BUY", qty, price=last_price)
        if not pv.ok:
            messagebox.showinfo("Preview", f"Preview FAILED: {pv.reason}\n{pv.info}")
            return

        # аккуратно формируем отображаемую цену: если тиков ещё не было — показываем n/a
        raw_price = getattr(pv, "rounded_price", None)
        if raw_price is None:
            raw_price = last_price

        no_price = False
        price_disp: str
        try:
            price_val = float(raw_price) if raw_price is not None else 0.0
        except Exception:
            price_val = 0.0

        if price_val <= 0:
            no_price = True
            price_disp = "n/a"
        else:
            price_disp = f"{price_val}"

        self._log(
            f"[PREVIEW] symbol={sym} qty={qty} price={price_disp} "
            f"qty_rounded={pv.rounded_qty} reason={pv.reason}"
        )

        if no_price:
            msg = (
                "Preview OK\n"
                "Price: n/a (no tick yet)\n"
                f"Qty≈{pv.rounded_qty}"
            )
        else:
            msg = (
                "Preview OK\n"
                f"Price≈{price_disp}\n"
                f"Qty≈{pv.rounded_qty}"
            )

        messagebox.showinfo("Preview", msg)  # ui bridge
    
    def on_buy_sim(self) -> None:
        """Buy через UIAPI в SIM."""
        api = self._ensure_uiapi()
        if api is None:
            messagebox.showwarning("Buy (SIM)", "UI bridge (UIAPI) недоступен")
            return

        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]
        qty_str = self.var_qty.get().strip() or "0"

        try:
            qty = float(qty_str)
        except Exception:
            messagebox.showwarning("Buy (SIM)", "Qty must be a number")
            return

        if qty <= 0:
            messagebox.showwarning("Buy (SIM)", "Quantity must be > 0")
            return

        try:
            # явный лог о том, что это ручной BUY в SIM-режиме (через UIAPI + StateEngine)
            self._log(f"[UI] manual BUY SIM {sym} qty={qty} via UIAPI")
            res = api.buy_market(sym, qty)
            self._log(f"[UI] ui bridge BUY SIM {sym} qty={qty} -> {res}")
        except Exception as e:  # noqa: BLE001
            self._log(f"[ERROR] ui bridge BUY SIM failed: {e!r}")
            messagebox.showerror("Buy (SIM)", f"Buy failed: {e}")
    
    def _manual_close_sim_position(self, symbol: str, reason: str = "UI_CLOSE") -> None:
        """Закрывает все позиции по symbol в AUTOSIM, считает PnL и пишет SELL в trades.jsonl."""
        # получаем движок autosim
        try:
            sim = getattr(self, "_autosim", None)
        except Exception:
            sim = None
        if sim is None:
            return
            
        # берём engine, где реально лежат позиции AUTOSIM
        try:
            engine = getattr(sim, "engine", None)
        except Exception:
            engine = None
        if engine is None:
            return

        # нормализуем символ
        try:
            sym_u = (symbol or "").upper()
        except Exception:
            sym_u = symbol or ""

        # собираем все открытые позиции по этому символу из engine.active_positions
        positions = []
        try:
            for p in list(getattr(engine, "active_positions", []) or []):
                try:
                    if (p.get("symbol") or "").upper() == sym_u:
                        positions.append(p)
                except Exception:
                    continue
        except Exception:
            positions = []

        if not positions:
            return
            
        try:
            self._log(f"[AUTOSIM] manual_close: found {len(positions)} positions for {sym_u}")
        except Exception:
            pass

        # получаем последнюю цену из UIAPI/state
        last_price = None
        try:
            api = self._ensure_uiapi()
            if api is not None and hasattr(api, "get_last_price"):
                last_price = api.get_last_price(sym_u)
        except Exception:
            last_price = None

        lp = None
        # 1) пробуем цену из UIAPI
        if last_price is not None:
            try:
                lp = float(last_price)
            except Exception:
                lp = None

        # 2) если UIAPI ничего не знает — берём цену из позиции AUTOSIM
        if lp is None or lp <= 0.0:
            try:
                first_pos = positions[0]
                candidate = first_pos.get("current_price") or first_pos.get("entry_price")
                if candidate is not None:
                    lp = float(candidate)
            except Exception:
                lp = None

        # 3) если после всех попыток цена всё ещё невалидна — выходим
        if lp is None or lp <= 0.0:
            try:
                self._log(f"[AUTOSIM] manual_close: no valid last_price for {sym_u}, cancel")
            except Exception:
                pass
            return

        # закрываем все найденные позиции в AUTOSIM и сами считаем PnL для журнала
        records = []
        for pos in positions:
            # безопасно достаём основные поля позиции
            try:
                side_pos = str(pos.get("side", "")).upper()
                qty = float(pos.get("qty") or 0.0)
                entry = float(pos.get("entry_price") or 0.0)
            except Exception:
                continue

            if qty <= 0.0 or entry <= 0.0:
                # всё равно пробуем закрыть позицию в движке, но в журнал не пишем
                try:
                    sim._close_position(pos, lp, reason=reason)
                except Exception:
                    pass
                continue

            # вызываем закрытие в движке AUTOSIM, чтобы он обновил equity / active_positions
            try:
                sim._close_position(pos, lp, reason=reason)
            except Exception:
                # даже если он ничего не вернул — журнал мы всё равно запишем
                pass

            # вычисляем сторону закрытия и PnL
            if side_pos in ("SHORT", "SELL"):
                close_side = "BUY"
                pnl_cash = (entry - lp) * qty
            else:
                # считаем, что любая неявная позиция — LONG/BUY
                close_side = "SELL"
                pnl_cash = (lp - entry) * qty

            notional = entry * qty
            pnl_pct = (pnl_cash / notional * 100.0) if notional else 0.0

            # оценка времени удержания из hold_days (если есть)
            hold_seconds = None
            try:
                hold_days = float(pos.get("hold_days", 0.0) or 0.0)
                hold_seconds = int(hold_days * 86400)
            except Exception:
                pass

            rec = {
                "type": "ORDER",
                "mode": "SIM",
                "symbol": pos.get("symbol"),
                "side": close_side,
                "qty": qty,
                "price": lp,
                "status": "FILLED",
                "ts": int(time.time()),
                "source": reason,
                "pnl_cash": pnl_cash,
                "pnl_pct": pnl_pct,
            }
            if hold_seconds is not None:
                rec["hold_seconds"] = hold_seconds

            records.append(rec)

        if not records:
            return

        # пишем все SELL в журнал одной пачкой
        try:
            JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
            with JOURNAL_FILE.open("a", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            # не даём ошибкам журнала ломать UI
            return

        # после ручного закрытия руками обновляем snapshot для UI,
        # чтобы Active position (SIM) и мини-equity обновились сразу
        try:
            active_now = list(getattr(engine, "active_positions", []) or [])

            portfolio = {
                "equity": float(getattr(engine, "equity", 0.0) or 0.0),
                "cash": float(getattr(engine, "cash", 0.0) or 0.0),
                "open_positions_count": len(active_now),
            }

            snapshot = {
                "portfolio": portfolio,
                "active": active_now,
            }

            # обновляем панель активных позиций
            try:
                self._update_active_from_sim(snapshot)
            except Exception:
                pass

            # обновляем мини-equity бар
            try:
                self._update_equity_bar(snapshot)
            except Exception:
                pass

            # перезаписываем sim_state.json для консистентности
            try:
                sim_state_path = RUNTIME_DIR / "sim_state.json"
                sim_state_path.write_text(
                    json.dumps(snapshot, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass

        except Exception:
            # любые ошибки здесь не должны ломать UI
            pass

    def on_close_sim(self) -> None:
        """Close через UIAPI в SIM."""
        api = self._ensure_uiapi()
        if api is None:
            messagebox.showwarning("Close (SIM)", "UI bridge (UIAPI) недоступен")
            return

        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]
        if not messagebox.askyesno("Close (SIM)", f"Close position for {sym}?"):
            return

        try:
            # сначала закрываем AUTOSIM и фиксируем PnL
            try:
                self._manual_close_sim_position(sym, reason="UI_CLOSE")
            except Exception:
                pass

            # затем дергаем UIAPI, чтобы TPSL/EXECUTOR тоже знали о закрытии
            api.close_position(sym, reason="UI_close")
            self._log(f"[UI] ui bridge CLOSE SIM {sym}")
        except Exception as e:  # noqa: BLE001
            self._log(f"[ERROR] ui bridge CLOSE SIM failed: {e!r}")
            messagebox.showerror("Close (SIM)", f"Close failed: {e}")


    def _run_cli(self, args, tag: str | None = None) -> None:
        # по умолчанию тег зависит от состояния Dry-Run бейджа
        if tag is None:
            try:
                dry_on = bool(getattr(self, "dry_run_ui_on", True))
            except Exception:
                dry_on = True
            tag = "[DRY]" if dry_on else "[REAL]"

        self._log(f"{tag}[RUN] exe={sys.executable} script={' '.join(args)}")
        try:
            out = subprocess.check_output(
                [sys.executable] + args,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if out.strip():
                self._log(f"{tag} " + out.strip())
        except subprocess.CalledProcessError as e:
            self._log(f"{tag}[ERR] " + e.output.strip())
            messagebox.showerror(tag, f"{e.output.strip()}")
        except FileNotFoundError as e:
            self._log(f"{tag}[ERR] {repr(e)}")
            messagebox.showerror(tag, str(e))

    def on_buy_real(self) -> None:
        sym = self.var_symbol.get().strip()
        qty = self.var_qty.get().strip() or "0"
        try:
            float(qty)
        except Exception:
            messagebox.showwarning("Buy", "Qty must be a number")
            return
        self._run_cli(
            [str(SCRIPTS_DIR / "real_buy_market.py"), sym, str(qty), "--ask"]
        )

    def on_close_real(self) -> None:
        if self._safe_is_on():
            messagebox.showinfo(
                "Close", "SAFE is ON — disable SAFE to place REAL orders"
            )
            return

        sym = self.var_symbol.get().strip()
        default_qty = self.var_qty.get().strip() or "0"
        ans = simpledialog.askstring(
            "Close position",
            f"Enter quantity to close for {sym}\n(Empty = use {default_qty})",
            initialvalue=default_qty,
            parent=self,
        )
        if ans is None:
            return
        q = ans.strip() or default_qty
        try:
            qf = float(q)
        except Exception:
            messagebox.showwarning("Close", "Invalid quantity")
            return
        if qf <= 0:
            messagebox.showwarning("Close", "Quantity must be > 0")
            return
        if messagebox.askyesno("Confirm", f"Close {qf} {sym} at Market?"):
            self._run_cli(
                [str(SCRIPTS_DIR / "real_sell_market.py"), sym, str(qf), "--ask"]
            )

    def on_panic(self) -> None:
        """Panic через UIAPI в SIM (закрытие позиций)."""
        api = self._ensure_uiapi()
        if api is None:
            messagebox.showwarning("Panic", "UI bridge (UIAPI) недоступен")
            return
        sym = self.var_symbol.get().strip() or DEFAULT_SYMBOLS[0]
        if not messagebox.askyesno("Panic", f"Panic close for {sym}?"):
            return
        try:
            # сначала закрываем AUTOSIM и фиксируем PnL
            try:
                self._manual_close_sim_position(sym, reason="UI_PANIC")
            except Exception:
                pass

            # затем уже дергаем UIAPI.panic
            api.panic(sym)
            self._log(f"[UI] ui bridge PANIC {sym}")
        except Exception as e:  # noqa: BLE001
            self._log(f"[ERROR] ui bridge PANIC failed: {e!r}")
            messagebox.showerror("Panic", f"Panic failed: {e}")


def launch(*args, **kwargs) -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    launch()
