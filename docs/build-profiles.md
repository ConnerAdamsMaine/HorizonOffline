# Build profiles and memory

Horizon is large enough that the profile, not the code, decides whether an optimized build is
practical on a laptop. This page documents the profiles in the root `Cargo.toml`, the memory each
one costs, and the wrapper that chooses a safe concurrency for the machine in front of you.

## Profiles

| Profile | Use | LTO | CGUs | Incremental | Debug info | Strip | Output folder |
|---|---|---|---:|---:|---|---|---|
| `dev` | edit, debug, `cargo test` | off | 256 | yes | line tables | no | `target/debug` |
| `fast` | play, quick optimized iteration | off | 16 | yes | none | debuginfo | `target/fast` |
| `release` | production / distribution | Thin | 4 | no | none | debuginfo | `target/release` |
| `bench` | performance measurements | Thin | 4 | no | line tables | no | `target/release` |
| `release-max` | opt-in whole-program build | Fat | 1 | no | none | symbols | `target/release` |

`bench` deliberately matches `release` in LTO and codegen units: a measurement build that optimizes
differently from what players run is not evidence about players. It keeps line tables so a profile
can name functions. Cargo's built-in `bench` profile writes to `target/release`, so build the game
once and point `tools/gameplay_bench.py --build target/release` at it.

`release-max` is the only profile allowed to use Fat LTO and one codegen unit. It is for release
engineers with a large machine, not a default.

The old `release` profile used Thin LTO with `codegen-units = 1`. That gives one enormous LLVM module
for the final crates and a long, memory-hungry link. The current four units still allow cross-crate
inlining and compile in parallel; the runtime difference has not been measured on this fork, so it
is a tradeoff to verify before a release, not a claim. Use `release-max` when that last difference
matters.

## What actually exhausts memory

Three different failures look alike at the terminal. Keep them separate:

1. **Compilation-memory exhaustion.** Cargo starts one rustc per logical CPU by default. A
   `horizon-client` cold build has hundreds of units; several large ones (`horizon-client`,
   `horizon-world`, the patched `naga`/`wgpu-hal`, `windows`) can run together. On a 16 GiB
   machine that is a swap storm or an OOM kill. This is a jobs problem, not a profile problem.
2. **Linker exhaustion (mainly MSVC).** The final binary link is one process. `link.exe` holds the
   image, PDB and symbol database; with LTO it also holds the cross-crate IR. `LNK1102: out of
   memory` or a very long link is this failure. `lld-link` (or `rust-lld`) usually lowers both
   memory and time; it is kept opt-in because static CRT combinations are less battle-tested.
3. **Pathological LTO.** Only `release-max` should need 8–16 GiB. If plain `release` blows up,
   first try `-j 1` and a stable toolchain; suspect a nightly LLVM regression rather than the
   profile.

Other contributors already handled: `dev` uses line tables rather than full debug info (full debug
made test/example binaries hundreds of megabytes), and `release` strips debuginfo.

## Use the wrapper

```sh
python3 tools/cargo_build.py --profile fast
python3 tools/cargo_build.py --profile release
python3 tools/cargo_build.py --profile bench
python3 tools/cargo_build.py --profile release-max --jobs 4
python3 tools/cargo_build.py --profile fast --dry-run   # print the estimate and command
```

The wrapper computes jobs from **available physical memory** (installed RAM capped by what is free
now), the profile's per-unit estimate and a 25% reserve. It never counts the page file, so a Windows
machine cannot "afford" more compilers because it has a large page file:

| Profile | Estimated MiB per job |
|---|---:|
| `dev` | 900 |
| `fast` | 1,800 |
| `release` | 2,200 |
| `bench` | 2,400 |
| `release-max` | 4,000 |

`--jobs N` and `CARGO_BUILD_JOBS` override it. `CARGO_INCREMENTAL` is forced on for `dev`/`fast` and
off for the optimized profiles; incremental artifacts are not reproducible and slow a cold release
build. The wrapper always passes `--locked`. Wrapper builds on one checkout are serialized with an
advisory lock (`.local/cargo-build.lock`); `--no-lock` bypasses it. This keeps two simultaneous
10-job builds from exhausting the machine, which is the failure mode the wrapper exists to prevent.

## Measured build

On the audit machine (12 logical CPUs, 48 GiB RAM, Windows 10, rustc 1.100.0-nightly):

| Build | Profile | Wall time | Peak live compiler/linker working set | Binary |
|---|---|---:|---:|---:|
| cold, wrapper jobs=12 (Phase 1) | `bench` (release-equivalent) | 17m 34s | 9.4 GiB | 98 MiB (with line tables) |
| full rebuild after stabilization (jobs=10) | `bench` | 18m 50s | 8,837 MiB | 102,137,856 B |
| forced relink after `touch` (jobs=10) | `bench` | 12m 47s | 9,019 MiB | 102,137,856 B |
| no-op | `bench` | 1.15s | — | unchanged |
| warm `fast` rebuild | `fast` | see [build-validation](audit/build-validation.md) | | |

The full Phase 2 rebuild recompiled the changed client crates and linked; the forced relink is one
crate plus the Thin-LTO link, showing the link is the long pole. `cargo_build.py --dry-run` on this
machine reports 12 jobs for `dev`/`fast`, 11 for `release`, 10 for `bench` and 6 for `release-max`
with about 33.9 GiB free. See [build-validation](audit/build-validation.md) for reproducibility
(the PE/link output is not byte-identical after a forced relink) and the remaining limits.

The 9.4 GiB is the sum of the working sets of all concurrent `rustc`, `cargo` and linker processes,
sampled every 3 s; a single unit's peak is lower. The previous `release` shape was not built for
comparison because it is the configuration this change removes; use `build_times.py` on a branch
that still has it if a before/after number is needed.

## Windows linker (opt-in)

Do not change the default. To try `lld-link` locally, add to a **local** (untracked)
`.cargo/config.toml`:

```toml
[target.x86_64-pc-windows-msvc]
linker = "lld-link"
```

or pass `RUSTFLAGS="-C linker=lld-link"`. Verify the static CRT builds CI produces
(`+crt-static`) still run before proposing it as a default. Record wall time and the sum of
`rustc`/linker working sets for a cold `fast` build.

## Verification checklist

1. `python3 tools/cargo_build.py --profile bench --dry-run` — the command and estimate match this
   page.
2. `cargo metadata --no-deps` — one `[profile]` source; the five profiles above.
3. Build `bench` cold, then `--smoke` on the resulting game.
4. `python3 tools/build_times.py run --profiles dev,fast` before/after a profile change; compare
   with `build_times.py compare`.
5. On a small-RAM machine, compare bare `cargo build --profile fast` with
   `tools/cargo_build.py --profile fast`: the former should show the thrash, the latter should not.
