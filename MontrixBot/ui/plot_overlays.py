def draw_tpsl_overlays(ax, entry=None, tp=None, sl=None):
    """Draw horizontal lines for entry/TP/SL on a Matplotlib Axes.
    Safe no-op if Matplotlib not available or ax is None.
    """
    try:
        import matplotlib.pyplot as plt  # noqa: F401
    except Exception:
        return
    if ax is None:
        return
    try:
        if entry is not None:
            ax.axhline(entry, linestyle="--", linewidth=1.0, alpha=0.6, label="ENTRY")
        if tp is not None:
            ax.axhline(tp, linestyle="-.", linewidth=1.0, alpha=0.8, label="TP")
        if sl is not None:
            ax.axhline(sl, linestyle=":", linewidth=1.0, alpha=0.8, label="SL")
        # keep legend minimal
        handles, labels = ax.get_legend_handles_labels()
        if labels:
            ax.legend(loc="best")
    except Exception:
        pass
