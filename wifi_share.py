"""Importable shim for the legacy ``wifi-share.py`` launcher.

This keeps the original single-file script available while exposing a stable
module path for packaging tools such as ``uv``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT_PATH = Path(__file__).with_name("wifi-share.py")
_SPEC = importlib.util.spec_from_file_location("wifi_share_cli", _SCRIPT_PATH)

if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load CLI script from {_SCRIPT_PATH}")

_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

main = _MODULE.main
ProcessError = _MODULE.ProcessError
create_QR_object = _MODULE.create_QR_object
create_QR_string = _MODULE.create_QR_string
escape = _MODULE.escape
execute = _MODULE.execute
fix_ownership = _MODULE.fix_ownership
log = _MODULE.log


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nk bye")
        raise SystemExit(1)
