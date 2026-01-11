# ui/layout/__init__.py
from typing import Protocol

class RefreshableView(Protocol):
    def refresh(self, *args, **kwargs) -> None:
        ...
