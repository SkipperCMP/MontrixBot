import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # папка MontrixBot

# --- Общие настройки игнора для full-режима ---

IGNORE_DIRS = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "dev",
    "exports",
}

IGNORE_SUFFIXES = {
    ".pyc",
    ".tmp",
}

# Файлы, которые мы всегда хотим включать в минимальный манифест
ALWAYS_INCLUDE = {
    "VERSION",
    "settings.json",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# === FULL-МОД: старое поведение, полный manifest по всему проекту ===
def iter_files_full(root: Path):
    for path in root.rglob("*"):
        if path.is_dir():
            # Пропускаем целые директории
            if path.name in IGNORE_DIRS:
                continue
            # не ломаем обход — просто не входим в игнорируемые ветки
            rel = path.relative_to(root)
            if any(part in IGNORE_DIRS for part in rel.parts):
                continue
            continue

        rel = path.relative_to(root)

        # игнор по каталогам
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue

        # игнор по суффиксу
        if path.suffix in IGNORE_SUFFIXES:
            continue

        yield rel


def build_manifest_full():
    root = ROOT
    manifest_lines = []
    for rel in sorted(iter_files_full(root)):
        full = root / rel
        digest = sha256_file(full)
        manifest_lines.append(f"{digest}  {rel.as_posix()}")

    out_path = root / "manifest.txt"
    out_path.write_text("\n".join(manifest_lines), encoding="utf-8")
    print(f"[FULL] manifest.txt written to {out_path}")


# === MIN-МОД: хэшим только нужные файлы из audit_bundle.json ===

def load_changed_files_from_audit(root: Path) -> list[str]:
    """
    Читает audit_bundle.json и возвращает список файлов из секции files.changed.
    """
    audit_path = root / "audit_bundle.json"
    if not audit_path.exists():
        raise FileNotFoundError(
            f"audit_bundle.json not found at {audit_path}. "
            f"Сначала сгенерируй или обнови audit_bundle.json для текущего патча."
        )

    data = json.loads(audit_path.read_text(encoding="utf-8"))
    changed = data.get("files", {}).get("changed", [])
    if not isinstance(changed, list):
        raise ValueError("Invalid format in audit_bundle.json: files.changed must be a list")

    # нормализуем строки
    changed = [str(Path(p)) for p in changed]
    return changed


def build_manifest_min():
    root = ROOT

    # 1. Берём список изменённых файлов из audit_bundle.json
    changed_files = load_changed_files_from_audit(root)

    # 2. Добавляем файлы, которые всегда должны быть в манифесте
    all_paths = set(changed_files) | ALWAYS_INCLUDE

    manifest_lines = []

    for rel_str in sorted(all_paths):
        rel_path = Path(rel_str)
        full = root / rel_path
        if not full.exists():
            # Если файла нет — просто предупреждаем и пропускаем
            print(f"[MIN] WARNING: {rel_path} not found, skipping")
            continue
        digest = sha256_file(full)
        manifest_lines.append(f"{digest}  {rel_path.as_posix()}")

    out_path = root / "manifest_min.txt"
    out_path.write_text("\n".join(manifest_lines), encoding="utf-8")
    print(f"[MIN] manifest_min.txt written to {out_path}")
    print(f"[MIN] files hashed: {len(manifest_lines)}")


def main():
    parser = argparse.ArgumentParser(description="Generate manifest for MontrixBot")
    parser.add_argument(
        "--mode",
        choices=["full", "min"],
        default="min",
        help="full = по всему проекту (старый режим), min = только изменённые файлы из audit_bundle.json",
    )
    args = parser.parse_args()

    if args.mode == "full":
        build_manifest_full()
    else:
        build_manifest_min()


if __name__ == "__main__":
    main()
