"""
compiler.py — Takes generated .pyx source, writes it to a temp build dir,
compiles it with Cython + setuptools, and imports the resulting extension
module so we get back a real, callable, compiled function object.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class CompileResult:
    success: bool
    compiled_func: Optional[Callable]
    build_dir: Optional[str]
    error: Optional[str] = None


def compile_cython_function(cython_source: str, func_name: str) -> CompileResult:
    """
    Compiles a .pyx string containing `func_name` and returns the loaded
    compiled function object. build_dir is returned so callers can clean up
    or persist it (e.g. to cache the compiled artifact for reuse).
    """
    module_name = f"speedcraft_ext_{uuid.uuid4().hex[:8]}"
    build_dir = tempfile.mkdtemp(prefix="speedcraft_build_")

    pyx_path = os.path.join(build_dir, f"{module_name}.pyx")
    setup_path = os.path.join(build_dir, "setup.py")

    with open(pyx_path, "w") as f:
        f.write(cython_source)

    setup_contents = f"""
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize("{module_name}.pyx", compiler_directives={{'language_level': "3"}}),
    script_args=["build_ext", "--inplace"],
)
"""
    with open(setup_path, "w") as f:
        f.write(setup_contents)

    try:
        result = subprocess.run(
            [sys.executable, "setup.py", "build_ext", "--inplace"],
            cwd=build_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return CompileResult(success=False, compiled_func=None, build_dir=build_dir,
                              error="Compilation timed out after 120s.")

    if result.returncode != 0:
        return CompileResult(
            success=False, compiled_func=None, build_dir=build_dir,
            error=f"Cython/gcc compilation failed:\n{result.stderr[-3000:]}",
        )

    # Find the compiled .so / .pyd file
    compiled_file = None
    for fname in os.listdir(build_dir):
        if fname.startswith(module_name) and (fname.endswith(".so") or fname.endswith(".pyd")):
            compiled_file = os.path.join(build_dir, fname)
            break

    if not compiled_file:
        return CompileResult(success=False, compiled_func=None, build_dir=build_dir,
                              error="Build succeeded but no compiled extension file was found.")

    try:
        spec = importlib.util.spec_from_file_location(module_name, compiled_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        compiled_func = getattr(module, func_name)
    except Exception as e:
        return CompileResult(success=False, compiled_func=None, build_dir=build_dir,
                              error=f"Failed to import compiled extension: {e}")

    return CompileResult(success=True, compiled_func=compiled_func, build_dir=build_dir)


def cleanup_build_dir(build_dir: Optional[str]) -> None:
    if build_dir and os.path.isdir(build_dir):
        shutil.rmtree(build_dir, ignore_errors=True)
