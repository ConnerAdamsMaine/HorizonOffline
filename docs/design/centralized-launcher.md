# One-file launcher with a per-user game payload

Status: implemented for Model M2 (embedded payload, two processes) on Windows; Linux uses the same code path but
still needs a hand test in a `noexec` folder. macOS keeps working through `versions/<tag>/` and `game_app.rs` and
is not in scope. The launcher tests, the CLI commands and the offline Release workflow below are the evidence.
Whoever extends this should read [native-client.md](../native-client.md), [launcher-commands.md](../launcher-commands.md)
and [FORK-SETUP.md](../../launcher/FORK-SETUP.md) first.

What is built: `launcher/src/payload.rs` (manifest, key, verification, atomic install, prune, selection, version
stub, embedded install, packaging), payload-aware program/preparer/slot selection in `launcher/src/backend.rs`,
`payload list|verify|prune|install|pack` in `launcher/src/cli.rs`, `HORIZON_PAYLOAD_ZIP` embedding in
`launcher/build.rs`, and the pack/install/verify/embed steps in `.github/workflows/offline-launcher.yml`.

Deliberately not built yet: a signature check over `payload.json`. Embedded payloads are trusted by provenance;
an archive passed to `payload install` is refused without `--trust-unsigned`, the same escape hatch
`import-build` uses. Retention is manual: `payload prune` keeps the selected payload and removes the rest.

The goal, in the owner's words: **one file to download and run, with everything else the launcher needs kept in
one per-user folder.** The launcher is the program a player gets; the game is a payload it owns and starts.

