# capture_results.py
from __future__ import annotations

import ast
import io
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_JSON_PATH = os.path.join(PROJECT_DIR, "result.json")
TEST_MODULE_PATH = os.path.join(PROJECT_DIR, "test_module.py")

DEFAULT_HINT = "Check the expected return/output for this test and compare with your function result."

_CAPTURE_BUF: Optional[io.StringIO] = None
_ORIG_STDOUT = None
_ORIG_STDERR = None


class Tee(io.TextIOBase):
    def __init__(self, original, buf: io.StringIO):
        self._original = original
        self._buf = buf

    def write(self, s):
        try:
            self._buf.write(s)
        except Exception:
            pass
        try:
            return self._original.write(s)
        except Exception:
            return len(s)

    def flush(self):
        try:
            self._buf.flush()
        except Exception:
            pass
        try:
            self._original.flush()
        except Exception:
            pass


def _safe_write_json(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _extract_hints_from_test_module(py_path: str) -> Dict[str, str]:
    """
    Map: test_name -> hint message (from assertEqual third arg in test_module.py)
    """
    if not os.path.exists(py_path):
        return {}

    try:
        src = open(py_path, "r", encoding="utf-8").read()
        tree = ast.parse(src, filename=py_path)
    except Exception:
        return {}

    hints: Dict[str, str] = {}

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            if node.name.startswith("test_"):
                msg = None
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "assertEqual":
                        # assertEqual(actual, expected, msg) => msg is args[2]
                        if len(sub.args) >= 3 and isinstance(sub.args[2], ast.Constant) and isinstance(sub.args[2].value, str):
                            msg = sub.args[2].value
                            break
                        # sometimes msg is 4th arg in other patterns; keep fallback
                        if len(sub.args) >= 4 and isinstance(sub.args[3], ast.Constant) and isinstance(sub.args[3].value, str):
                            msg = sub.args[3].value
                            break
                hints[node.name] = msg or DEFAULT_HINT
            self.generic_visit(node)

    V().visit(tree)
    return hints


def start() -> None:
    """
    Call at the beginning of main.py to start capturing stdout/stderr.
    Also creates result.json immediately on first run.
    """
    global _CAPTURE_BUF, _ORIG_STDOUT, _ORIG_STDERR

    if _CAPTURE_BUF is not None:
        return  # already started

    _CAPTURE_BUF = io.StringIO()
    _ORIG_STDOUT = sys.stdout
    _ORIG_STDERR = sys.stderr
    sys.stdout = Tee(_ORIG_STDOUT, _CAPTURE_BUF)
    sys.stderr = Tee(_ORIG_STDERR, _CAPTURE_BUF)

    _safe_write_json(
        RESULT_JSON_PATH,
        {
            "ok": True,                 # 1st key
            "state": "running",         # 2nd key ✅
            "challenge": "failed",      # placeholder until done
            "tests": [],
            "passed": [],
            "failed": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stdout": "",
        },
    )


def _short_test_name(test_id: str) -> str:
    # "test_module.UnitTests.test_port_scanner_ip" -> "test_port_scanner_ip"
    return test_id.split(".")[-1] if test_id else test_id


def finish(test_program) -> None:
    """
    Call after unittest.main(..., exit=False) completes.
    Uses the unittest result object (not fragile regex parsing).
    Writes/updates result.json with challenge status + passed/failed + hints + stdout.
    """
    global _CAPTURE_BUF, _ORIG_STDOUT, _ORIG_STDERR

    hints = _extract_hints_from_test_module(TEST_MODULE_PATH)
    all_tests: List[str] = sorted(hints.keys())

    # Get unittest result
    result = getattr(test_program, "result", None)
    failures = getattr(result, "failures", []) if result else []
    errors = getattr(result, "errors", []) if result else []

    failed_names: Set[str] = set()
    for test_case, _trace in failures:
        failed_names.add(_short_test_name(test_case.id()))
    for test_case, _trace in errors:
        failed_names.add(_short_test_name(test_case.id()))

    failed_names_sorted = sorted(failed_names)
    passed_names = [t for t in all_tests if t not in failed_names]

    all_ok = bool(all_tests) and len(failed_names) == 0

    output = _CAPTURE_BUF.getvalue() if _CAPTURE_BUF else ""

    payload = {
        "ok": True,                     # 1st key
        "state": "done",                # 2nd key ✅
        "challenge": "passed" if all_ok else "failed",
        "tests": [
            {
                "name": n,
                "status": ("failed" if n in failed_names else "passed"),
                "hint": hints.get(n, DEFAULT_HINT),   # always present
            }
            for n in all_tests
        ],
        "passed": passed_names,
        "failed": [
            {"name": n, "status": "failed", "hint": hints.get(n, DEFAULT_HINT)}
            for n in failed_names_sorted
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stdout": output,
    }

    _safe_write_json(RESULT_JSON_PATH, payload)

    # restore streams
    try:
        sys.stdout = _ORIG_STDOUT
        sys.stderr = _ORIG_STDERR
    finally:
        _CAPTURE_BUF = None
        _ORIG_STDOUT = None
        _ORIG_STDERR = None
