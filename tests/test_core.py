"""
Basic unit tests that don't require an ANTHROPIC_API_KEY or network access —
they test the eligibility gate, differential tester, and compiler using
hand-written Cython (simulating what the LLM would produce).

Run with: python -m pytest tests/
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from speedcraft import extractor, differ, compiler


def numeric_ok(n):
    total = 0
    for i in range(n):
        total += i * i
    return total


def uses_try_except(n):
    try:
        return 10 / n
    except ZeroDivisionError:
        return 0


def uses_dict(n):
    d = {}
    for i in range(n):
        d[i] = i * 2
    return len(d)


def uses_string(n):
    s = "prefix"
    for i in range(n):
        s += str(i)
    return s


def test_eligibility_accepts_pure_numeric():
    ext = extractor.extract(numeric_ok)
    assert ext.eligibility.eligible, ext.eligibility.reasons


def test_eligibility_rejects_try_except():
    ext = extractor.extract(uses_try_except)
    assert not ext.eligibility.eligible
    assert any("try/except" in r for r in ext.eligibility.reasons)


def test_eligibility_rejects_dict():
    ext = extractor.extract(uses_dict)
    assert not ext.eligibility.eligible


def test_eligibility_rejects_string_ops():
    ext = extractor.extract(uses_string)
    assert not ext.eligibility.eligible


def test_differential_catches_broken_conversion():
    """A deliberately WRONG cython version (off-by-one) must be rejected."""
    broken_cython = """
cpdef long numeric_ok(long n):
    cdef long total = 0
    cdef long i
    for i in range(n + 1):  # BUG: off-by-one, should be range(n)
        total += i * i
    return total
"""
    result = compiler.compile_cython_function(broken_cython, "numeric_ok")
    assert result.success, result.error
    diff = differ.run_differential_test(numeric_ok, result.compiled_func, n_trials=50)
    assert diff.passed is False


def test_differential_accepts_correct_conversion():
    correct_cython = """
cpdef long numeric_ok(long n):
    cdef long total = 0
    cdef long i
    for i in range(n):
        total += i * i
    return total
"""
    result = compiler.compile_cython_function(correct_cython, "numeric_ok")
    assert result.success, result.error
    diff = differ.run_differential_test(numeric_ok, result.compiled_func, n_trials=50)
    assert diff.passed is True


if __name__ == "__main__":
    test_eligibility_accepts_pure_numeric()
    test_eligibility_rejects_try_except()
    test_eligibility_rejects_dict()
    test_eligibility_rejects_string_ops()
    test_differential_catches_broken_conversion()
    test_differential_accepts_correct_conversion()
    print("All tests passed.")
