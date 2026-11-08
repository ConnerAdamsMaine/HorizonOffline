# Free Horizon RustMC

**An offline-play fork of Horizon for Minecraft: Java Edition 26.3.**

Open the normal launcher, enter a player name, and click **Play**. The fork keeps Horizon's existing Home interface, game installation, resource preparation, instance folders, Console and crash handling, with Microsoft login removed from normal Horizon Play.

[Download Releases](https://github.com/lightningblade-1234/Free-Horizon-RustMC/releases) · [First-time setup](launcher/FORK-SETUP.md) · [Build workflow](https://github.com/lightningblade-1234/Free-Horizon-RustMC/actions/workflows/offline-launcher.yml)

## What this fork changes

- Offline Play from the existing **Home** screen.
- An editable player name remembered between launches.
- No Microsoft credential renewal, ownership gate or account-session handoff in normal Horizon Play.
- Embedded Windows shaders, so the built launcher can run after build caches are removed.
- A one-command Windows source setup helper.
- GitHub Actions builds the Windows launcher and existing installer for this fork's Releases.

**Minecraft JARs, assets and prepared game data are never distributed in this repository or its Releases.** Preparation uses the user's own locally obtained Minecraft installation. Releases contain only the compiled launcher and license/setup notices.

## Download and run — Windows x64

1. Open [Releases](https://github.com/lightningblade-1234/Free-Horizon-RustMC/releases/latest).
2. Download **`horizon-launcher-setup.exe`** to install, or **`horizon-launcher.exe`** to run directly. A ZIP and SHA-256 checksums are also provided.
3. Open **Home**, enter your **Offline name**, and press **Play**.
4. Choose **Singleplayer** in the game to create or open a world.

Running the released launcher needs **no Rust, Visual Studio, source checkout or Microsoft login**. The launcher installs/selects a Horizon game build and prepares the required local resources. Use **Versions** to choose a build if needed.

First-time runtime setup is built into the launcher: after its startup game install, it reuses local Java or downloads the required managed Java runtime, obtains a checksum-verified public server JAR in your local cache, and runs the existing preparer. No PowerShell script or repository folder is needed for the release executable. Home stays open with progress/errors in the Console; a game starts only after you enter a valid name and click Play.

If the first release is still building, check the [build workflow](https://github.com/lightningblade-1234/Free-Horizon-RustMC/actions/workflows/offline-launcher.yml). Downloadable files appear after the build and checks succeed.

## Clone and set up with one command

For users who want to build the launcher themselves:

```powershell
git clone https://github.com/lightningblade-1234/Free-Horizon-RustMC.git
Set-Location Free-Horizon-RustMC
powershell -ExecutionPolicy Bypass -File .\tools\setup_launcher.ps1
```

The developer helper:

1. Reuses installed build tools, or installs missing Rust/C++/Windows SDK prerequisites through **winget**.
2. Selects **Rust 1.95.0** and low-cache build settings.
3. Builds the launcher into **`dist\horizon-launcher.exe`**.
4. Installs a Horizon game build using the existing launcher if none is selected.
5. Reuses/installs Java 25, obtains the checksum-verified public server JAR in your local cache, and prepares from your own Minecraft files.
6. Opens the normal Home screen. Already prepared installations are reused.

Windows installers may require elevation or a restart; rerun the command afterward. If winget is missing, install Microsoft's **App Installer** first. The helper does not download Minecraft client files.

For another Minecraft folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\setup_launcher.ps1 -MinecraftDir 'D:\your\minecraft'
```

`-BuildOnly` builds just the launcher. `-NoLaunch` completes setup without opening the window. Compiled outputs are gitignored; source code stays in the repository and executable downloads belong in Releases.

## Local files needed for first preparation

- An existing **Minecraft 26.3** installation with its client JAR, version JSON, libraries and assets. The usual Windows location is `%APPDATA%\.minecraft`.
- **Java 25** for preparation. A Minecraft-managed runtime or a local JDK is reused; the launcher obtains a managed runtime if needed.
- The genuine **26.3 server JAR**, used to export server-side game data needed by single player. It is a preparation input; ordinary Play runs in Rust.

Both the released launcher and source setup helper handle the server JAR download and checksum check. An existing verified local JAR can also be reused. Its pinned SHA-1 is `33680f5f2ac32864d6d7cf5e56a705fdb3e05f4c`.

Minecraft client files, version metadata and assets must come from your local installation; automatic setup does not authenticate or download a missing client installation. Missing inputs appear as errors in Home; use the Minecraft folder chooser or provide the requested file, then try Play again. Preparation progress and game output are available in the **Console**.

## Names and multiplayer

Names must contain **1–16 printable ASCII characters**, without spaces or control characters. The launcher remembers the name. Keep the same spelling and capitalization to keep the same offline UUID.

This identity supports **single-player, LAN and offline-mode servers**. Online-mode servers require genuine account authentication.

## Updating

- **Released launcher:** download a newer release from this fork. Fork Releases keep the upstream launcher self-updater disabled.
- **Source checkout:** run `git pull --ff-only` on `main`, then repeat the setup command.
- **Game builds:** use the normal launcher's version picker and update controls.

The **Offline launcher release** workflow builds on relevant pushes to this fork's `main`. It can also be started from **Actions → Offline launcher release → Run workflow**.

**Sync upstream** checks `horizon-rust/horizon`'s `main`, waits until 15 minutes after its run started, then starts its next run automatically. GitHub's cron schedule remains a recovery trigger because scheduled starts can be delayed or skipped. Changes to the sync workflow/tool also start the poller. It merges and pushes new commits only when Git reports no conflicts. Conflicts leave the fork unchanged, fail the run and list the files to resolve; the next check still runs. It never force-pushes. Runner queues can delay checks.

To start/restart the recurring poller, run **Sync upstream** from Actions with **keep_running** enabled. Disable the workflow to stop it. For a single check, clear **keep_running**; an existing recurring run keeps its own schedule.

After a successful sync, it explicitly starts **checks**, plus a launcher release build when launcher/dependency inputs changed. These checks catch compilation/behavior failures that a clean Git merge cannot detect. Pull the updated fork locally and rerun source setup to rebuild your own executable.

This fork keeps **Sync upstream**, **checks** (Python tooling, formatting, lint and Rust tests) and **Offline launcher release** enabled. Inherited upstream service/release automations are disabled here because their private runners, signing keys and project services are not part of this fork. Parity harnesses remain available for local development; those disabled workflows do not constitute a vanilla parity run.

## Files and troubleshooting

| What | Default Windows location |
| --- | --- |
| Launcher settings and remembered name | `%APPDATA%\horizon-launcher\settings.json` |
| Installed builds and prepared resources | `%APPDATA%\horizon-launcher\versions\<tag>\` |
| Server JAR cache | `%APPDATA%\horizon-launcher\server-jars\26.3.jar` |
| Default game folder | `%APPDATA%\horizon\` |
| Source-built launcher | `dist\horizon-launcher.exe` in the checkout |

Each instance can have its own game folder. Home's **Folder** control opens the selected one. Custom data locations and `HORIZON_LAUNCHER_HOME` / `HORIZON_HOME` overrides change these defaults.

- **Missing resources:** provide the local file reported by the launcher and run Play or Prepare again. Inputs must match the selected build's Minecraft version.
- **Extra arguments rejected:** remove `--name`, `--session-file` and `--session-stdin`; Home supplies the offline identity.
- **Source rebuild fails:** finish any prerequisite installation/restart and rerun the helper. Close a running copy of the executable being rebuilt if Windows reports it is locked.
- **Older launcher fails after cache cleanup:** rebuild current `main` or download a newer fork Release with embedded shaders.

## License and attribution

Based on [Horizon](https://github.com/horizon-rust/horizon). Original project and fork code use the [MIT license](LICENSE); dependencies retain their own licenses ([third-party notices](THIRD_PARTY_NOTICES.md)).

Unofficial and not affiliated with or endorsed by Mojang or Microsoft. Minecraft is their trademark; their game files are not included in this fork.
