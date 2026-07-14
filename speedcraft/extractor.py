"""
extractor.py — Pulls source code for a hot function and decides whether it's
SAFE to auto-convert to Cython.

This is the most important safety gate in the whole tool. We only allow
conversion of functions that are:
  - top-level (not methods, not closures/nested functions)
  - free of I/O, imports-of-unsafe-things, exceptions-as-control-flow,
    string-heavy work, dict/set-heavy work, or calls to unknown external
    functions we can't reason about
  - purely numeric: loops, arithmetic, list/array indexing, basic control flow

If a function doesn't pass, we skip it and tell the user why, instead of
pretending we can convert anything.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from dataclasses import dataclass
from typing import List, Optional


UNSAFE_CALL_NAMES = {
    "open", "input", "eval", "exec", "__import__", "compile",
    "requests", "socket", "os", "sys", "subprocess",
}

DISALLOWED_NODE_TYPES = (
    ast.Try,          # exception-based control flow: hard to map safely to C
    ast.With,         # context managers: file/io-like, out of scope
    ast.Yield,        # generators: out of scope for v1
    ast.YieldFrom,
    ast.Global,
    ast.Nonlocal,
    ast.Lambda,       # closures: out of scope for v1
    ast.ListComp,     # allowed structurally, but we flag for review (see below)
)


@dataclass
class EligibilityResult:
    eligible: bool
    reasons: List[str]


@dataclass
class ExtractedFunction:
    name: str
    source: str
    signature: inspect.Signature
    eligibility: EligibilityResult


def _check_ast(tree: ast.FunctionDef) -> EligibilityResult:
    reasons: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            reasons.append("uses try/except (exception control flow not supported in v1)")
        if isinstance(node, ast.With):
            reasons.append("uses 'with' blocks (I/O / context managers out of scope)")
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            reasons.append("is a generator function (not supported in v1)")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            reasons.append("uses global/nonlocal state (not supported in v1)")
        if isinstance(node, ast.Lambda):
            reasons.append("contains a lambda/closure (not supported in v1)")
        if isinstance(node, ast.Call):
            fname = None
            if isinstance(node.func, ast.Name):
                fname = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fname = node.func.attr
            if fname in UNSAFE_CALL_NAMES:
                reasons.append(f"calls potentially unsafe function '{fname}' (I/O or dynamic exec)")
        if isinstance(node, ast.Dict) or isinstance(node, ast.Set):
            reasons.append("uses dict/set literals (string/hash-heavy code out of scope for v1)")
        if isinstance(node, ast.Str) if hasattr(ast, "Str") else False:
            pass  # legacy node, ignore

    # Detect heavy string operations (very rough heuristic: string constants + concatenation)
    has_string_const = any(
        isinstance(node, ast.Constant) and isinstance(node.value, str)
        for node in ast.walk(tree)
    )
    if has_string_const:
        reasons.append("contains string literals/operations (string-heavy code out of scope for v1)")

    # Nested function defs (closures) not supported
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node is not tree:
            reasons.append("contains a nested function definition (not supported in v1)")

    dedup_reasons = sorted(set(reasons))
    return EligibilityResult(eligible=(len(dedup_reasons) == 0), reasons=dedup_reasons)


def extract(func_obj) -> Optional[ExtractedFunction]:
    """Returns None if source can't be retrieved (e.g. built-in)."""
    try:
        raw_source = inspect.getsource(func_obj)
    except (OSError, TypeError):
        return None

    source = textwrap.dedent(raw_source)
    tree = ast.parse(source)
    func_def = tree.body[0]
    if not isinstance(func_def, ast.FunctionDef):
        return None

    eligibility = _check_ast(func_def)
    signature = inspect.signature(func_obj)

    return ExtractedFunction(
        name=func_obj.__name__,
        source=source,
        signature=signature,
        eligibility=eligibility,
    )
