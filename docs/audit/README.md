# Audit, baseline and remediation backlog

This directory records the independent repository's audit, the measurements, and what to do next.
It is evidence, not a release note. Phase 2 stabilized the tree and qualified the benchmark suite;
[git-history.md](git-history.md) still applies unchanged (three commits, no upstream history).

| Page | Contents |
|---|---|
| [architecture.md](architecture.md) | Source-review findings and their status after the Phase 2 fixes. |
| [git-history.md](git-history.md) | The three-commit history, the integrity findings and why upstream bisection is unavailable. |
| [benchmark-assessment.md](benchmark-assessment.md) | What the older `perf_bench`/`pacing_bench`/`graphics_bench` tools measure well and what they miss. |
| [benchmark-qualification.md](benchmark-qualification.md) | Phase 2: the suite's method, repeatability, correctness coverage, contamination and limits. |
| [profiling.md](profiling.md) | Measured CPU/thread, memory and rendering evidence, and how to profile further. |
| [build-validation.md](build-validation.md) | The five Cargo profiles, the memory-aware wrapper, build times, memory, binary size and reproducibility. |
| [baseline.md](baseline.md) | The 5-repeat qualified baseline: provenance, results, statistics, correctness and limits. |
| [verification.md](verification.md) | Every check run in Phase 2, the defects fixed, and platform-specific exclusions. |
| [../benchmark-suite.md](../benchmark-suite.md) | The suite's scenarios, phases, statistics, comparison rule and tiers. |
| [../build-profiles.md](../build-profiles.md) | The profiles, memory math and wrapper usage. |

## What Phase 2 changed

- **Stabilization.** The Windows/Git-bash release-asset test, the Pterodactyl/AMP repository mismatch,
  two `horizon-client-render` Clippy failures, the HDR half-float tolerance, twelve launcher failures
  (space-containing temp paths, two missing i18n keys, a hardcoded upstream URL, stale generated
  docs) and the stale launcher command reference are fixed. The relay's bridge slot is released as
  soon as either end closes, instead of after the idle timeout. `streaming.rs` poisoned locks no longer
  panic the tick thread; autosave and player-writer errors surface; the per-root caches and uniform
  section sharing are bounded.
- **Benchmark.** Five repeats by default, warm-up/measurement/cooldown phases, alternating A/B
  builds, Student-t intervals, CV/IQR and non-destructive outliers, per-repeat raw data, binary and
  toolchain fingerprints, contamination detection, bounded traces, an instrumentation-overhead
  scenario, `world_ops` and scaling scenarios, and noise-aware comparison verdicts.
- **Build.** The wrapper uses available physical memory, never the page file, and serializes local
  wrapper builds; the five profiles were verified and the `bench` build measured.
- **Baseline.** Ten scenarios × five repeats, all valid, plus an independent five-scenario
  five-repeat run for repeatability, stored as `benchmarks/gameplay/baseline-qualified.json` and
  `baseline-repeat.json`.
- **CI.** `tools/bench_tiers.py` and `.github/workflows/bench.yml` run tiers 1–4; tier 1 is cheap,
  tiers 2–3 run nightly on the game runner, tier 4 is manual.

## Prioritized remediation backlog

Ordered by expected impact, confidence, difficulty and dependencies. Status is from Phase 2.

| # | Item | Impact | Confidence | Difficulty | Depends on | Status |
|---|---|---|---|---|---|---|
| 1 | Port `Check`/`valid()` workload gates to `perf_bench.py` stress scenes. | High | High | Low | — | **Open.** The new suite asserts; perf_bench stress scenes still do not. |
| 2 | Report integrated-server MSPT in `perf_bench`'s client tables. | High | Medium | Medium | — | **Open.** The gameplay suite records it; perf_bench still omits it. |
| 3 | Make `graphics_bench.py` use strict `wait_loaded`, not `wait-ready`. | High | High | Low | — | **Open.** |
| 4 | Make windowed FPS a stable regression signal on a shared desktop (offscreen and compositor controls, longer holds, or GPU-time-only gating). | High | Medium | Medium | Tier 3 runs | **Open.** CPU p50, mspt and RSS are stable now; FPS CIs are wide on this host. |
| 5 | Bound/replace the `'static` block-registry pointer key with a stable registry id. | Medium (ABA safety) | Medium | Medium | Registry lifecycle | **Documented**, not changed. |
| 6 | Reduce `tick_blocks` spikes (24 ms max for 16 pistons) and `spawn_natural` cost (~1.6 ms/tick). | Medium | Medium | Medium | Span evidence | **Measured**, not changed. |
| 7 | Cache `held_name()` if a profile shows it; intern particle sprite names. | Low–Medium | High (refuted for `held_name`) | Medium | Allocation profile | **Rejected for `held_name`**: `tick_hud` measures 0.014–0.023 ms/tick, ~0.03–0.05% of a tick. Particle interning remains allocation-profile work. |
| 8 | Allocation call-site profiling (`heaptrack`, ETW/WPA, dhat) and a permanent allocation counter behind a feature. | Medium | High | Medium | — | **Open.** The suite measures RSS/private/virtual but not allocations. |
| 9 | Per-thread CPU split without `psutil` (Windows). | Low–Medium | High | Low | — | **Open**; traces give per-thread wall time. |
| 10 | Align `client_tick_ms` definitions across Horizon and vanilla. | Medium (comparability) | Medium | Medium | perf_bench | **Open.** |
| 11 | Byte-for-byte Windows release reproducibility (PE timestamp/link determinism). | Low | High | High | Toolchain/linker | **Known limit**, documented in [build-validation.md](build-validation.md). |
| 12 | Review the release-signing key replacement and the fork update repository. | Integrity, not performance | High (diff) | Decision needed | Maintainer | **Open**, unchanged: maintainer decision ([git-history.md](git-history.md)). |

## What Phase 2 did not do

- No upstream history, remotes, merges or attribution changes.
- No engine-wide performance rewrite: changes are limited to defects with direct evidence.
- No `release-max` build or runtime comparison; the production profile is `release`/`bench`.
- No vanilla comparison from the new suite; that remains `tools/perf_bench.py`'s job.
- No long tier-4 soak (300 s+) in the checked-in baseline; the suite and tier 4 command exist, and the
  20 s mixed soak is the only slope recorded in the baseline.
