"""
profiler.py — Runs cProfile on a target script/module and identifies the
top N "hot" user-defined functions (bottlenecks) worth optimizing.

Scope note: we deliberately ignore builtin/stdlib/site-packages frames so
we only surface functions the USER wrote, since those are the only ones
we can safely rewrite in Cython.
"""

from __future__ import annotations

import cProfile
import importlib.util
import pstats
import io
import os
import sys
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class HotFunction:
    name: str
    filename: str
    line_number: int
    cumulative_time: float
    total_time: float
    n_calls: int
    func_obj: Optional[Callable] = field(default=None, repr=False)

    @property
    def qualified_id(self) -> str:
        return f"{os.path.basename(self.filename)}:{self.line_number}:{self.name}"


def _is_user_code(filename: str, project_root: str) -> bool:
    """Filter out stdlib / site-packages / built-in frames."""
    if filename in ("~", "<string>") or filename.startswith("<"):
        return False
    abs_file = os.path.abspath(filename)
    abs_root = os.path.abspath(project_root)
    if not abs_file.startswith(abs_root):
        return False
    if "site-packages" in abs_file or "dist-packages" in abs_file:
        return False
    if os.sep + "lib" + os.sep + "python" in abs_file:
        return False
    return True


def profile_script(script_path: str, top_n: int = 5) -> List[HotFunction]:
    """
    Runs the target script under cProfile in-process (so we can later grab
    live function objects out of its module namespace), and returns the
    top_n hottest user-defined functions sorted by cumulative time.
    """
    script_path = os.path.abspath(script_path)
    project_root = os.path.dirname(script_path)

    # Use "__main__" as the module name so the target script's own
    # `if __name__ == "__main__":` guard actually executes (this is what
    # triggers real function calls under the profiler).
    spec = importlib.util.spec_from_file_location("__main__", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["__speedcraft_target__"] = module

    profiler = cProfile.Profile()

    # Run the target module's top-level code under the profiler.
    # We wrap in try/finally so a script that raises still gives us partial stats.
    try:
        profiler.enable()
        spec.loader.exec_module(module)
    finally:
        profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")

    hot_functions: List[HotFunction] = []
    # stats.stats: {(filename, lineno, funcname): (cc, nc, tt, ct, callers)}
    for (filename, lineno, funcname), (cc, nc, tt, ct, _callers) in stats.stats.items():
        if funcname.startswith("<") or funcname == "profile_script":
            continue
        if not _is_user_code(filename, project_root):
            continue

        func_obj = getattr(module, funcname, None)
        if not callable(func_obj):
            continue  # only support top-level functions in v1 (no methods/nested)

        hot_functions.append(
            HotFunction(
                name=funcname,
                filename=filename,
                line_number=lineno,
                cumulative_time=ct,
                total_time=tt,
                n_calls=nc,
                func_obj=func_obj,
            )
        )

    hot_functions.sort(key=lambda f: f.cumulative_time, reverse=True)
    return hot_functions[:top_n], module


def format_report(hot_functions: List[HotFunction]) -> str:
    lines = ["\n🔥 Bottleneck Report (top user-defined functions by cumulative time)\n"]
    lines.append(f"{'#':<3}{'Function':<28}{'Calls':>10}{'Total(s)':>12}{'Cumulative(s)':>16}")
    lines.append("-" * 70)
    for i, hf in enumerate(hot_functions, 1):
        lines.append(
            f"{i:<3}{hf.name:<28}{hf.n_calls:>10}{hf.total_time:>12.4f}{hf.cumulative_time:>16.4f}"
        )
    return "\n".join(lines)
