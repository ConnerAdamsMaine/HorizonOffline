# Stabilization and verification (Phase 2)

What was broken, why, what was changed, and what was executed on the machine available to this
phase. This supersedes the Phase 1 verification notes; the Phase 1 measurement record remains in
[baseline-eb1e547](../../benchmarks/gameplay/baseline-eb1e547-20261112-070113.json) and the audit
history.

## Machine and checkout

| Item | Value |
|---|---|
| OS | Windows 10.0.19045, x86_64 |
| CPU | Intel Core i7-8700, 6 cores / 12 threads |
| RAM | 48,866 MiB |
| GPU | NVIDIA Quadro P2000, Vulkan, driver 582.78 |
| Toolchain | `rustc 1.100.0-nightly (f7575a9da 2026-09-24)`, `cargo 1.100.0-nightly` |
| Python | 3.15.2 |
| Checkout | `C:/Users/Conner Adams/Desktop/HorizonOffline` (path contains spaces) |
| Branch | `main`, commit `eb1e547` plus the Phase 1 and Phase 2 working tree |

The machine was shared with the development application throughout. That is recorded in the
benchmark reports as background CPU and is the main qualification limit of the new baseline.

## Defects and repairs

| # | Symptom | Actual cause | Scope | Repair | Evidence |
|---|---|---|---|---|---|
| 1 | 4 × `test_optional_release_assets` failed with `execvpe(/bin/bash) failed` | Windows `CreateProcess` resolves a bare `bash` through the system directory before `PATH`, so Python ran `C:\Windows\System32\bash.exe` (the WSL launcher) although `shutil.which` found Git's bash. A second, real portability bug hid behind it: `Path.write_text` produced CRLF fixtures, and Git's `sha256sum` prints GNU's binary `*` marker. | Windows + Git Bash environment; the test itself is Linux-first | Resolve the shell/tool paths with `shutil.which`, put the shell's folder first on `PATH`, probe that it runs OpenSSL, write fixture bytes with `write_bytes`, and accept GNU's `*name` checksum form. If no runnable POSIX shell exists the test still skips with a specific reason. No assertion was removed. | `python3 -m unittest tests.test_optional_release_assets tests.test_server_panels` → 12 tests OK |
| 2 | `test_server_panels.AmpTests.test_it_installs_with_the_eggs_script_and_starts_with_the_start_script` failed | `eb1e547` retargeted the Pterodactyl egg's install script to this repository but left the AMP update template on `horizon-rust/horizon`. The two panel paths genuinely disagreed; the test was right. | Product packaging data, not a test assumption | Point both AMP references at the independent repository (`ConnerAdamsMaine/HorizonOffline`), the same value the egg and the server's self-update use. | Same 12-test run |
| 3 | `horizon-client-render` Clippy failed with `recursion-depth-exceeding-limit` at `gfx/cull.rs:675` | The new compiler lint evaluates `Send` for `impl FnOnce() + Send` and walks wgpu-core's nested `Arc`/lock/storage types past the default recursion depth. The bound is real; the depth is not this repository's type. The lint is crate-wide, not per function. | Toolchain/compiler limitation | `#![recursion_limit = "256"]` on the crate root with a comment naming the closure and the wgpu types. | `cargo clippy -p horizon-client-render -p horizon-client -p horizon-bench --all-targets -- -D warnings` → exit 0 |
| 4 | `horizon-client-render` Clippy also failed with `unreachable call` at `audio.rs:1124` | Real dead code: without the `audio` feature `type Stream = Infallible`, so `open_named` can only return `Err`, and the `Ok` arm of the caller cannot be constructed. The old `#[cfg(not(feature = "audio"))] open_named` made the compiler prove exactly that. | Genuine implementation shape, no-audio builds | Split output initialisation by feature: the audio build keeps the fallible open/fallback match; the no-audio build reports the same warning and starts with no stream. Removed the impossible helper. | Same Clippy run; full `horizon-client-render` tests pass |
| 5 | `gfx::hdr::tests::the_menu_blur_keeps_the_light_it_blurs` failed at `3.9882813` against a `0.01` absolute tolerance | Measured `3.98828125 = 4 − 3·2⁻⁸`: six blur/composite passes on an `Rgba16Float` target quantize the light in half-float steps of `2⁻⁸` near 4.0. The pipeline kept the light; the test required 0.25% of a target whose precision at 4.0 is 0.1% per step. | GPU/format-precision-dependent assertion | Tolerance is now 0.5% relative, documented with the exact value and the format's step. The assertion still fails a real darkening (e.g. a lost copy or a zeroed blur). | `cargo test -p horizon-client-render --lib` → 1758 passed, 0 failed, 61 ignored |
| 6 | `horizon-relay` test `a_bridge_gives_its_slot_back_when_either_end_closes` failed deterministically: "bridges stuck at 1" | Real defect: the bridge runs a copy in each direction and joins the sibling. When the guest closed, the sibling's `read` stayed blocked (Windows does not reliably wake a blocked `recv` when a cloned handle is shut down), so the `BridgeSlot` was held until the attach side also dropped — up to the 120 s idle timeout. | Concurrency/lifetime, all platforms; exposed on Windows | Both directions share a stop flag and poll their read with a 250 ms timeout (still enforcing the idle timeout); the first direction to end wakes the sibling and the slot is released. The 5 s test now passes in 0.86 s. | `cargo test -p horizon-relay` → all targets passed (13 + 3 + 1 + 1 + 2 + 10 tests); Clippy green |
| 7 | 12 launcher test failures: path-with-spaces, i18n, release URL/signing key | Four distinct causes: (a) the data-location migration tests put fixtures under `%TEMP%`, whose Windows path contains spaces and is rejected by the tool-safety rule; (b) the fork's payload exporter added two user-facing strings that no language table had (French lacked both, and every table lacked the keys); (c) the signed-update test hardcoded the upstream repository URL while production uses `REPO`; (d) `docs/launcher-commands.md` was stale after `payload pack --sources` was added. | Windows test fixture + product data + generated docs | (a) pick a tool-safe temp root (ProgramData fallback), and added a test that unsafe destinations are refused with their contents preserved; (b) added both keys to all 86 tables with real French text and English fallback; (c) assert against `REPO`; (d) regenerated with `HORIZON_WRITE_DOCS=1`. | `cargo test --workspace` in `launcher/` → 667 + 116 + 6 + 10 + 1 + 2 + 2 passed, 0 failed, 10 ignored |

