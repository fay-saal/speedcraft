<div align="center">

# ⚡ SpeedCraft-AI

### The Auto-Cythonizer — turn slow Python into fast C, without writing a line of C.

<p>
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Cython-3.0-FFD43B?style=for-the-badge&logo=python&logoColor=black" />
  <img src="https://img.shields.io/badge/C-Compiled-00599C?style=for-the-badge&logo=c&logoColor=white" />
  <img src="https://img.shields.io/badge/Claude_API-LLM_Powered-D97757?style=for-the-badge&logo=anthropic&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-brightgreen?style=for-the-badge" />
</p>

<p>
  <a href="https://github.com/fay-saal/speedcraft-ai"><img src="https://img.shields.io/badge/▲_REPOSITORY-000000?style=for-the-badge&logo=github&logoColor=white" /></a>
  <a href="https://github.com/fay-saal/speedcraft-ai/issues"><img src="https://img.shields.io/badge/ISSUES-000000?style=for-the-badge&logo=github&logoColor=white" /></a>
  <a href="https://github.com/fay-saal/speedcraft-ai/stargazers"><img src="https://img.shields.io/github/stars/fay-saal/speedcraft-ai?style=for-the-badge&color=yellow" /></a>
</p>

</div>

<br>

```
$ speedcraft optimize slow_script.py

🔍 Profiling slow_script.py ...
🔥 Bottleneck: is_prime_count — 0.0019s cumulative
🤖 Requesting Cython translation from LLM...
🔨 Compiling generated Cython code...
🧪 Running differential test (300 random trials)...
✓ PASSED 300/300 trials — correctness verified.
⚡ Speedup: 19.6x
```

<br>

## `> overview`

---

Python developers write slow loops. Making them fast usually means learning Cython's type system and hand-porting code to C — a skill most Python devs never get around to.

**SpeedCraft-AI automates the whole pipeline:** it profiles your script, finds the actual bottleneck functions, asks an LLM to translate them into typed Cython, compiles them with `gcc`, and — before any of it touches your code — runs **200+ randomized differential tests** comparing the original and compiled output. If they don't match exactly, the conversion is thrown away and your original Python stays untouched.

No manual C. No blind trust in AI-generated code either.

<br>

## `> the safety layer`

---

This is the part that makes the tool trustworthy instead of just fast:

| Stage | What it does |
|---|---|
| **Eligibility gate** (AST-based) | Rejects functions with `try/except`, generators, closures, dicts/strings, or I/O calls *before* ever calling the LLM |
| **Differential testing** | Runs the original and compiled function on identical randomized inputs, hundreds of times, comparing outputs with float-tolerant equality |
| **Automatic fallback** | Any mismatch → conversion is discarded, original Python function is kept, reason is printed |

> **Real example from development:** an early Cython template used `int(num ** 0.5)` for a primality check. Floating-point `pow()` precision occasionally returned `4.999999...` instead of `5.0`, silently misclassifying `25` as prime. The differential tester caught it in 3 trials. This is exactly the class of bug that "looks right" testing misses.

<br>

## `> how it works`

---

```
cProfile → Eligibility (AST) → LLM → Cython → gcc compile → Differential Test (200x)
                                                                      │
                                                          ┌───────────┴───────────┐
                                                        PASS                    FAIL
                                                          │                       │
                                              persist .so + write shim    keep original Python
```

<br>

## `> scope`

---

**✅ Handles:** top-level, pure numeric, loop-heavy functions — prime counting, simulations, custom math, nested loops.

**❌ Does not handle (yet):** classes, generators, closures, string/dict-heavy code, I/O. These are rejected with a clear reason instead of silently mishandled.

This is **not** a Numba/Codon replacement — if your code is array-heavy numeric math, use those, they're mature and don't need an LLM in the loop. SpeedCraft-AI targets the gap: custom scalar/loop logic that doesn't fit neatly into `@jit`.

<br>

## `> install`

---

```bash
git clone https://github.com/fay-saal/speedcraft-ai.git
cd speedcraft-ai
pip install -e .
export ANTHROPIC_API_KEY=your_key_here
```

Requires a C compiler (`gcc` on Linux/Mac, MSVC Build Tools on Windows) — the same requirement Cython itself has.

<br>

## `> usage`

---

```bash
# profile + optimize (default: top 5 functions, 200 test trials)
speedcraft optimize my_script.py

# preview what would be converted, no API calls, no cost
speedcraft optimize my_script.py --dry-run

# tune rigor
speedcraft optimize my_script.py --top 3 --trials 500
```

Then swap your import:

```python
# before
from my_script import slow_function

# after
from my_script_accelerated import slow_function
```

<br>

## `> tech stack`

---

<p>
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Cython-FFD43B?style=flat-square&logo=python&logoColor=black" />
  <img src="https://img.shields.io/badge/gcc-A8B9CC?style=flat-square&logo=gnu&logoColor=black" />
  <img src="https://img.shields.io/badge/Claude_API-D97757?style=flat-square&logo=anthropic&logoColor=white" />
  <img src="https://img.shields.io/badge/cProfile-3776AB?style=flat-square&logo=python&logoColor=white" />
</p>

<br>

## `> status`

---

> v0.1, early release. Core pipeline (profiling, eligibility checking, compilation, differential testing) is tested end-to-end. LLM conversion prompt is functional but still being refined based on real-world feedback — issues/PRs welcome.

<br>

## `> license`

---

MIT © 2026 Faysal ([DieBack Theatre](https://github.com/fay-saal))

<br>

## `> links`

---

- **Repository:** [github.com/fay-saal/speedcraft-ai](https://github.com/fay-saal/speedcraft-ai)
- **Issues:** [github.com/fay-saal/speedcraft-ai/issues](https://github.com/fay-saal/speedcraft-ai/issues)

<div align="center">
<sub>Built with ⚡ by DieBack Theatre</sub>
</div>
