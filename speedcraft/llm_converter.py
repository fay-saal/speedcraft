"""
llm_converter.py — Sends an eligible Python function to Claude and asks
for a Cython (.pyx) translation with static typing.

We keep the prompt tightly scoped (numeric-only functions, per extractor.py's
eligibility gate) so the model has a much easier, safer job than "convert
arbitrary Python to C".
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

try:
    import anthropic
except ImportError:
    anthropic = None


SYSTEM_PROMPT = """You are a Cython optimization expert. You convert numeric, \
loop-heavy Python functions into equivalent, high-performance Cython code.

Rules you MUST follow:
1. Output ONLY a single ```cython fenced code block. No prose before or after.
2. Use `cpdef` for the function so it's callable from pure Python.
3. Add static C types (cdef int, cdef double, double[:], etc.) to all local \
variables and loop counters where it's safe and beneficial.
4. Preserve the EXACT function name, parameter order, and behavior of the \
original function. Do not change what it computes.
5. Do not add print statements, I/O, or side effects that weren't in the original.
6. Add `# cython: boundscheck=False` and `# cython: wraparound=False` directives \
at the top ONLY if you are confident the function never relies on negative \
indexing or out-of-bounds behavior; otherwise omit them (safety first).
7. If inputs are Python lists, either keep them as typed lists/memoryviews or \
convert internally — but the function signature accepted by Python callers \
must remain compatible with how the original Python function was called \
(same argument types accepted).
8. Do not invent helper functions unless strictly necessary; keep it self-contained.
"""

USER_PROMPT_TEMPLATE = """Convert this Python function to optimized Cython.

```python
{source}
```

Respond with only the Cython code block."""


@dataclass
class ConversionResult:
    success: bool
    cython_code: Optional[str]
    raw_response: Optional[str]
    error: Optional[str] = None


def _extract_code_block(text: str) -> Optional[str]:
    match = re.search(r"```(?:cython|python)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def convert_to_cython(source: str, model: str = "claude-sonnet-4-6") -> ConversionResult:
    """
    Calls the Anthropic API to translate `source` (a Python function's source
    code) into Cython. Requires ANTHROPIC_API_KEY to be set in the environment.
    """
    if anthropic is None:
        return ConversionResult(
            success=False, cython_code=None, raw_response=None,
            error="The 'anthropic' package is not installed. Run: pip install anthropic",
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ConversionResult(
            success=False, cython_code=None, raw_response=None,
            error="ANTHROPIC_API_KEY environment variable is not set.",
        )

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": USER_PROMPT_TEMPLATE.format(source=source)}],
        )
    except Exception as e:  # network / auth / rate limit errors
        return ConversionResult(success=False, cython_code=None, raw_response=None, error=str(e))

    raw_text = "".join(block.text for block in response.content if hasattr(block, "text"))
    code = _extract_code_block(raw_text)

    if not code:
        return ConversionResult(
            success=False, cython_code=None, raw_response=raw_text,
            error="Could not find a code block in the model's response.",
        )

    return ConversionResult(success=True, cython_code=code, raw_response=raw_text)
