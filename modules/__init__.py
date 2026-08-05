"""Pre-register all submodules in sys.modules to work around a Python 3.14
import-machinery KeyError that occurs on Streamlit Community Cloud.

By loading each submodule via ``importlib.util.spec_from_file_location`` we
bypass the broken ``_find_and_load`` path and place the module directly in
``sys.modules``.  Subsequent ``from modules.X import Y`` statements then hit
the cache and never trigger the faulty finder.
"""

import importlib
import importlib.util
import os
import sys

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
_pkg_name = __name__  # "modules"

_SUBMODULES = [
    "settings",
    "storage",
    "ui",
    "llm_client",
    "knowledge_base",
    "chatbot",
    "agent",
    "alerts",
    "diagnostics_bridge",
    "data_sources",
    "network_monitor",
    "anomaly_detector",
    "forecasting",
    "remediation",
    "reports",
]

for _name in _SUBMODULES:
    _fqn = f"{_pkg_name}.{_name}"
    if _fqn in sys.modules:
        continue
    _path = os.path.join(_pkg_dir, f"{_name}.py")
    if not os.path.isfile(_path):
        continue
    try:
        _spec = importlib.util.spec_from_file_location(_fqn, _path)
        if _spec is None or _spec.loader is None:
            continue
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules[_fqn] = _mod
        _spec.loader.exec_module(_mod)
    except Exception:
        # If pre-loading fails, the normal import path will still be tried.
        pass
