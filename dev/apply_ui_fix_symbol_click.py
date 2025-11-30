# dev/apply_ui_fix_symbol_click.py
import os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "ui", "app.py")
BACKUP = TARGET + ".bak_symbol_click"

def main():
    if not os.path.exists(TARGET):
        print("ERROR: ui/app.py not found")
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()

    # If method already exists, exit gracefully
    if re.search(r"\n\s*def\s+_on_symbol_click\s*\(", src):
        print("OK: _on_symbol_click already present. Nothing to change.")
        return 0

    # Try to insert after class App definition or after __init__
    pattern_class = re.compile(r"(class\s+App\s*\([^\)]*\)\s*:\s*\n)", re.M)
    m = pattern_class.search(src)
    insert_at = None
    if m:
        insert_at = m.end()
    else:
        # fallback: after first def __init__ inside class App
        pattern_init = re.compile(r"(def\s+__init__\s*\([^\)]*\)\s*:\s*\n)", re.M)
        m2 = pattern_init.search(src)
        if m2:
            insert_at = m2.end()

    method = (
        "\n"
        "    def _on_symbol_click(self, symbol: str):\n"
        "        try:\n"
        "            print(f\"[UI] Symbol clicked: {symbol}\")\n"
        "        except Exception:\n"
        "            pass\n"
        "\n"
    )

    if insert_at is None:
        # As a last resort, append to end of file with class check comment
        new_src = src + "\n\n# --- Auto-added fallback for LiveTickerPanel callback ---\n" + method
    else:
        new_src = src[:insert_at] + method + src[insert_at:]

    # Backup and write
    shutil.copyfile(TARGET, BACKUP)
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(new_src)

    print("OK: _on_symbol_click inserted. Backup created:", os.path.basename(BACKUP))
    return 0

if __name__ == "__main__":
    sys.exit(main())
