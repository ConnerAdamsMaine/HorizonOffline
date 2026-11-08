//! The offline backend with real installed-process fixtures and fresh, isolated launcher data.
use horizon_launcher::backend::{self, Job, Msg, Settings};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::{mpsc::channel, Mutex, MutexGuard, OnceLock};
use std::time::Duration;

const CLIENT: &str = if cfg!(windows) {
    "horizon-client.exe"
} else {
    "horizon-client"
};
const TAG: &str = "v0.2.1";
static ENV: Mutex<()> = Mutex::new(());

struct Home {
    root: PathBuf,
    _lock: MutexGuard<'static, ()>,
}

impl Home {
    fn new(test: &str) -> Self {
        let lock = ENV.lock().unwrap_or_else(|e| e.into_inner());
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "horizon-local {test}-{}-{nonce}",
            std::process::id()
        ));
        fs::create_dir_all(&root).unwrap();
        for (key, path) in [
            ("HORIZON_HOME", "game"),
            ("HORIZON_LAUNCHER_HOME", "launcher"),
            ("XDG_DATA_HOME", "data"),
            ("XDG_CONFIG_HOME", "config"),
            ("HORIZON_LAUNCHER_TRASH", "trash"),
            ("HORIZON_LAUNCHER_CLIPBOARD", "clipboard"),
            ("HORIZON_LAUNCHER_DESKTOP", "desktop"),
        ] {
            std::env::set_var(key, root.join(path));
        }
        for (key, value) in [
            ("HORIZON_LAUNCHER_NO_SELF_UPDATE", "1"),
            ("HORIZON_NO_AUDIO", "1"),
            ("HORIZON_NO_KEYCHAIN", "1"),
            ("HORIZON_TELEMETRY_URL", "off"),
            ("HORIZON_MSA_CLIENT_ID", ""),
            ("HORIZON_SESSION_FILE", "must-not-be-read.json"),
            ("HORIZON_ACCOUNT_SESSIONS", "must-not-be-read"),
            ("HORIZON_LAUNCHER_EXE", "must-not-be-called"),
        ] {
            std::env::set_var(key, value);
        }
        backend::forget_prepared();
        std::env::remove_var("HORIZON_SERVER_JAR");
        let home = Self { root, _lock: lock };
        home.install(TAG);
        Settings {
            selected: Some(TAG.into()),
            ..Settings::default()
        }
        .save()
        .unwrap();
        home
    }

    fn install(&self, tag: &str) {
        let dir = self.version(tag);
        fs::create_dir_all(&dir).unwrap();
        fs::copy(probe(), dir.join(CLIENT)).unwrap();
        fs::write(dir.join("build.txt"), tag).unwrap();
        fs::write(dir.join(".installed"), "").unwrap();
        let resources = self.resources(tag);
        fs::create_dir_all(&resources).unwrap();
        fs::write(resources.join("horizon-resources.json"), "{}").unwrap();
    }

    fn version(&self, tag: &str) -> PathBuf {
        self.root.join("launcher/versions").join(tag)
    }

    fn resources(&self, tag: &str) -> PathBuf {
        self.version(tag).join(".local/horizon-client/26.3")
    }

    fn local_inputs(&self) -> PathBuf {
        use sha1::{Digest, Sha1};
        let game = self.root.join("local-minecraft");
        let version = game.join("versions/9.9");
        fs::create_dir_all(&version).unwrap();
        let client = b"local preparation test input, not a game";
        let hash = |bytes: &[u8]| format!("{:x}", Sha1::digest(bytes));
        let manifest = br#"{"id":"9.9","libraries":[]}"#;
        fs::write(version.join("9.9.jar"), client).unwrap();
        fs::write(version.join("9.9.json"), manifest).unwrap();
        fs::write(
            self.version(TAG).join("research-lock.json"),
            serde_json::json!({
                "minecraft": {"version":"9.9", "java_major":25,
                    "manifest_sha1":hash(manifest), "client_sha1":hash(client),
                    "server_sha1":"not-a-real-server"}
            })
            .to_string(),
        )
        .unwrap();
        game
    }
}