This page fixes the vocabulary, the on-disk layout, the manifest every tool must agree on, and the order to build
it in, so the work can be done without re-deriving the analysis. Section [Model M1](#model-m1-in-process-payload)
records why the original idea (`game.dll` / `game.so` loaded by the launcher) is the expensive way to get there.

## Vocabulary

| Term | Meaning |
| --- | --- |
| **Launcher** | `horizon-launcher`, the program a player downloads. Owns accounts, versions, preparation, and starting the game. |
| **Payload** | The game program and the files beside it (`horizon-client`, `horizon-ctl`, `horizon-prepare`, `horizon-server`), installed into a per-user folder rather than into `versions/<tag>/`. |
| **Payload root** | The one folder the payload lives in: `payload/` under the launcher's data folder (below). |
| **Payload key** | Content identity of an installed payload: `sha256(manifest-as-shipped)` first 16 hex characters. Two builds with the same key are the same bytes. |
| **Manifest** | `payload.json`: what the payload contains, its hashes, its entry program, and the game version it serves. Normative form in [The manifest](#the-manifest-normative). |
| **Slot** | The Windows runtime copy under `<data_dir>/run/<home key>/game/` (`launcher/src/windows_runtime.rs`), which keeps the executable path stable per game home so the Windows Firewall identity does not change. |
| **Data folder** | `backend::data_dir()` (`launcher/src/backend.rs:920`): `HORIZON_LAUNCHER_HOME` when set, else the `launcher` root of `location.json` (`launcher/src/data_location.rs:19`), else `dirs::data_dir()/horizon-launcher`. |

The owner's proposed folders map onto this without new code: set `HORIZON_LAUNCHER_HOME` to them.

- Windows: `%LOCALAPPDATA%\HorizonOL` (his spelling) → everything, including the payload root.
- Linux: `$HOME/.HorizonOL` → the same.

Without that variable the data folder is `%APPDATA%\horizon-launcher` on Windows (Roaming; see
[open questions](#open-questions)) and `~/.local/share/horizon-launcher` on Linux.

## Where the payload lives

```
<data folder>/
  versions/<tag>/                 # today's installs, unchanged, still the source of an imported build
  payload/<payload key>/          # an installed payload: horzion payload, extracted and verified
    payload.json                  # the manifest, byte-for-byte as shipped
    horizon-client.exe            # entry program from the manifest (horizon-client on Linux)
    horizon-ctl.exe
    horizon-prepare.exe
    horizon-server.exe
  payload/.partial-<pid>/         # extraction in progress; never started from, removed on next start
  run/<home key>/game/            # Windows slot, unchanged (see Slots and firewall identity)
  embedded/payload.zip            # nothing: the payload is compiled into the launcher (Model M2)
```

Rules, all of them testable:

1. **Paths are relative to the data folder.** Never hardcode `%LOCALAPPDATA%` or `$HOME`; the data folder is
   relocatable through `HORIZON_LAUNCHER_HOME` and `location.json`, and CI and the harnesses relocate it (see
   [AGENTS.md](../../AGENTS.md), "Keep your runs away from real player data").
2. **A payload is installed whole or not at all.** Extract into `payload/.partial-<pid>/`, verify every file
   against the manifest, write `payload.json` last, then rename the directory to `payload/<key>/`. A rename that
   fails because the target exists means another launcher won the race: verify the existing one and delete the
   partial.
3. **Read-only after install.** Nothing writes inside `payload/<key>/`; a new build is a new key and a new folder.
   Deleting one is only allowed when no lock is held on it (rule 5).
4. **Manifest first, program second.** A payload is chosen by its manifest, never by a file that happens to be
   named `horizon-client`; `mod_api_level` (`launcher/src/backend.rs` `mod_api_level`) must read the mark from the
   program the manifest names, because reading the wrong file silently downgrades every native mod check.
5. **One launcher may replace a payload only when no game runs from it.** Take the same lock discipline the
   Windows slot already uses: an exclusive advisory lock file per payload directory, held for the launcher's
   lifetime, plus (Windows) the open handle on the image that keeps the exe from being replaced while it runs.
   Do not delete a payload whose lock is held; leave it and prune it at the next start.
6. **No symbolic links inside a payload, ever.** Reject entries whose file type is a link or (Windows) whose
   attributes carry the reparse point bit, as `windows_runtime::plain_directory` already does.
7. **Executable bits on Unix.** `horizon-client`, `horizon-ctl`, `horizon-prepare` and `horizon-server` are
   `0755`; every other file is `0644`. The folder is `0755`.

### Platform notes

**Windows.** `%APPDATA%` (Roaming) is where `dirs::data_dir()` points, so a 98 MB payload there follows the player
between domain machines. That is wrong for binaries: prefer `dirs::data_local_dir()` for the payload root, or make
the packaged build default the data folder to `%LOCALAPPDATA%\HorizonOL`. Either change is a one-line default in
`backend::data_dir()`; both must keep `HORIZON_LAUNCHER_HOME` and `location.json` winning.

Windows also refuses to replace or delete a running image, which is why today's design copies the program into a
slot. See [Slots and firewall identity](#slots-and-firewall-identity).

**Linux.** The payload must be executable from where it is. On a `noexec` mount the start must fail with a
translated, actionable message naming the folder (never a bare `errno`), not silently fall back to `versions/`.
`~/.HorizonOL` is acceptable only because the owner asked for it; `$XDG_DATA_HOME` (default
`~/.local/share`) is the convention, and `horizon-launcher` is already the folder name there.

## Model M1: in-process payload

The owner's original proposal: `game.dll` on Windows, `game.so` on Linux, loaded by the launcher, which calls
into it instead of spawning a second process.

It is achievable, and the mechanical part is small, but three facts make it a bad trade today.

**1. One process gets one GUI event loop.** The game creates its loop and owns the calling thread until the
window closes: `EventLoop::new()?.run_app(&mut app)` (`crates/horizon-client/src/game.rs:18033`). winit 0.30
allows one event loop per process; a second `EventLoop::new` is a recreation error. GPUI (`gpui-fast`) owns the
main thread and its own message pump. So either

- the launcher closes its window, calls into the payload and never comes back — same user experience as Model M2
  minus crash isolation, minus the "the game exited with code N" recovery, minus stdout/stderr capture; or
- the game is rewritten to draw into a GPUI view: `game/window_handler.rs` (`impl ApplicationHandler`), the surface
  creation in `gfx.rs`, and the winit → `horizon-client-input` event mapping. That is the client's whole platform
  layer, and it splits `--dedicated` out of the binary that is also the dedicated server.

**2. Two Rust runtimes in one process.** `launcher/` is its own Cargo workspace with its own lockfile and pins
(`gpui-fast` pins `wgpu 30.0.1`, its own `ureq`, …). A `cdylib` exposes no stable ABI: one process then has two
allocators, two panic runtimes, two `log` globals and two wgpu instances. It works only if *no Rust type crosses
the boundary*, both halves are built by the same rustc, and the launcher stops being a separate workspace. That
last part is structural: `launcher/Cargo.toml`'s `[workspace]` exists to keep those pins apart.

**3. Memory goes up, not down.** Two processes share one executable image's clean pages. One process holds both
images (64.5 MB launcher + 97.7 MB game) and, if both link wgpu, two copies of it. This contradicts the build
constraint this work started from ("no memory usage blow ups").

Nothing in the tree loads Rust code dynamically today: `libloading` appears only under `third_party/`, and native
mods are statically linked into a game the launcher rebuilds (`docs/native-mods.md`, horizon-mixins). This would be
the first runtime-dylib consumer.

If it is still wanted later, [Appendix: the C ABI of Model M1](#appendix-the-c-abi-of-model-m1) has the surface and
the rules. Do not start there.

## Model M2: embedded payload, two processes (recommended)

The launcher carries the payload inside itself, installs it into the payload root on first play, verifies it, and
spawns it exactly as it spawns a version today.

- **One file to download.** Build the launcher with the payload embedded: `include_bytes!(env!("HORIZON_PAYLOAD_ZIP"))`,
  where the path comes from the build script. Measured in this checkout: `horizon-client.exe` is 97,730,048 bytes
  and deflates to 35,243,960 (2.8×), so the launcher grows from 64,550,400 to roughly 100 MB. Everything else
  (the manifest, the three tools) is already inside that.
- **First play extracts once.** `~1 s` for ~100 MB from local disk; nothing stays resident afterwards, because the
  zip bytes live in the mapped image and are read, not copied.
- **Nothing else changes.** Crash isolation, the game's own console/log handling, GPU and audio device lifetimes,
  the Launch API (`docs/api/launch.md`), and `--dedicated` all stay as they are.
- **The extraction is a normal install.** Same verification, same atomic rename, same lock as a downloaded payload;
  embedding only changes where the bytes come from.

Where the launcher's code changes, precisely:

| What | Where | Change |
| --- | --- | --- |
| Payload root, key, manifest type | new `launcher/src/payload.rs` | `payload_root()`, `payload_key()`, `Manifest` (serde, `deny_unknown_fields`, like `data_location::Roots`) |
| Extract and verify | `launcher/src/payload.rs` | zip entries → `payload/.partial-<pid>/`, sha256 per file, rename, prune partials |
| Embedded bytes | `launcher/build.rs` or `launcher/src/embedded.rs` | `include_bytes!` behind `option_env!("HORIZON_PAYLOAD_ZIP")`; without it, download the payload like any release asset |
| Choose the program | `backend::client_program` (`launcher/src/backend.rs:3142`, one call site at `3063`) | payload entry when one is installed, else `version_dir(tag)/CLIENT` |
| Dedicated server program | `backend::server_command` (`launcher/src/backend.rs:3152`, uses `version_dir(tag).join(CLIENT)` directly) | same choice; keep this call site in sync or the server starts a stale build |
| Mod API level | `backend::mod_api_level` | read the mark from the chosen program, not unconditionally from `version_dir(tag)` |
| Slot source | `windows_runtime::mark(cmd, source)` | pass the payload directory instead of the version directory |
| CLI | `launcher/src/cli.rs` | `payload list`, `payload verify`, `payload prune` (clap derive, like the rest) |
| Strings | `launcher/src/i18n/` | new keys through `tr()` / `trf()` in all 84 `lang/*.json`; `i18n::tests` fails otherwise |

Everything the launcher already does for an installed version — `resolve_version`, `need_prepared`,
`resources(tag)`, `complete_assets_with_log`, `local_client_with_log` — keeps working, because the payload is a
program plus a resources folder, and neither is versioned differently.

## The manifest (normative)

`payload.json`, UTF-8, no BOM, keys in the order below, unknown fields rejected (the launcher's existing serde
style). It is written as shipped and never rewritten by the launcher. The same rules as a machine-readable schema:
[payload.schema.json](payload.schema.json); change the two together.

```json
{
  "schema": 1,
  "key": "3f9c1a5d2b7e4c60",
  "tag": "nightly",
  "game_version": "26.3",
  "mod_api_level": 27,
  "platform": "x86_64-pc-windows-msvc",
  "entry": "horizon-client.exe",
  "files": [
    { "path": "horizon-client.exe",  "sha256": "…", "size": 97730048, "exec": true  },
    { "path": "horizon-ctl.exe",     "sha256": "…", "size": 1481216,  "exec": true  },
    { "path": "horizon-prepare.exe", "sha256": "…", "size": 2391552,  "exec": true  },
    { "path": "horizon-server.exe",  "sha256": "…", "size": 8837632,  "exec": true  }
  ],
  "preparer_output_version": 3
}
```

| Field | Type | Rule |
| --- | --- | --- |
| `schema` | integer | `1`. Bump only for an incompatible change; a reader rejects a higher number and says so. |
| `key` | string | 16 lowercase hex, equal to the first 16 characters of `sha256` of the manifest bytes with `"key"` omitted (canonical form below). |
| `tag` | string | The version tag the payload was built for, e.g. `nightly`. Informational: the folder is named by `key`. |
| `game_version` | string | The Minecraft version, `26.3` today (`horizon_core::version`). A payload for another version must not be installed over this one. |
| `mod_api_level` | integer | The mark the game carries (`horizon_mods::api_level::MARK`); the launcher's `mod_api_level` must agree, and a mismatch is an error, not a warning. |
| `platform` | string | The Rust target triple of the binaries. Refuse any payload whose triple is not this build's (`std::env::consts::ARCH` plus the target's OS and ABI). |
| `entry` | string | Must appear in `files` and must be the game program. |
| `files[].path` | string | Relative, forward slashes, no `..`, no absolute path, no leading `/`, no `:`; unique. |
| `files[].sha256` | string | 64 lowercase hex. |
| `files[].size` | integer | Bytes on disk. |
| `files[].exec` | boolean | Executable bit on Unix; ignored on Windows. |
| `preparer_output_version` | integer | `OUTPUT_VERSION` from `crates/horizon-prepare/src/lib.rs`, which is what decides whether a player's prepared resources still fit. |

**Canonical manifest bytes** for the key: serialize with keys sorted, no whitespace, and `key` removed; the key is
then inserted back as the second field. Implementations must produce identical bytes on both platforms, or the
same payload gets two keys. A unit test pins one manifest's expected key.

**Trust.** The payload is code the launcher will execute, extracted into a user-writable folder. Verify it twice:

1. **Per-file sha256** against the manifest, at extract and before every prune/verify command.
2. **A signature over the manifest**, checked with `horizon-release-sign` (already used for release archives,
   `launcher/src/signed.rs`), before anything is extracted. An unsigned payload is refused unless the launcher was
   started with the existing `--trust-unsigned` escape hatch that `import-build` already offers for local builds.

Never extract an archive entry whose normalized path escapes the partial folder, whatever its name says.

## Slots and firewall identity

Today Windows copies the chosen version's program into `<data_dir>/run/<sha256(game home)>/game/` so that the
executable path for one game home never changes across versions, and the player does not get a new Windows Firewall
prompt every update (`windows_runtime.rs`, `docs/native-client.md`). Two tests pin that behaviour and must keep
passing.

A payload folder keyed by content hash **does** change path between builds, so the slot stays:

- `windows_runtime::mark(cmd, payload_dir)` stages from the payload instead of the version. Same copy, same lock,
  same `source.json`, same deletion protection.
- With `HORIZON_LAUNCHER_HOME` set to a per-user folder, the slot is still keyed by the *game home*, so several
  homes sharing one payload still get their own stable path. Do not key the slot by payload.
- On Linux there is no slot and none is needed: the payload path is stable per key, and a "pin the game to the
  launcher's own executable path" step has no counterpart there.

## Starting the game

Order, for both platforms:

1. Resolve the data folder (`backend::data_dir()`), then `payload_root()`.
2. Choose the payload: the one selected for the version (`Settings::selected`), else the newest key with a valid
   manifest. With none installed, install the embedded one (M2) or say, translated, that no game is installed.
3. Verify the manifest signature, then the entry file's hash and size. A mismatch removes the payload folder and
   reinstalls from the embedded copy; if that fails, the error names the folder and the expected hash.
4. `need_prepared(tag)`: preparation is unchanged and still per version (`resources(tag)`); a payload does not carry
   prepared resources, because they come from the player's own Minecraft install (`docs/launcher-preparation.md`).
5. Build the command exactly as `client_command` does today: `--resources`, `HORIZON_HOME`, `PIPEWIRE_PROPS`,
   `HORIZON_LAUNCHER_EXE` for session renewal, the launcher render env strip, `--name` for an offline start,
   `--dedicated --nogui` for a server.
6. On Windows, mark the payload directory and let `windows_runtime::prepare` stage the slot; spawn the slot's
   program, as today.

Offline starts keep working unchanged: the offline build (`HORIZON_OFFLINE_LAUNCHER=1`,
`.github/workflows/offline-launcher.yml`) has no account row and no Microsoft card, and `Settings::load` forces
`dev_offline`, so a payload adds no sign-in anywhere.

## What must not regress

- `versions/<tag>/` installs, `import-build <path> --trust-unsigned`, `resolve_version`, `.installed` markers.
- The Launch API contract (`crates/horizon-client/src/game/launch_api.rs`, `VERSION`): only a process CLI, unchanged.
- The Windows slot and its two tests in `launcher/src/windows_runtime.rs`.
- `mod_api_level` reading the mark from the file that will actually run.
- The offline fork build and its Release workflow.
- `cargo test` for the launcher workspace (`launcher/` is a separate workspace: `cd launcher && cargo test`).

## Implementation order

| Phase | Work | Done when | State |
| --- | --- | --- | --- |
| P0 | `payload.rs`: root, key, manifest type, canonical bytes, verification of a directory against a manifest. No behaviour change. | Unit tests: key stability, path rejection (`..`, absolute, link, duplicate), hash mismatch, `deny_unknown_fields`, platform mismatch. | Done: eight payload tests pass. |
| P1 | Extract/stage/prune with the atomic rename and the lock; `payload list/verify/prune` in `cli.rs`; `client_program` and `server_command` choose a payload when one is installed; `mod_api_level` follows it. | A payload installed by hand into a scratch `HORIZON_LAUNCHER_HOME` plays the game through the launcher; `payload verify` exits 0; a tampered file fails and is repaired. | Done: the packaged `dist/horizon-system` payload installs and plays; `verify` is used by `prune` and at launch. |
| P2 | Packaging: a build step that zips the four programs plus the manifest, and the launcher embedding it via `HORIZON_PAYLOAD_ZIP`; first play installs it. | A launcher built with no `versions/` and no network installs its payload and starts the game offline. | Done: `payload pack` writes the zip; `build.rs` embeds it; the workflow installs and verifies both the archive and the embedded copy in a fresh home. |
| P3 | Windows slot sources the payload; Linux exec bits and the `noexec` message. | Slot tests still pass; a `noexec` payload folder fails with the translated message instead of a raw error. | Windows done and tested. Linux exec bits are set on extract; the `noexec` hand test is still open. |
| P4 | Docs (`native-client.md`, `launcher-commands.md`, `FORK-SETUP.md`), translations for every new string, release workflow artifacts. | `cd launcher && cargo test`; `cargo fmt --check`; the offline Release workflow builds and packages. | In this change: generated command reference, 46 English fallback keys across every language file, workflow steps. |

Keep each pull request under ~500 lines ([AGENTS.md](../../AGENTS.md)); P1 and P2 are separate pull requests.

## Test plan

Both platforms, in a scratch home as the repository rules require (`mktemp -d`, `HORIZON_HOME`,
`HORIZON_LAUNCHER_HOME`, `HORIZON_LAUNCHER_TRASH`, `HORIZON_LAUNCHER_CLIPBOARD`, `HORIZON_LAUNCHER_DESKTOP`,
`HORIZON_LAUNCHER_NO_SELF_UPDATE=1`, `HORIZON_NO_AUDIO=1`):

- `cd launcher && cargo test` (unit tests, including `windows_runtime::tests` on Windows).
- `horizon-launcher --version`, `payload list`, `payload verify`, `account offline <name>`, `play` — the offline
  flow already verified by hand for this fork.
- Negative: truncated payload, one byte changed, manifest from another `platform`, manifest with a `..` path,
  payload folder replaced by a junction (Windows) or a symlink (Linux) — each must fail closed and say where.
- `python3 tools/launcher_mcp_e2e.py` for the launcher's MCP surface (unchanged but cheap to confirm).
- Linux: the same in a `noexec` tmpfs; and a payload installed under a path containing a space and a non-ASCII
  user name (Windows: `tool_safe` in `backend.rs` lists the MinGW tools that break on those).

## Open questions

1. **Model.** Settled on M2 (embedded payload, two processes). M1 (in-process dylib) stays in the appendix as the
   rejected alternative.
2. **Windows base folder.** Still open: the default remains `%APPDATA%\horizon-launcher` (Roaming). The release
   workflow sets `HORIZON_LAUNCHER_HOME` explicitly; changing the default to `%LOCALAPPDATA%` is a one-line
   follow-up that must keep `HORIZON_LAUNCHER_HOME` and `location.json` winning.
3. **Distribution.** Settled on embedded: `HORIZON_PAYLOAD_ZIP` is compiled into the offline Release launcher, so
   first play needs no network.
4. **Retention.** Settled on explicit pruning: `payload prune` keeps the payload selected for the current version
   (or `--keep`), removes the rest, and leaves a payload a game is running from for the next start.
5. **Name.** Still open: `HorizonOL` is only used in this page as the owner's example; the product name is
   unchanged.
6. **ARM64 and other targets.** Still open: `docs/windows-arm64.md` documents a second Windows target; the
   manifest's `platform` already makes one architecture refuse the other's payload, but the Release workflow still
   builds x64 only.
7. **macOS.** Out of scope here. `version_dir(tag)/Horizon.app` is wrapped by `game_app.rs`; a payload would need
   the same treatment, and winit's main-thread rule makes M1 worse there.

## Appendix: the C ABI of Model M1

Only if M1 is chosen. The payload becomes `crate-type = ["cdylib"]`, built from a new root
(`crates/horizon-client/src/payload_lib.rs`), keeping `main.rs` as the executable.

```c
/* All strings are UTF-8, not NUL-terminated. */
uint32_t horizon_abi_version(void);                      /* 1 */
int32_t  horizon_start(const uint8_t *json, size_t len);  /* JSON config; 0 on success, else an exit code */
int32_t  horizon_stop(void);                              /* asks the game to quit; returns the code it used */
void     horizon_free(uint8_t *ptr, size_t len);          /* frees a buffer horizon_start allocated */
```

Rules, each of which is a bug if broken:

- No Rust type crosses the boundary. The config is JSON, in both directions. The library owns and frees every
  buffer it returns (`horizon_free`), because the two sides have different allocators.
- No panic crosses the boundary: `catch_unwind` inside every export, `panic = "unwind"` for the library.
- Same rustc and same panic strategy as the launcher; otherwise unspecified behaviour. This forces the launcher out
  of its separate workspace or into a lockstep build.
- `entry::main` becomes `entry::run(args: Vec<String>) -> ExitCode`: `std::env::args()` at
  `crates/horizon-client/src/entry.rs:24` and the `std::process::exit` call at `entry.rs:278` cannot stay.
- Logging and the crash handler are process-global; the library must tolerate a logger the launcher installed and
  must not install a process-wide panic hook that takes the launcher down.
- `horizon_start` cannot run a GUI event loop inside the launcher's: see
  [Model M1](#model-m1-in-process-payload). The launcher must exit its window before calling it.

## Measurements (this checkout, 2026-11-10)

| Item | Value |
| --- | --- |
| `horizon-client.exe` | 97,730,048 bytes |
| The same file, deflated | 35,243,960 bytes (2.8×) |
| `horizon-launcher.exe` (static CRT, `--release`, stripped) | 64,550,400 bytes |
| `horizon-ctl.exe` / `horizon-prepare.exe` / `horizon-server.exe` | 1,481,216 / 2,391,552 / 8,837,632 bytes |
| The four game programs plus the launcher, one folder, zipped | 67,964,423 bytes |
| `cargo build --profile fast` for the four programs, warm | 5m 27s |
| `cargo build --manifest-path launcher/Cargo.toml --release` | 3m 13s warm, 8m 12s cold |

Build commands, as verified for this checkout (no LTO, `CARGO_BUILD_JOBS=4` to bound memory):

```sh
export CARGO_BUILD_JOBS=4
cargo build --profile fast \
  -p horizon-client -p horizon-client-lib --bin horizon-client --bin horizon-ctl \
  -p horizon-prepare --bin horizon-prepare -p horizon-server --bin horizon-server

HORIZON_OFFLINE_LAUNCHER=1 HORIZON_LAUNCHER_NO_SELF_UPDATE=1 HORIZON_MSA_CLIENT_ID= \
  CARGO_BUILD_JOBS=4 cargo build --manifest-path launcher/Cargo.toml --release --locked
```

`cargo run -p xtask -- package` is **not** a usable path for this fork: it stops on
`Missing exporters/manifest.json` unless `horizon-prepare compile-exporters` has run and its bundle was copied to
`exporters/`. Add a payload packaging step instead of depending on it.