### Stability fixes made from the audit (not test failures)

| Finding | Change | Evidence |
|---|---|---|
| `streaming.rs` poisoned mutexes panicked the tick thread | Every `done`, `queue`, `meshes` and `context` lock recovers with `unwrap_or_else(PoisonError::into_inner)`, matching the rest of the codebase; `try_lock` returns the poisoned guard instead of panicking. | `cargo test -p horizon-client-render --lib` passes; Clippy green |
| Autosave/durability errors discarded (`let _ =`) | Player autosave failures are logged at `error!` with the world root, `finish_player_autosaves` errors propagate through the save path, and the "Saved the game" status only appears after a save that finished its player writes. `Autosaves::drop` drains completed writes and reports a panicked writer. | `cargo test -p horizon-client --lib --bins` → 1185 passed, 0 failed, 291 ignored |
| Failed tadpole spawn ignored | Logged with the frogspawn and spawn positions. | Same run |
| Process-lifetime caches unbounded per root | `BUILTIN`, `RESOURCE_IDS`, `COMMAND_EXPORTS` and `SHARED` section sharing are bounded (8 roots for the registries, 4096 shared sections), keeping evicted `Arc`s valid for their callers; the `'static` block-registry pointer invariant is documented. | Added cache-bound tests in `game/chat.rs`; client tests pass |

The release-signing key replacement and the fork update repository recorded in
[git-history.md](git-history.md) were **not** changed: they are a maintainer integrity decision, not
a stabilization fix. Attribution files were not touched.

## Verification executed

