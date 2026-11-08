use super::*;

const SHA1: &str = "a9993e364706816aba3e25717850c26c9cd0d89d"; // SHA-1 of abc.

struct Fixture {
    root: PathBuf,
    manifest: PathBuf,
    candidate: PathBuf,
    cache: PathBuf,
}

impl Fixture {
    fn new(name: &str) -> Self {
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "horizon-prerequisites-{name}-{}-{nonce}",
            std::process::id()
        ));
        fs::create_dir_all(&root).unwrap();
        let manifest = root.join("version.json");
        fs::write(
            &manifest,
            serde_json::json!({"downloads":{"server":{
                "url":"https://piston-data.mojang.com/test-server.jar", "sha1":SHA1
            }}})
            .to_string(),
        )
        .unwrap();
        Self {
            candidate: root.join("user-picked.jar"),
            cache: root.join("cache/server.jar"),
            root,
            manifest,
        }
    }

    fn setup(&self, fetch: sources::Fetch) -> Result<PathBuf, String> {
        setup_server_jar(
            "fixture",
            &self.manifest,
            &self.candidate,
            &self.cache,
            fetch,
            &|_| {},
        )
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

#[test]
fn setup_downloads_and_verifies_the_public_jar_before_caching_it() {
    let fixture = Fixture::new("download");
    let path = fixture
        .setup(&|url| {
            assert_eq!(url, "https://piston-data.mojang.com/test-server.jar");
            Ok(b"abc".to_vec())
        })
        .unwrap();
    assert_eq!(path, fixture.cache);
    assert_eq!(fs::read(path).unwrap(), b"abc");
    assert!(!fixture.candidate.exists());
}

#[test]
fn a_valid_local_jar_is_reused_without_a_download() {
    let fixture = Fixture::new("local");
    fs::write(&fixture.candidate, b"abc").unwrap();
    assert_eq!(
        fixture.setup(&|_| panic!("unexpected download")).unwrap(),
        fixture.candidate
    );
    assert!(!fixture.cache.exists());
}

#[test]
fn setup_preserves_a_user_picked_jar_and_replaces_only_its_own_bad_cache() {
    let fixture = Fixture::new("bad-cache");
    fs::write(&fixture.candidate, b"keep the user's file").unwrap();
    fs::create_dir_all(fixture.cache.parent().unwrap()).unwrap();
    fs::write(&fixture.cache, b"interrupted cache").unwrap();
    assert_eq!(
        fixture.setup(&|_| Ok(b"abc".to_vec())).unwrap(),
        fixture.cache
    );
    assert_eq!(fs::read(&fixture.cache).unwrap(), b"abc");
    assert_eq!(
        fs::read(&fixture.candidate).unwrap(),
        b"keep the user's file"
    );
    assert_eq!(
        fixture.setup(&|_| panic!("unexpected download")).unwrap(),
        fixture.cache
    );
}

#[test]
fn a_bad_download_cannot_replace_any_local_jar() {
    let fixture = Fixture::new("checksum");
    fs::write(&fixture.candidate, b"user file").unwrap();
    fs::create_dir_all(fixture.cache.parent().unwrap()).unwrap();
    fs::write(&fixture.cache, b"old cache").unwrap();
    let error = fixture
        .setup(&|_| Ok(b"corrupt download".to_vec()))
        .unwrap_err();
    assert!(error.contains("not the one Horizon pins"), "{error}");
    assert_eq!(fs::read(&fixture.candidate).unwrap(), b"user file");
    assert_eq!(fs::read(&fixture.cache).unwrap(), b"old cache");
}

#[test]
fn setup_obtains_and_runs_java_when_no_compatible_runtime_is_installed() {
    use sha1::{Digest, Sha1};
    let fixture = Fixture::new("java-download");
    let probe = fixture
        .root
        .join(format!("java-probe{}", std::env::consts::EXE_SUFFIX));
    let source = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../crates/horizon-prepare/tests/support/java_probe.rs");
    let output = crate::process::command("rustc")
        .arg(source)
        .arg("-o")
        .arg(&probe)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let executable = fs::read(&probe).unwrap();
    let digest = |bytes: &[u8]| format!("{:x}", Sha1::digest(bytes));
    // Keep native executable paths below Windows' process-launch path limit.
    let component = format!("test-java-{}", std::process::id());
    let java = format!("bin/java{}", std::env::consts::EXE_SUFFIX);
    let runtime_manifest = serde_json::json!({"files":{
        java.clone():{"type":"file","executable":true,"downloads":{"raw":{
            "url":"https://fixture/java", "sha1":digest(&executable), "size":executable.len()}}},
        "bin/java.version":{"type":"file","downloads":{"raw":{
            "url":"https://fixture/version", "sha1":digest(b"255.0.1"), "size":7}}}
    }})
    .to_string()
    .into_bytes();
    let index = serde_json::json!({mojang::java_platform().unwrap():{component.clone():[{
        "manifest":{"url":"https://fixture/manifest", "sha1":digest(&runtime_manifest)},
        "version":{"name":"255.0.1"}
    }]}})
    .to_string()
    .into_bytes();
    fs::write(
        &fixture.manifest,
        serde_json::json!({"javaVersion":{"component":component}}).to_string(),
    )
    .unwrap();
    let fetch = |url: &str| {
        Ok(match url {
            "https://fixture/java" => executable.clone(),
            "https://fixture/version" => b"255.0.1".to_vec(),
            "https://fixture/manifest" => runtime_manifest.clone(),
            _ => index.clone(),
        })
    };
    // Deliberately above any installed Java version, so this tests the download path on all hosts.
    assert!(
        java_with_fetch(255, false, &[], &fixture.manifest, &|_| {}, true, &|_| {
            panic!("strict local mode must not download")
        })
        .is_err()
    );
    let home = java_with_fetch(255, false, &[], &fixture.manifest, &|_| {}, false, &fetch).unwrap();
    let output = crate::process::command(home.join(&java))
        .arg("-version")
        .output()
        .unwrap();
    assert!(output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("255.0.1"));
    let component_root = data_dir().join("minecraft/runtime").join(component);
    fs::remove_dir_all(component_root).unwrap();
}
