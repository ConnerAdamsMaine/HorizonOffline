# Git history and regression investigation

## History shape

This checkout is a squashed offline fork. It has **three commits** and no upstream remote, so git
bisect of upstream performance work is impossible here.

| Commit | Date | Subject | Scope |
|---|---|---|---|
| `d30b340` | 2026-11-08 | `chore: Removed microsoft login scheme from codebase` | 5,926 files, 2,266,796 insertions: the whole codebase in one commit |
| `6dce07f` | 2026-11-10 | `feat(launcher): offline build plays with a typed name, no sign-in` | 12 files, +198/−32 |
| `eb1e547` | 2026-11-11 | `Cracked it bitches` | 105 files, +5,672/−118 |

The only tag, `v1`, points at `eb1e547`. The only remote is
`github.com/ConnerAdamsMaine/HorizonOffline.git`. Upstream is identifiable from issue links,
`sync-upstream.yml`/`tools/sync_upstream.py`, the `horizon-server` update repository and benchmark
prose (`horizon-rust/horizon`, release `v0.2.97`), but no upstream history or tags are available
locally.

**No fork commit touches rendering, simulation, threading, allocation or world management.** Those
subsystems arrived in the squashed base. Any pre-fork performance regression requires an upstream
remote and history.

## Timeline of fork-local changes

1. `d30b340` — fork point; Microsoft login removed from the launcher.
2. `6dce07f` — offline identity: `HORIZON_OFFLINE_LAUNCHER`, a typed name becomes a stable offline
   UUID, `auth.rs` accepts `user_type == "legacy"`, and the offline session never contacts services.
3. `eb1e547` — launcher payload delivery (`launcher/src/payload.rs`, embedded payload), payload CLI,
   design docs and lang files. It also replaces the release-signing public key in
   `crates/horizon-release-sign/release-keys.txt` and points server self-updates at the fork.

## Suspected regressions

No performance regression can be attributed to a commit in this history: no such commit exists.
Behavioral/integrity findings:

| # | Commit | Subsystem | Mechanism | Status |
|---|---|---|---|---|
| 1 | `eb1e547` | Release integrity | The inlined release-signing public key changed (`MU4oiIQc…` → `jS0T+yMR…`); the file is CODEOWNERS-protected upstream. `payload install --trust-unsigned` was added. | **Confirmed by diff**; security impact not assessed here |
| 2 | `6dce07f` | Auth/session | `user_type` check widened from `msa` to `msa \| legacy`; the game accepts offline sessions it previously refused. | Confirmed, intended, not a regression |
| 3 | `eb1e547` | Server self-update | `REPO` in `crates/horizon-server/src/update.rs` retargeted to the fork; updates pull fork releases signed with key #1. | Confirmed by diff; weakens update-chain trust |
| 4 | `eb1e547` | Launcher startup | Payload verification and extraction on first play adds one-time startup work. | Unverified; no measurement |

## Build-config history

There are no build-config commits in this history. The working-tree change made during this audit
(`Cargo.toml`: release Thin/4 CGUs, `bench`, `release-max`) is uncommitted at the time of writing.
`codegen-units = 1 → 4` can change runtime performance; the companion `bench` profile measures the
new production shape. See [build-profiles](../build-profiles.md) for the measured build.

## Benchmark claims in the tree

All quantitative performance evidence predates the fork and references upstream commits:

- `benchmarks/perf/` holds paired Horizon/vanilla/vanilla+mods runs at render distances 8/16/32. The
  most credible set is Windows 11, Ryzen 7 9800X3D + RTX 5080, release `v0.2.97`, with contended
  games discarded.
- Mac mini M4 Pro runs are explicitly marked "not player numbers" (loaded, offscreen, shrunken
  vanilla window). The 2026-11-04 site runs came from loaded machines (load 28–70) and their docs
  say so.
- Server vs Pumpkin: Horizon wins at ≤20 and ≥60 bots, loses at 25–50 near spawn; 100-player TPS is
  an open known gap in `ROADMAP.md`.
- Every number belongs to upstream main, so none measures this fork's three commits.

The methodology claims checked against `docs/benchmark.md` are stated with their caveats and are not
oversold.

## What would unblock bisection

```sh
git remote add upstream https://github.com/horizon-rust/horizon.git
git fetch upstream --tags
```

Then run the suite and `tools/perf_bench.py` on an upstream checkout at the benchmark commits named
in the reports (`1bd24e4042`, `67dad0d`, `a55b9a2e52`, `d91cab68d`, `v0.2.97`) and on this fork on
idle hardware. Without that, treat all upstream ratios as historical context, not as a statement
about this tree.