| Check | Command | Result |
|---|---|---|
| Rust formatting | `cargo fmt --all -- --check` | pass |
| Clippy, changed game crates | `cargo clippy -p horizon-client-render -p horizon-client -p horizon-bench --all-targets -- -D warnings` | pass (2m47s) |
| Render crate tests | `cargo test -p horizon-client-render --lib` | 1758 passed, 0 failed, 61 ignored (129s) |
| Client/gameplay tests | `cargo test -p horizon-client --lib --bins` | 1185 passed, 0 failed, 291 ignored (48s) |
| Benchmark crate tests | `cargo test -p horizon-bench --lib --bins` | 17 passed |
| Launcher workspace | `cargo test --workspace` in `launcher/` | 667 + 116 + 6 + 10 + 1 + 2 + 2 passed, 0 failed, 10 ignored |
| Python suite | `python3 -m unittest discover -s tests` | 778 tests, OK, 3 skipped (172 s) |
| Gameplay smoke | `python3 tools/gameplay_bench.py --smoke --repeats 1` | 4/4 scenarios valid |
| New scenarios | `entities_0`, `entities_100`, `redstone_medium`, `world_ops`, `memory_soak`, `overhead` | all valid after their setup fixes |
| Report schema | `horizon-bench validate baseline-qualified.json` | valid (10 scenarios) |
| Benchmark profile build | `python3 tools/cargo_build.py --profile bench` | 18m50s, 8,837 MiB peak compiler working set, 97.4 MiB binary |
| Relay suite | `cargo test -p horizon-relay` | all targets passed (13 + 3 + 1 + 1 + 2 + 10) |
| PR readiness | `python3 tools/pr_ready.py --quick` | **green**: 8306 workspace tests, 778 Python tests, 26 content-root, 783 launcher, rustfmt/clippy, public tree; 30m12s |

`python3 tools/pr_ready.py --quick` reruns the Python suite, rustfmt, Clippy for the workspace and the
touched crates' tests; its result is recorded in the Phase 2 summary. The full `pr_ready` also needs
the prepared vanilla data for the parity harnesses.

## Platform-specific and unsupported checks

- **WSL bash is never used.** The release-asset tests now execute the POSIX shell Git installs. A
  machine with only WSL and no working `/bin/bash` would skip them with the explicit message.
- **GPU tests** return early when no adapter is available. On this machine Vulkan is present and
  the HDR tests ran; on CI's GPU-less Linux runners they are skipped by the test itself.
- **Vanilla parity harnesses** need the prepared `.local/` data (Minecraft 26.3, datagen). This
  checkout has it; `pr_ready` decides which harnesses the change can affect.
- **`release-max`** (Fat LTO, 1 CGU) was not built. It is opt-in for large machines and is not
  required for the production profile; see [build-profiles.md](../build-profiles.md).
- **Byte-for-byte release reproducibility** is not achieved on Windows: a no-op rebuild reuses the
  binary, but a forced relink changes bytes from offset 289 (PE/link metadata) although the inputs
  are identical. See [build-validation.md](build-validation.md).

## PR-readiness result

`python3 tools/pr_ready.py --quick` (30 m 12 s, 141 files changed since `origin/main`):

| Check | Result |
|---|---|
| Scope | 141 files: over the 500-line guidance and mixes CI, game, launcher (this assignment spans both; no PR was opened) |
| Cargo.lock | unchanged |
| Public tree | pass |
| Python tests | 778 passed |
| rustfmt | pass |
| Clippy (workspace, `-D warnings`) | pass |
| Workspace tests | 8,306 passed |
| Doc tests | pass |
| Content-root tests | 26 passed |
| Launcher rustfmt / Clippy / tests | pass / pass / 783 passed |
| Parity | not run (`--quick`); CI's parity job selects the affected harnesses when `.local/` data is available |

The only failure on the first full run was the deterministic `horizon-relay` bridge-slot defect
described above; after the fix the gate is green. The suite's performance tiers are not part of
`pr_ready`: they are `tools/bench_tiers.py` and `.github/workflows/bench.yml`.