impl Drop for Home {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

fn probe() -> &'static Path {
    static PROBE: OnceLock<PathBuf> = OnceLock::new();
    PROBE.get_or_init(|| {
        let root = std::env::temp_dir().join(format!("horizon-local-probe-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let executable = root.join(CLIENT);
        let source =
            Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/support/local_client_probe.rs");
        let output = horizon_launcher::process::command("rustc")
            .arg(source)
            .arg("-o")
            .arg(&executable)
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        executable
    })
}

fn monitored(cmd: Command) -> (Vec<String>, Result<(), String>) {
    let (tx, rx) = channel();
    let running = backend::spawn(Job::Client, cmd, tx).unwrap();
    let mut lines = Vec::new();
    loop {
        match rx.recv_timeout(Duration::from_secs(30)) {
            Ok(Msg::Line(Job::Client, line)) => lines.push(line),
            Ok(Msg::Exit(Job::Client, result)) => return (lines, result),
            Ok(_) => panic!("unexpected job/message"),
            Err(error) => {
                running.kill();
                panic!("game-process fixture did not exit: {error}");
            }
        }
    }
}

#[test]
fn local_names_use_the_games_rule_and_invalid_names_never_construct_a_command() {
    let _home = Home::new("names");
    for name in [
        "Alex",
        "Alex_2",
        "A",
        "AB",
        "0123456789abcdef",
        "Alex-2",
        "!~",
    ] {
        assert!(backend::local_client(TAG, name).is_ok(), "{name:?}");
    }
    for name in [
        "",
        " ",
        "two words",
        "0123456789abcdefg",
        "Alex\n",
        "A\0B",
        "A\u{7f}",
        "été",
        "玩家",
    ] {
        let error = backend::local_client(TAG, name).unwrap_err();
        assert!(error.contains("player name"), "{error}");
    }
}

#[test]
fn the_name_survives_settings_reload_and_can_change_for_the_next_run() {
    let home = Home::new("settings");
    let mut settings = Settings::load();
    for name in ["Alex", "Steve_2"] {
        settings.local_player_name = name.into();
        settings.save().unwrap();
        settings = Settings::load();
        assert_eq!(settings.local_player_name, name);
        assert_eq!(settings.selected.as_deref(), Some(TAG));
    }
    let json: serde_json::Value =
        serde_json::from_slice(&fs::read(home.root.join("launcher/settings.json")).unwrap())
            .unwrap();
    assert_eq!(json["local_player_name"], "Steve_2");
    assert!(!home.root.join("launcher/accounts.json").exists());
    assert!(!home.root.join("launcher/account-secrets.json").exists());
}

#[test]
fn local_launch_uses_the_selected_installed_binary_and_only_resources_and_name() {
    let home = Home::new("command");
    home.install("v0.2.2");
    // A signed-in public profile cannot change this start, and no owner/token is available.
    let accounts = br#"{"accounts":[{"name":"Other","uuid":"069a79f444e94726a5befca90e38aaf5"}],"selected":"069a79f444e94726a5befca90e38aaf5"}"#;
    fs::write(home.root.join("launcher/accounts.json"), accounts).unwrap();
    let tag = backend::resolve_version(None).unwrap();
    assert_eq!(tag, TAG, "the selected older build, not the newest");
    let mut settings = Settings::load();
    settings.game_args = "--session-file bad.json --session-stdin --name Other".into();
    settings.save().unwrap();
    let cmd = backend::local_client(&tag, "Alex").unwrap();
    let version = home.version(TAG);
    let expected = if cfg!(target_os = "macos") {
        version.join("Horizon.app/Contents/MacOS").join(CLIENT)
    } else {
        version.join(CLIENT)
    };
    assert_eq!(Path::new(cmd.get_program()), expected);
    assert_eq!(
        cmd.get_current_dir(),
        Some(home.root.join("game").as_path())
    );
    let resources = home.resources(TAG);
    let args = cmd.get_args().collect::<Vec<_>>();
    assert_eq!(args.len(), 4);
    assert_eq!(args[0], "--resources");
    // Windows accepts both separators; compare the path, not its display spelling.
    assert_eq!(Path::new(args[1]), resources);
    assert_eq!(args[2], "--name");
    assert_eq!(args[3], "Alex");
    for key in [
        "HORIZON_SESSION_FILE",
        "HORIZON_ACCOUNT_SESSIONS",
        "HORIZON_LAUNCHER_EXE",
    ] {
        assert_eq!(
            cmd.get_envs().find(|(k, _)| *k == key).map(|(_, v)| v),
            Some(None)
        );
    }
    let (lines, exited) = monitored(cmd);
    assert!(exited.is_ok(), "{exited:?}");
    assert!(lines.contains(&format!("build={TAG}")), "{lines:?}");
    assert!(lines.contains(&"arg=Alex".into()));
    assert!(lines.contains(&"fixture stderr".into()));
    for key in [
        "HORIZON_SESSION_FILE",
        "HORIZON_ACCOUNT_SESSIONS",
        "HORIZON_LAUNCHER_EXE",
    ] {
        assert!(lines.contains(&format!("{key}=false")), "{lines:?}");
    }
    assert_eq!(
        fs::read(home.root.join("launcher/accounts.json")).unwrap(),
        accounts
    );
    assert!(!home.root.join("game/sessions").exists());
    assert!(!home.root.join("launcher/account-secrets.json").exists());
    assert!(!home.root.join("launcher/minecraft").exists());
}

#[test]
fn local_asset_diagnostics_reach_the_callers_console_before_the_game_starts() {
    let home = Home::new("asset-log");
    // Exercise the missing-lock diagnostic on every host, including CI with no Minecraft
    // install. This empty test store contains no Mojang files.
    let minecraft = home.root.join("empty-minecraft-store");
    fs::create_dir_all(&minecraft).unwrap();
    let mut settings = Settings::load();
    settings.minecraft_dir = Some(minecraft);
    settings.save().unwrap();
    let lines = Mutex::new(Vec::new());
    let cmd = backend::local_client_with_log(TAG, "Alex", &|line| {
        lines.lock().unwrap().push(line);
    })
    .unwrap();
    // The fixture has prepared base resources but no research-lock.json for copying extras.
    // That failure is observable in the caller's log, and does not prevent the process starting.
    let logged = lines.lock().unwrap();
    assert!(
        logged
            .iter()
            .any(|line| line.contains("research-lock.json")),
        "{logged:?}"
    );
    drop(logged);
    let expected = if cfg!(target_os = "macos") {
        home.version(TAG)
            .join("Horizon.app/Contents/MacOS")
            .join(CLIENT)
    } else {
        home.version(TAG).join(CLIENT)
    };
    assert_eq!(Path::new(cmd.get_program()), expected);
    let (_, exited) = monitored(cmd);
    assert!(exited.is_ok());
}

#[test]
fn missing_or_interrupted_preparation_is_refused_even_after_a_cached_ready_answer() {
    let home = Home::new("resources");
    assert!(backend::is_prepared(TAG));
    let manifest = home.resources(TAG).join("horizon-resources.json");
    for contents in [None, Some(""), Some("not json")] {
        if let Some(contents) = contents {
            fs::write(&manifest, contents).unwrap();
        } else {
            fs::remove_file(&manifest).unwrap();
        }
        let error = backend::local_client(TAG, "Alex").unwrap_err();
        assert!(error.contains("local Minecraft installation"), "{error}");
        assert!(
            error
                .replace('\\', "/")
                .contains(&home.resources(TAG).display().to_string().replace('\\', "/")),
            "{error}"
        );
    }
    fs::write(&manifest, "{}").unwrap();
    fs::write(home.resources(TAG).join("blocks.json"), "").unwrap();
    assert!(backend::local_client(TAG, "Alex").is_err());
}

#[test]
fn an_uninstalled_build_cannot_be_selected_for_local_play() {
    let _home = Home::new("uninstalled");
    assert!(backend::local_client("v0.2.99", "Alex")
        .unwrap_err()
        .contains("not installed"));
}

#[test]
fn game_startup_failures_and_nonzero_exits_use_the_existing_process_monitor() {
    let home = Home::new("failures");
    let cmd = backend::local_client(TAG, "Alex").unwrap();
    // A missing executable after preflight is still reported by the real spawn path.
    fs::remove_file(home.version(TAG).join(CLIENT)).unwrap();
    let (tx, _rx) = channel();
    let error = backend::spawn(Job::Client, cmd, tx)
        .err()
        .expect("spawn must fail");
    assert!(error.contains("Could not"), "{error}");
    home.install(TAG);
    let (lines, exited) = monitored(backend::local_client(TAG, "Fail").unwrap());
    assert!(exited.unwrap_err().contains("Exited with"));
    assert!(lines.contains(&"fixture stderr".into()));
}

#[test]
fn offline_preparation_reports_missing_local_inputs_without_accounts_or_downloads() {
    let home = Home::new("local-preparation");
    let minecraft = home.local_inputs();
    for missing in [None, Some(home.root.join("missing server.jar"))] {
        if let Some(path) = missing {
            std::env::set_var("HORIZON_SERVER_JAR", path);
        }
        let error = backend::preparer(TAG, &minecraft, backend::MinecraftFrom::Local, &|_| {})
            .err()
            .expect("no server jar must stop preparation");
        assert!(error.contains("HORIZON_SERVER_JAR"), "{error}");
        assert!(error.contains("9.9"), "{error}");
    }
    fs::remove_file(minecraft.join("versions/9.9/9.9.jar")).unwrap();
    for from in [
        backend::MinecraftFrom::Local,
        backend::MinecraftFrom::LocalSetup,
    ] {
        let error = backend::preparer(TAG, &minecraft, from, &|_| {})
            .err()
            .expect("no client jar must stop preparation");
        assert!(error.contains("no Minecraft 9.9 client jar"), "{error}");
    }
    assert!(!home.root.join("launcher/account-secrets.json").exists());
    assert!(!home.root.join("launcher/accounts.json").exists());
    assert!(!home.root.join("launcher/minecraft").exists());
    assert!(!home.root.join("launcher/server-jars").exists());
}

#[test]
fn offline_preparation_cannot_fetch_a_missing_pinned_manifest() {
    let home = Home::new("local-manifest");
    let minecraft = home.local_inputs();
    fs::remove_file(minecraft.join("versions/9.9/9.9.json")).unwrap();
    let lines = Mutex::new(Vec::new());
    for from in [
        backend::MinecraftFrom::Local,
        backend::MinecraftFrom::LocalSetup,
    ] {
        let error = backend::preparer(TAG, &minecraft, from, &|line| {
            lines.lock().unwrap().push(line);
        })
        .err()
        .expect("missing metadata must not be downloaded");
        assert!(error.contains("local Minecraft version JSON"), "{error}");
    }
    assert!(lines
        .lock()
        .unwrap()
        .iter()
        .any(|line| line.contains("Using Minecraft 9.9")));
    assert!(!home.root.join("launcher/account-secrets.json").exists());
}

#[test]
fn offline_extra_arguments_preserve_game_options_but_refuse_identity_and_sessions() {
    let home = Home::new("extra-args");
    let mut settings = Settings::load();
    for arguments in [
        "--session-file bad.json",
        "--session-stdin",
        "--name Other",
        "--session-file=bad.json",
    ] {
        settings.game_args = arguments.into();
        settings.save().unwrap();
        let mut cmd = backend::local_client(TAG, "Alex").unwrap();
        assert!(backend::append_offline_game_args(&mut cmd).is_err());
        assert_eq!(cmd.get_args().count(), 4);
    }
    settings.game_args = "--width 800 --creative".into();
    settings.save().unwrap();
    let mut cmd = backend::local_client(TAG, "Alex").unwrap();
    let mut instance = horizon_launcher::instances::selected();
    instance.kind = horizon_launcher::instances::Kind::Own;
    instance.home = home.root.join("another instance");
    horizon_launcher::instances::apply(&mut cmd, &instance).unwrap();
    backend::append_offline_game_args(&mut cmd).unwrap();
    // Instance variables cannot reintroduce inherited session inputs.
    cmd.env("HORIZON_SESSION_FILE", "bad.json");
    backend::strip_session_env(&mut cmd);
    let (lines, exit) = monitored(cmd);
    assert!(exit.is_ok());
    assert!(lines.contains(&"arg=Alex".into()));
    assert!(lines.contains(&"arg=--creative".into()));
    assert!(lines.contains(&format!("cwd={}", instance.home.display())));
    assert!(lines.contains(&"HORIZON_SESSION_FILE=false".into()));
}
