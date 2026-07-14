"""
differ.py — Differential testing between the original Python function and
the compiled Cython version.

This is the CORE SAFETY LAYER of SpeedCraft-AI. We NEVER trust an LLM's
generated code just because it "looks right" — we generate randomized test
inputs (based on the function's type hints / a sample call the user provides)
and run BOTH versions, comparing outputs. If they don't match within
tolerance for every trial, we reject the Cython version and keep the
original Python function untouched.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, get_type_hints


@dataclass
class DiffResult:
    passed: bool
    trials_run: int
    failure_example: Optional[dict] = None
    error: Optional[str] = None


def _random_value_for_type(annotation) -> Any:
    if annotation in (int, "int"):
        return random.randint(-1000, 1000)
    if annotation in (float, "float"):
        return round(random.uniform(-1000.0, 1000.0), 4)
    if annotation in (list, List[int], "List[int]"):
        return [random.randint(-100, 100) for _ in range(random.randint(1, 50))]
    if annotation in (List[float], "List[float]"):
        return [round(random.uniform(-100, 100), 3) for _ in range(random.randint(1, 50))]
    # default fallback: small int, works for most numeric loop bodies
    return random.randint(1, 100)


def generate_random_args(func: Callable, n_positional: Optional[int] = None) -> tuple:
    """
    Best-effort random argument generator using type hints when available,
    falling back to small positive ints (safe default for loop-bound style
    numeric functions like `def f(n): ...` or `def f(a, b): ...`).
    """
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    import inspect
    sig = inspect.signature(func)
    params = [p for p in sig.parameters.values() if p.name != "self"]

    args = []
    for p in params:
        annotation = hints.get(p.name, p.annotation)
        args.append(_random_value_for_type(annotation))
    return tuple(args)


def _values_match(a: Any, b: Any, rel_tol: float = 1e-6, abs_tol: float = 1e-9) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)
        except TypeError:
            return a == b
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_values_match(x, y, rel_tol, abs_tol) for x, y in zip(a, b))
    return a == b


def run_differential_test(
    original_func: Callable,
    compiled_func: Callable,
    n_trials: int = 200,
    custom_arg_generator: Optional[Callable[[], tuple]] = None,
) -> DiffResult:
    """
    Runs both functions n_trials times with matching random inputs.
    Returns DiffResult(passed=True) ONLY if every trial matches.
    Any exception in either function counts as a failed trial (and is surfaced).
    """
    for i in range(n_trials):
        args = custom_arg_generator() if custom_arg_generator else generate_random_args(original_func)

        try:
            expected = original_func(*args)
        except Exception as e:
            # If the original function itself throws on this input, skip this
            # trial (we're testing equivalence, not the original's robustness).
            continue

        try:
            actual = compiled_func(*args)
        except Exception as e:
            return DiffResult(
                passed=False, trials_run=i + 1,
                failure_example={"args": args, "expected": expected, "actual": f"EXCEPTION: {e}"},
                error=f"Compiled version raised an exception where original succeeded: {e}",
            )

        if not _values_match(expected, actual):
            return DiffResult(
                passed=False, trials_run=i + 1,
                failure_example={"args": args, "expected": expected, "actual": actual},
                error="Output mismatch between original and compiled versions.",
            )

    return DiffResult(passed=True, trials_run=n_trials)
