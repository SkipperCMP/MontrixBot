"""
Лёгкая обёртка для авто-симулятора сигналов.

Оставлена для совместимости: старый код может импортировать

    from core.sim.autosim import AutoSimFromSignals, AutoSimConfig

Вся реальная логика находится в core.sim.auto_from_signals.
"""

from .auto_from_signals import AutoSimFromSignals, AutoSimConfig

__all__ = ("AutoSimFromSignals", "AutoSimConfig")
