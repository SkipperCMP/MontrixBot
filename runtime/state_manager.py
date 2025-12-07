from __future__ import annotations

import json
import logging
import os
import threading
import tempfile
import time
from typing import Any, Dict, Callable, Optional

logger = logging.getLogger("state_manager")


class StateManager:
    """Потокобезопасный менеджер state.json с жёстким логированием ошибок.

    Задачи:
    - атомарно читать/писать JSON-файл состояния;
    - не падать при битом/отсутствующем файле;
    - никогда не делать "silent fail": любая проблема уходит в logger.
    """

    def __init__(self, path: str = "runtime/state.json") -> None:
        self._path = path
        self._lock = threading.Lock()
        directory = os.path.dirname(self._path) or "."
        os.makedirs(directory, exist_ok=True)

        if not os.path.exists(self._path):
            # создаём минимальный state при первом запуске
            initial = {"positions": {}, "meta": {"created_at": time.time()}}
            self._write_atomic(initial)

    # --------------------------------------------------------------------- #
    # ВНУТРЕННИЕ МЕТОДЫ ЧТЕНИЯ/ЗАПИСИ
    # --------------------------------------------------------------------- #

    def _read(self) -> Dict[str, Any]:
        """Безопасное чтение state.json.

        Гарантирует:
        - никогда не выбрасывает исключения наружу;
        - при любой проблеме возвращает минимальный валидный dict;
        - ошибки подробно логируются.
        """
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.warning("state file %s not found, recreating new one", self._path)
            data = {"positions": {}, "meta": {"recovered_at": time.time(), "reason": "missing"}}
            # пытаемся сохранить новый state, но не валимся, если не получилось
            try:
                self._write_atomic(data)
            except Exception:  # noqa: BLE001
                logger.exception("failed to recreate missing state file %s", self._path)
        except json.JSONDecodeError as e:
            logger.error("broken JSON in state file %s: %s", self._path, e)
            data = {
                "positions": {},
                "meta": {
                    "recovered_at": time.time(),
                    "reason": "json_decode_error",
                    "error": str(e),
                },
            }
            try:
                self._write_atomic(data)
            except Exception:  # noqa: BLE001
                logger.exception("failed to overwrite broken state file %s", self._path)
        except OSError as e:
            # проблемы с диском/правами: state не перезаписываем, но логируем
            logger.error("I/O error reading state file %s: %s", self._path, e)
            data = {
                "positions": {},
                "meta": {
                    "recovered_at": time.time(),
                    "reason": "io_error",
                    "error": str(e),
                },
            }
        except Exception as e:  # noqa: BLE001
            # на всякий случай — логируем ВСЁ, но не даём упасть выше
            logger.exception("unexpected error reading state file %s: %s", self._path, e)
            data = {
                "positions": {},
                "meta": {
                    "recovered_at": time.time(),
                    "reason": "unexpected_error",
                    "error": str(e),
                },
            }

        if not isinstance(data, dict):
            logger.error("state file %s returned non-dict data, resetting", self._path)
            data = {"positions": {}, "meta": {"recovered_at": time.time(), "reason": "non_dict"}}
        data.setdefault("meta", {})
        return data

    def _write_atomic(self, data: Dict[str, Any]) -> None:
        """Атомарная запись state.json.

        При ошибке пишет в лог и НЕ выбрасывает исключения наружу.
        """
        directory = os.path.dirname(self._path) or "."
        os.makedirs(directory, exist_ok=True)

        fd: Optional[int] = None
        tmp_path: Optional[str] = None
        try:
            fd, tmp_path = tempfile.mkstemp(prefix="state_", suffix=".json", dir=directory)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            fd = None  # дескриптор уже закрыт os.fdopen

            os.replace(tmp_path, self._path)
            tmp_path = None
        except OSError as e:
            logger.error("failed to write state file %s: %s", self._path, e)
        except Exception as e:  # noqa: BLE001
            logger.exception("unexpected error writing state file %s: %s", self._path, e)
        finally:
            # удаляем временный файл, если он остался
            if tmp_path is not None:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            # если вдруг остался открытый fd
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

    # --------------------------------------------------------------------- #
    # ПУБЛИЧНЫЙ API
    # --------------------------------------------------------------------- #

    def get(self, key: str, default: Any = None) -> Any:
        """Безопасно получить значение по ключу из state."""
        with self._lock:
            data = self._read()
            return data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Установить значение ключа и сохранить state."""
        with self._lock:
            data = self._read()
            data[key] = value
            meta = data.setdefault("meta", {})
            meta["updated_at"] = time.time()
            self._write_atomic(data)

    def update(self, fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Функциональное обновление state.

        fn должен принять dict и вернуть либо новый dict, либо None (в этом
        случае считаем, что он модифицировал dict in-place).
        """
        with self._lock:
            data = self._read()
            original = dict(data)

            try:
                updated = fn(data)
            except Exception as e:  # noqa: BLE001
                logger.exception("error in StateManager.update callback: %s", e)
                # при ошибке callback оставляем старый state, чтобы не корраптить файл
                data = original
            else:
                if updated is not None:
                    data = updated

            meta = data.setdefault("meta", {})
            meta["updated_at"] = time.time()
            self._write_atomic(data)
