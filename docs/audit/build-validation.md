# Build-profile and build-wrapper validation

Profiles, memory math, the resource-aware wrapper and their measured behaviour. The common
developer commands are in [build-profiles.md](../build-profiles.md); this page is the Phase 2
evidence.

## Profiles as configured

| Profile | LTO | CGU | Incremental | Debug info | Strip | Output |
|---|---|---:|---|---|---|---|
| `dev` | off (Cargo default) | 256 (default) | yes | line tables | no | `target/debug` |
| `fast` | off (inherits release then overrides) | 16 | yes | none | debuginfo | `target/fast` |
| `release` | Thin | 4 | no | none | debuginfo | `target/release` |
| `bench` | Thin | 4 | no | line tables | no | `target/release` |
| `release-max` | Fat | 1 | no | none | symbols | `target/release` |

Verified by reading the single `[profile]` block in the root `Cargo.toml` (`cargo metadata
--no-deps` reports one manifest source) and by observing each profile's output folder. `bench`
matches `release` in LTO and codegen units, so a measurement build optimizes like the player build.
`release-max` was **not** built: it is opt-in for large machines and is not the production profile.

## Wrapper

`tools/cargo_build.py` now:

- reads **physical** memory (`GlobalMemoryStatusEx.ullTotalPhys`, `sysctl hw.memsize`,
  `/proc/meminfo MemTotal`) and never counts the page file, which the Windows struct also reports;
- also reads **available** memory (`ullAvailPhys`, `MemAvailable`, `psutil`) and uses
  `min(total, available)` before the 25% reserve, so a second build or a running game lowers the job
  count instead of pushing the machine into the page file;
- caps jobs at logical CPUs and the profile's per-job estimate;
- serializes wrapper invocations on this checkout with `.local/cargo-build.lock` (advisory
  `flock`/`msvcrt` lock, `--no-lock` to bypass), because two 10-job builds on one machine is exactly
  the exhaustion the wrapper prevents;
- forces `CARGO_INCREMENTAL=0` for optimized profiles, keeps it on for `dev`/`fast`, and always
  passes `--locked`;
- reports the estimate and the exact command on stderr before running.

Tests: `python3 -m unittest tests.test_cargo_build` → 9 passed, including the available-memory
clamp (48 GiB installed / 8 GiB free → 2 jobs for `release`), the unknown-memory cap and the profile
set.

`--dry-run` on this machine (48,866 MiB, 12 logical CPUs, ~33.9 GiB free):

| Profile | Jobs | Estimated peak compiler memory |
|---|---:|---:|
| dev | 12 | 10,800 MiB |
| fast | 12 | 21,600 MiB |
| release | 11 | 24,200 MiB |
| bench | 10 | 24,000 MiB |
| release-max | 6 | 24,000 MiB |

## Measured builds

All with the wrapper, Windows 10, rustc 1.100.0-nightly, `CARGO_INCREMENTAL=0`, peak = sum of the
working sets of concurrent `rustc`/`cargo`/`link` processes sampled every 3 s (a single unit's peak
is lower; short peaks can be missed).

| Build | Profile | Wall | Peak compiler working set | Binary |
|---|---|---:|---:|---:|
| Cold, Phase 1 wrapper (jobs 12) | `bench` | 17 m 34 s | 9.4 GiB | 98 MiB with line tables |
| Full rebuild after Phase 2 source changes (jobs 10) | `bench` | 18 m 50 s | 8,837 MiB | 102,137,856 B (97.4 MiB) |
| `touch crates/horizon-client/src/lib.rs`, then rebuild | `bench` | 12 m 47 s | 9,019 MiB | 102,137,856 B |
| No-op rebuild | `bench` | 1.15 s | — | unchanged |
| Rebuild after Phase 2 source changes (jobs 10) | `fast` | 15 m 19 s | 4,471 MiB | 97,671,168 B (93.1 MiB, no line tables) |

The forced relink's 12 m 47 s is one crate plus the Thin-LTO link: the link, not compilation, is the
long pole. The full rebuild also recompiled `horizon-client-render`, `horizon-client-lib`,
`horizon-bench` and `horizon-client`.

### Reproducibility

- No-op rebuild: identical SHA-256 (`ee81558e…`).
- Forced relink after touching a source file with unchanged contents: the binary **differs** from
  byte 289 onward (SHA-256 `bf934eb6…`). Offset 289 is inside the PE header/link metadata, and the
  inputs were identical. Byte-for-byte reproducibility is therefore **not** provided on this
  Windows/MSVC toolchain; the binary size and behaviour are unchanged, and the source commit plus
  the build command are recorded in every benchmark report. A release check should compare the signed
  artifacts CI produces, not a locally relinked binary.
- `.local/cargo-build.lock` serializes local wrapper builds; CI uses separate build folders.

### Runtime tradeoff

`bench` (Thin/4) is the production-equivalent build. `fast` (no LTO, 16 CGUs, incremental) is for
iteration. A controlled comparison was attempted: the same four scenarios (`idle`, `entities`,
`redstone`, `mixed`), 3 repeats, offscreen, same binary conditions, against the same machine.

| Scenario | CPU p50 fast/bench | `tick.mspt` fast/bench | p99 fast/bench | RSS fast/bench |
|---|---:|---:|---:|---:|
| idle | 1.00 | 1.10 | 0.52 | 1.00 |
| entities | 1.03 | 1.00 | 1.69 | 0.99 |
| redstone | 0.62 | 0.93 | 0.58 | 1.00 |
| mixed | 0.77 | — | 1.09 | 1.01 |

The CPU/tick ratios straddle 1 and the frame p99 ratios swing both ways; at this sample size and on
this shared host there is **no demonstrated runtime regression** from `fast`, and no evidence that it
is faster either. It remains the iteration profile, not a measurement profile: the published
baseline uses `bench`. `release-max` remains unmeasured and is not recommended on a 12-core/48 GiB
machine without checking its ~8–16 GiB link.

## What the profiles mean for ordinary hardware

The wrapper's job count scales down with the profile's per-unit cost and the available memory. On an
8 GiB laptop the `release` estimate is 2 jobs and `release-max` 1; the wrapper will not start a
machine-wide LTO build by default. `dev` uses line tables instead of full debug info, which keeps
test binaries manageable. The Windows linker remains the default; `lld-link` is opt-in and
unvalidated here (documented in [build-profiles.md](../build-profiles.md)).
