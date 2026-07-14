"""
cli.py — SpeedCraft-AI command-line interface.

Usage:
    speedcraft optimize path/to/script.py
    speedcraft optimize path/to/script.py --top 3 --trials 300
    speedcraft optimize path/to/script.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from . import profiler, extractor, llm_converter, differ, compiler as compiler_mod, injector


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _c(text: str, color: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{RESET}"


def run_optimize(args: argparse.Namespace) -> int:
    script_path = os.path.abspath(args.script)
    if not os.path.isfile(script_path):
        print(_c(f"Error: file not found: {script_path}", RED))
        return 1

    print(_c(f"\n🔍 Profiling {os.path.basename(script_path)} ...", CYAN))
    try:
        hot_functions, module = profiler.profile_script(script_path, top_n=args.top)
    except Exception as e:
        print(_c(f"Error while running/profiling target script: {e}", RED))
        return 1

    if not hot_functions:
        print(_c("No user-defined hot functions found to optimize. Nothing to do.", YELLOW))
        return 0

    print(profiler.format_report(hot_functions))

    accelerated: list[str] = []
    module_name_map: dict[str, str] = {}
    cache_dir = None
    project_root = os.path.dirname(script_path)

    for hf in hot_functions:
        print(_c(f"\n--- Evaluating '{hf.name}' ---", BOLD))

        extracted = extractor.extract(hf.func_obj)
        if extracted is None:
            print(_c(f"  ⚠ Could not extract source for '{hf.name}'. Skipping.", YELLOW))
            continue

        if not extracted.eligibility.eligible:
            print(_c(f"  ⚠ Skipping '{hf.name}' — not eligible for auto-conversion:", YELLOW))
            for reason in extracted.eligibility.reasons:
                print(f"      - {reason}")
            continue

        print(f"  ✓ Eligible for Cython conversion.")

        if args.dry_run:
            print(_c("  (dry-run) Would call LLM to convert this function.", CYAN))
            continue

        print("  🤖 Requesting Cython translation from LLM...")
        conv = llm_converter.convert_to_cython(extracted.source, model=args.model)
        if not conv.success:
            print(_c(f"  ✗ LLM conversion failed: {conv.error}", RED))
            continue

        print("  🔨 Compiling generated Cython code...")
        comp = compiler_mod.compile_cython_function(conv.cython_code, hf.name)
        if not comp.success:
            print(_c(f"  ✗ Compilation failed:\n{comp.error}", RED))
            compiler_mod.cleanup_build_dir(comp.build_dir)
            continue

        print(f"  🧪 Running differential test ({args.trials} random trials)...")
        diff_result = differ.run_differential_test(
            hf.func_obj, comp.compiled_func, n_trials=args.trials
        )

        if not diff_result.passed:
            print(_c(f"  ✗ Differential test FAILED after {diff_result.trials_run} trials.", RED))
            print(f"      {diff_result.error}")
            if diff_result.failure_example:
                print(f"      args={diff_result.failure_example['args']}")
                print(f"      expected={diff_result.failure_example['expected']!r}")
                print(f"      actual={diff_result.failure_example['actual']!r}")
            print(_c("  → Keeping original Python function. No changes made.", YELLOW))
            compiler_mod.cleanup_build_dir(comp.build_dir)
            continue

        # Passed! Benchmark real speedup on a batch of calls.
        n_bench = 2000
        test_args = [differ.generate_random_args(hf.func_obj) for _ in range(n_bench)]

        t0 = time.perf_counter()
        for a in test_args:
            hf.func_obj(*a)
        py_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        for a in test_args:
            comp.compiled_func(*a)
        cy_time = time.perf_counter() - t0

        speedup = py_time / cy_time if cy_time > 0 else float("inf")
        print(_c(
            f"  ✓ PASSED {diff_result.trials_run}/{diff_result.trials_run} trials — "
            f"correctness verified.", GREEN
        ))
        print(_c(f"  ⚡ Speedup: {speedup:.1f}x  (python {py_time*1000:.2f}ms → cython {cy_time*1000:.2f}ms for {n_bench} calls)", GREEN))

        # find module name used by compiler (derived from build_dir contents)
        so_files = [f for f in os.listdir(comp.build_dir) if f.endswith(".so") or f.endswith(".pyd")]
        module_name = so_files[0].split(".")[0] if so_files else None

        cache_dir = injector.persist_compiled_artifact(comp.build_dir, module_name, project_root)
        module_name_map[hf.name] = module_name
        accelerated.append(hf.name)
        compiler_mod.cleanup_build_dir(comp.build_dir)

    if accelerated and not args.dry_run:
        shim_path = injector.write_accelerated_shim(
            script_path, accelerated, cache_dir, module_name_map
        )
        print(_c(f"\n✅ Done. {len(accelerated)} function(s) accelerated: {', '.join(accelerated)}", GREEN))
        print(f"   Import from: {os.path.basename(shim_path)}")
        print(f"   Example: from {os.path.splitext(os.path.basename(shim_path))[0]} import {accelerated[0]}")
    elif not args.dry_run:
        print(_c("\nNo functions were successfully accelerated.", YELLOW))

    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="speedcraft",
        description="SpeedCraft-AI: Auto-detect and accelerate slow numeric Python functions using AI-generated Cython.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    opt = sub.add_parser("optimize", help="Profile and optimize a Python script")
    opt.add_argument("script", help="Path to the target Python script")
    opt.add_argument("--top", type=int, default=5, help="Number of hottest functions to consider (default: 5)")
    opt.add_argument("--trials", type=int, default=200, help="Number of differential test trials per function (default: 200)")
    opt.add_argument("--model", default="claude-sonnet-4-6", help="Anthropic model to use for conversion")
    opt.add_argument("--dry-run", action="store_true", help="Only show what would be converted, without calling the LLM")
    opt.set_defaults(func=run_optimize)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
