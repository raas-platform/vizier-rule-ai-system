"""Top-level alias package to map `app.*` imports → `backend.app.*`.

This shim allows existing scripts and tests to keep using::

    from app.services.rule_analyzer_v2 import RuleAnalyzerV2

while 실제 구현 코드는 `backend/app/` 하위에 유지됩니다.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

# --- Ensure backend directory is discoverable -----------------------------
_backend_dir = Path(__file__).resolve().parent / "backend"
if _backend_dir.exists() and str(_backend_dir) not in sys.path:
    # `backend`가 최상위 path로 인식되도록 sys.path에 삽입
    sys.path.insert(0, str(_backend_dir))

del Path, _backend_dir

# -------------------------------------------------------------------------
# 동적 모듈 alias 헬퍼
# -------------------------------------------------------------------------

def _alias(submodule: str) -> ModuleType:
    """`backend.app.<submodule>` 를 임포트하고 `app.<submodule>` 로 alias.

    Parameters
    ----------
    submodule: str
        하위 모듈 이름 (예: "services")
    """
    backend_name = f"backend.app.{submodule}"
    alias_name = f"app.{submodule}"

    module = importlib.import_module(backend_name)
    # sys.modules 에 별칭 등록 → 이후 import 시 캐싱
    sys.modules[alias_name] = module
    return module


# 필수 서브모듈 선로드 (ImportError 무시)
_forced_submodules = [
    "main",
    "services",
    "models",
    "utils",
    "api",
    "middleware",
    "database",
]

for _sub in _forced_submodules:
    try:
        _alias(_sub)
    except ModuleNotFoundError:
        # 일부 모듈은 존재하지 않을 수 있음 → 무시
        pass

del importlib, sys, ModuleType, _alias, _sub, _forced_submodules 