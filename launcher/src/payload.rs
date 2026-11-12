//! The game payload (`docs/design/centralized-launcher.md`): one folder the launcher owns and
//! starts, independent of `versions/<tag>/`. A payload is installed whole or not at all, is
//! read-only afterwards, and is chosen by its manifest (`payload.json`), never by a file that
//! happens to be named like the game.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io::{Read, Seek};
use std::path::{Path, PathBuf};

/// The manifest every payload carries, byte for byte as shipped.
pub const MANIFEST: &str = "payload.json";
/// The schema this launcher reads. A higher number is refused with its number named.
pub const SCHEMA: u32 = 1;
/// The entry program's name on this platform.
pub const CLIENT: &str = crate::backend::CLIENT;
/// The Java exporter sources `horizon-prepare` compiles from its root. A payload carries them so
/// a fresh home can prepare from the player's own Minecraft install without a source checkout.
pub const EXPORTER_SOURCES: &str = "mods/horizon/src/test/java";

/// A file the payload holds. `path` is relative, forward-slashed, and unique in the manifest.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PayloadFile {
    pub path: String,
    pub sha256: String,
    pub size: u64,
    pub exec: bool,
}

impl PayloadFile {
    fn path(&self) -> PathBuf {
        PathBuf::from(self.path.replace('/', std::path::MAIN_SEPARATOR_STR))
    }
}

/// `payload.json`: what the payload contains, its hashes, its entry program, and the game
/// version it serves. Normative form: `docs/design/payload.schema.json`.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub schema: u32,
    pub key: String,
    pub tag: String,
    pub game_version: String,
    pub mod_api_level: u32,
    pub platform: String,
    pub entry: String,
    pub files: Vec<PayloadFile>,
    pub preparer_output_version: u32,
}

impl Manifest {
    /// Reads and checks a manifest as shipped. Every field rule in the design page is checked
    /// here, including the content key, the platform, the game version and the file paths.
    pub fn parse(bytes: &[u8]) -> Result<Self, String> {
        let manifest: Self = serde_json::from_slice(bytes).map_err(|e| {
            crate::i18n::trf(
                "The payload manifest is not valid: {error}",
                &[("error", &e.to_string())],
            )
        })?;
        manifest.check()?;
        Ok(manifest)
    }

    /// Checks the fields; hashes are checked against a folder by [`verify_dir`].
    pub fn check(&self) -> Result<(), String> {
        if self.schema != SCHEMA {
            return Err(crate::i18n::trf(
                "The payload manifest is schema {schema}; this launcher reads schema {current}.",
                &[
                    ("schema", &self.schema.to_string()),
                    ("current", &SCHEMA.to_string()),
                ],
            ));
        }
        if self.tag.trim().is_empty() {
            return Err(crate::i18n::tr("The payload manifest names no version.").into());
        }
        if self.game_version != horizon_core::VANILLA_VERSION {
            return Err(crate::i18n::trf(
                "The payload serves Minecraft {version}; this launcher runs {current}.",
                &[
                    ("version", &self.game_version),
                    ("current", horizon_core::VANILLA_VERSION),
                ],
            ));
        }
        if self.platform != platform() {
            return Err(crate::i18n::trf(
                "The payload was built for {platform}, not {current}.",
                &[("platform", &self.platform), ("current", platform())],
            ));
        }
        if !is_hex(&self.key, 16) {
            return Err(crate::i18n::tr(
                "The payload manifest's key is not 16 lowercase hex characters.",
            )
            .into());
        }
        let computed = self.computed_key();
        if self.key != computed {
            return Err(crate::i18n::trf(
                "The payload's key is {key}, but its manifest hashes to {computed}.",
                &[("key", &self.key), ("computed", &computed)],
            ));
        }
        if self.preparer_output_version != horizon_prepare::OUTPUT_VERSION {
            return Err(crate::i18n::trf(
                "The payload prepares with output version {version}; this launcher prepares {current}.",
                &[
                    ("version", &self.preparer_output_version.to_string()),
                    ("current", &horizon_prepare::OUTPUT_VERSION.to_string()),
                ],
            ));
        }
        if self.files.is_empty() {
            return Err(crate::i18n::tr("The payload manifest lists no files.").into());
        }
        let mut paths = BTreeSet::new();
        for file in &self.files {
            check_path(&file.path).map_err(|e| {
                crate::i18n::trf(
                    "The payload path {path} is not allowed: {error}",
                    &[("path", &file.path), ("error", &e)],
                )
            })?;
            if !is_hex(&file.sha256, 64) {
                return Err(crate::i18n::trf(
                    "{path}: its SHA-256 is not 64 lowercase hex characters.",
                    &[("path", &file.path)],
                ));
            }
            if !paths.insert(file.path.as_str()) {
                return Err(crate::i18n::trf(
                    "{path} appears twice in the payload.",
                    &[("path", &file.path)],
                ));
            }
        }
        if !paths.contains(self.entry.as_str()) {
            return Err(crate::i18n::trf(
                "The payload names {entry}, which is not one of its files.",
                &[("entry", &self.entry)],
            ));
        }
        let entry = Path::new(&self.entry)
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or_default();
        let expected = exec_name("horizon-client");
        if entry != expected {
            return Err(crate::i18n::trf(
                "The payload's entry must be the game program ({program}).",
                &[("program", &expected)],
            ));
        }
        Ok(())
    }

    /// The canonical bytes the key covers: keys sorted, no whitespace, `key` omitted.
    pub fn canonical_bytes(&self) -> Vec<u8> {
        let mut out = String::from("{");
        // Sorted order, as `serde_json`'s BTreeMap-backed object would write it.
        out.push_str("\"entry\":");
        push_str(&mut out, &self.entry);
        out.push_str(",\"files\":[");
        for (i, file) in self.files.iter().enumerate() {
            if i > 0 {
                out.push(',');
            }
            out.push_str("{\"exec\":");
            out.push_str(if file.exec { "true" } else { "false" });
            out.push_str(",\"path\":");
            push_str(&mut out, &file.path);
            out.push_str(",\"sha256\":");
            push_str(&mut out, &file.sha256);
            out.push_str(",\"size\":");
            out.push_str(&file.size.to_string());
            out.push('}');
        }
        out.push_str("],\"game_version\":");
        push_str(&mut out, &self.game_version);
        out.push_str(",\"mod_api_level\":");
        out.push_str(&self.mod_api_level.to_string());
        out.push_str(",\"platform\":");
        push_str(&mut out, &self.platform);
        out.push_str(",\"preparer_output_version\":");
        out.push_str(&self.preparer_output_version.to_string());
        out.push_str(",\"schema\":");
        out.push_str(&self.schema.to_string());
        out.push_str(",\"tag\":");
        push_str(&mut out, &self.tag);
        out.push('}');
        out.into_bytes()
    }

    /// The content key: `sha256(canonical bytes)`, first 16 lowercase hex.
    pub fn computed_key(&self) -> String {
        let digest = Sha256::digest(self.canonical_bytes());
        digest[..8].iter().map(|b| format!("{b:02x}")).collect()
    }

    /// Sets `key` to the content hash of everything else. Used by the packaging tool, never by
    /// an installed payload.
    pub fn seal(&mut self) {
        self.key = self.computed_key();
    }

    /// The file the manifest names as the game.
    pub fn entry_file(&self) -> &PayloadFile {
        self.files
            .iter()
            .find(|file| file.path == self.entry)
            .expect("a checked manifest's entry is one of its files")
    }

    /// A manifest with the file list of `files` and a freshly computed key.
    pub fn new(tag: &str, mod_api_level: u32, entry: &str, files: Vec<PayloadFile>) -> Self {
        let mut manifest = Self {
            schema: SCHEMA,
            key: String::new(),
            tag: tag.to_owned(),
            game_version: horizon_core::VANILLA_VERSION.to_owned(),
            mod_api_level,
            platform: platform().to_owned(),
            entry: entry.to_owned(),
            files,
            preparer_output_version: horizon_prepare::OUTPUT_VERSION,
        };
        manifest.seal();
        manifest
    }
}

fn push_str(out: &mut String, value: &str) {
    out.push_str(&serde_json::to_string(value).expect("a string serializes"));
}

fn is_hex(value: &str, len: usize) -> bool {
    value.len() == len
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

/// The program's name on this platform: `horizon-client.exe` on Windows, `horizon-client` here.
pub fn exec_name(stem: &str) -> String {
    #[cfg(windows)]
    return format!("{stem}.exe");
    #[cfg(not(windows))]
    return stem.to_owned();
}

/// The Rust target triple of this build: what the manifest's `platform` must equal.
pub fn platform() -> &'static str {
    #[cfg(all(target_arch = "x86_64", target_os = "windows", target_env = "msvc"))]
    return "x86_64-pc-windows-msvc";
    #[cfg(all(target_arch = "aarch64", target_os = "windows", target_env = "msvc"))]
    return "aarch64-pc-windows-msvc";
    #[cfg(all(target_arch = "x86_64", target_os = "windows", target_env = "gnu"))]
    return "x86_64-pc-windows-gnu";
    #[cfg(all(target_arch = "x86_64", target_os = "linux", target_env = "gnu"))]
    return "x86_64-unknown-linux-gnu";
    #[cfg(all(target_arch = "aarch64", target_os = "linux", target_env = "gnu"))]
    return "aarch64-unknown-linux-gnu";
    #[cfg(all(target_arch = "x86_64", target_os = "macos"))]
    return "x86_64-apple-darwin";
    #[cfg(all(target_arch = "aarch64", target_os = "macos"))]
    return "aarch64-apple-darwin";
    #[cfg(not(any(
        all(target_arch = "x86_64", target_os = "windows", target_env = "msvc"),
        all(target_arch = "aarch64", target_os = "windows", target_env = "msvc"),
        all(target_arch = "x86_64", target_os = "windows", target_env = "gnu"),
        all(target_arch = "x86_64", target_os = "linux", target_env = "gnu"),
        all(target_arch = "aarch64", target_os = "linux", target_env = "gnu"),
        all(target_arch = "x86_64", target_os = "macos"),
        all(target_arch = "aarch64", target_os = "macos"),
    )))]
    return "unknown-unknown-unknown";
}

/// A manifest path: relative, forward slashes, no `..`, absolute prefix, drive or `:`, no
/// empty, `.` or `..` component, and no backslash (which Windows would read as a separator).
fn check_path(path: &str) -> Result<(), String> {
    if path.is_empty() {
        return Err("the path is empty".into());
    }
    if path.contains('\0') {
        return Err("the path contains a NUL".into());
    }
    if path.starts_with('/') || path.contains(':') || path.contains('\\') {
        return Err("the path is absolute or uses a backslash".into());
    }
    for component in path.split('/') {
        if component.is_empty() || component == "." || component == ".." {
            return Err("the path has an empty, `.` or `..` component".into());
        }
        #[cfg(windows)]
        if component.ends_with([' ', '.']) || is_reserved(component) {
            return Err("the path is not a plain Windows file name".into());
        }
    }
    Ok(())
}

#[cfg(windows)]
fn is_reserved(component: &str) -> bool {
    const NAMES: [&str; 22] = [
        "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
        "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    ];
    let stem = component.split('.').next().unwrap_or_default();
    NAMES.iter().any(|name| stem.eq_ignore_ascii_case(name))
}

/// The payload root: `<data folder>/payload`.
pub fn root() -> PathBuf {
    crate::backend::data_dir().join("payload")
}

/// The directories under the root that hold a readable manifest, newest first by modification
/// time. The folder name is not trusted: the manifest inside decides its key.
pub fn installed() -> Vec<(String, Manifest, PathBuf)> {
    installed_in(&root())
}

fn installed_in(root: &Path) -> Vec<(String, Manifest, PathBuf)> {
    let mut found: Vec<(String, Manifest, PathBuf, std::time::SystemTime)> = fs::read_dir(root)
        .into_iter()
        .flatten()
        .flatten()
        .filter(|entry| {
            entry
                .file_name()
                .to_string_lossy()
                .bytes()
                .next()
                .is_some_and(|b| b.is_ascii_hexdigit())
        })
        .filter_map(|entry| {
            let dir = entry.path();
            let bytes = fs::read(dir.join(MANIFEST)).ok()?;
            let manifest = Manifest::parse(&bytes).ok()?;
            let modified = fs::metadata(&dir).and_then(|m| m.modified()).ok()?;
            Some((manifest.key.clone(), manifest, dir, modified))
        })
        .collect();
    found.sort_by_key(|entry| std::cmp::Reverse(entry.3));
    found
        .into_iter()
        .map(|(key, manifest, dir, _)| (key, manifest, dir))
        .collect()
}

/// The payload to run: the one whose `tag` is selected, else the newest installed one.
pub fn choose(root: &Path, selected: Option<&str>) -> Option<(Manifest, PathBuf)> {
    let all = installed_in(root);
    let selected = selected.and_then(|tag| {
        all.iter()
            .find(|(_, manifest, _)| manifest.tag == tag)
            .map(|(_, manifest, dir)| (manifest.clone(), dir.clone()))
    });
    selected.or_else(|| {
        all.into_iter()
            .next()
            .map(|(_, manifest, dir)| (manifest, dir))
    })
}

/// The program a payload names, if one is installed.
pub fn program_for(tag: &str) -> Option<PathBuf> {
    let (manifest, dir) = choose(&root(), Some(tag))?;
    if manifest.tag != tag {
        return None;
    }
    Some(dir.join(manifest.entry_file().path()))
}

/// Whether `tag` is served by an installed payload.
pub fn provides(tag: &str) -> bool {
    program_for(tag).is_some_and(|program| program.is_file())
}

/// Checks every file of `dir` against the manifest inside it. Returns the manifest.
pub fn verify_dir(dir: &Path) -> Result<Manifest, String> {
    let bytes = fs::read(dir.join(MANIFEST)).map_err(|e| {
        crate::i18n::trf(
            "The payload at {folder} has no readable manifest: {error}",
            &[
                ("folder", &dir.display().to_string()),
                ("error", &e.to_string()),
            ],
        )
    })?;
    let manifest = Manifest::parse(&bytes)?;
    let wanted: BTreeMap<&str, &PayloadFile> = manifest
        .files
        .iter()
        .map(|file| (file.path.as_str(), file))
        .collect();
    let mut found = BTreeSet::new();
    walk(dir, dir, &mut found)?;
    for path in &found {
        let path_text = path.to_string_lossy().replace('\\', "/");
        if path_text == MANIFEST {
            continue;
        }
        if !wanted.contains_key(path_text.as_str()) {
            return Err(crate::i18n::trf(
                "The payload holds {path}, which its manifest does not list.",
                &[("path", &path_text)],
            ));
        }
    }
    for file in &manifest.files {
        let path = dir.join(file.path());
        let meta = fs::metadata(&path).map_err(|e| damage(&file.path, &e.to_string()))?;
        if meta.len() != file.size {
            return Err(damage(
                &file.path,
                &crate::i18n::trf(
                    "its size is {size}, not {expected}",
                    &[
                        ("size", &meta.len().to_string()),
                        ("expected", &file.size.to_string()),
                    ],
                ),
            ));
        }
        let actual = sha256_file(&path).map_err(|e| damage(&file.path, &e.to_string()))?;
        if actual != file.sha256 {
            return Err(damage(
                &file.path,
                crate::i18n::tr("its SHA-256 does not match"),
            ));
        }
    }
    let program = dir.join(manifest.entry_file().path());
    let level = horizon_mods::api_level::read_mark(&fs::read(&program).unwrap_or_default());
    if level != Some(manifest.mod_api_level) {
        return Err(crate::i18n::trf(
            "The payload's game program serves mod API level {found}; its manifest says {expected}.",
            &[
                ("found", &level.unwrap_or(0).to_string()),
                ("expected", &manifest.mod_api_level.to_string()),
            ],
        ));
    }
    Ok(manifest)
}

fn damage(path: &str, why: &str) -> String {
    crate::i18n::trf(
        "The payload is damaged: {path} {why}. Reinstall it.",
        &[("path", path), ("why", why)],
    )
}

fn walk(dir: &Path, at: &Path, files: &mut BTreeSet<PathBuf>) -> Result<(), String> {
    for entry in fs::read_dir(at).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        let meta = fs::symlink_metadata(&path).map_err(|e| e.to_string())?;
        if meta.file_type().is_symlink() || is_reparse(&meta) {
            return Err(crate::i18n::trf(
                "The payload holds a link at {path}; links are never allowed.",
                &[("path", &path.display().to_string())],
            ));
        }
        if meta.is_dir() {
            walk(dir, &path, files)?;
        } else if meta.is_file() {
            files.insert(
                path.strip_prefix(dir)
                    .map_err(|e| e.to_string())?
                    .to_path_buf(),
            );
        } else {
            return Err(crate::i18n::trf(
                "The payload holds {path}, which is not a file or folder.",
                &[("path", &path.display().to_string())],
            ));
        }
    }
    Ok(())
}

#[cfg(windows)]
fn is_reparse(meta: &fs::Metadata) -> bool {
    use std::os::windows::fs::MetadataExt;
    meta.file_attributes() & 0x400 != 0
}

#[cfg(not(windows))]
fn is_reparse(_meta: &fs::Metadata) -> bool {
    false
}

fn sha256_file(path: &Path) -> std::io::Result<String> {
    let mut file = fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(hasher
        .finalize()
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect())
}

/// Installs the payload in `archive` under `root`, whole or not at all. The archive's
/// `payload.json` decides; nothing is written outside the partial folder until every file
/// matches. Returns the installed manifest and folder.
pub fn install<R: Read + Seek>(root: &Path, archive: R) -> Result<(Manifest, PathBuf), String> {
    let mut zip = zip::ZipArchive::new(archive).map_err(|e| {
        crate::i18n::trf(
            "The payload archive is not readable: {error}",
            &[("error", &e.to_string())],
        )
    })?;
    let bytes = read_entry(&mut zip, MANIFEST)?;
    let manifest = Manifest::parse(&bytes)?;
    let final_dir = root.join(&manifest.key);
    if final_dir.join(MANIFEST).is_file() {
        if verify_dir(&final_dir).is_ok() {
            return Ok((manifest, final_dir));
        }
        // A damaged install is replaced whole, not patched file by file.
        remove_dir(&final_dir)?;
    }
    fs::create_dir_all(root).map_err(|e| e.to_string())?;
    remove_partials(root);
    let partial = root.join(format!(".partial-{}", std::process::id()));
    remove_dir(&partial)?;
    fs::create_dir_all(&partial).map_err(|e| e.to_string())?;
    let result = extract(&mut zip, &manifest, &bytes, &partial).and_then(|()| {
        verify_dir(&partial)?;
        match fs::rename(&partial, &final_dir) {
            Ok(()) => Ok((manifest.clone(), final_dir.clone())),
            // Another launcher won the race: use its copy if it is whole.
            Err(_) if final_dir.join(MANIFEST).is_file() => {
                remove_dir(&partial)?;
                verify_dir(&final_dir)?;
                Ok((manifest.clone(), final_dir.clone()))
            }
            Err(e) => Err(e.to_string()),
        }
    });
    if result.is_err() {
        let _ = remove_dir(&partial);
    }
    result
}

fn read_entry<R: Read + Seek>(zip: &mut zip::ZipArchive<R>, name: &str) -> Result<Vec<u8>, String> {
    let mut entry = zip
        .by_name(name)
        .map_err(|_| crate::i18n::trf("The payload archive has no {name}.", &[("name", name)]))?;
    if !entry.is_file() || entry.size() > 1 << 20 {
        return Err(crate::i18n::trf(
            "The payload archive's {name} is not a small file.",
            &[("name", name)],
        ));
    }
    let mut bytes = Vec::new();
    entry.read_to_end(&mut bytes).map_err(|e| e.to_string())?;
    Ok(bytes)
}

fn extract<R: Read + Seek>(
    zip: &mut zip::ZipArchive<R>,
    manifest: &Manifest,
    manifest_bytes: &[u8],
    dir: &Path,
) -> Result<(), String> {
    let wanted: BTreeSet<&str> = manifest
        .files
        .iter()
        .map(|file| file.path.as_str())
        .collect();
    let mut seen = BTreeSet::new();
    for i in 0..zip.len() {
        let mut entry = zip.by_index(i).map_err(|e| e.to_string())?;
        if entry.is_dir() {
            continue;
        }
        reject_link(&entry)?;
        let path = entry
            .enclosed_name()
            .ok_or_else(|| {
                crate::i18n::trf(
                    "The payload archive entry {name} escapes its folder.",
                    &[(
                        "name",
                        &entry.name().map(|n| n.into_owned()).unwrap_or_default(),
                    )],
                )
            })?
            .to_string_lossy()
            .replace('\\', "/");
        if path == MANIFEST {
            continue;
        }
        if !wanted.contains(path.as_str()) {
            return Err(crate::i18n::trf(
                "The payload archive holds {path}, which its manifest does not list.",
                &[("path", &path)],
            ));
        }
        if !seen.insert(path.clone()) {
            return Err(crate::i18n::trf(
                "{path} appears twice in the payload archive.",
                &[("path", &path)],
            ));
        }
        let to = dir.join(Path::new(&path));
        if let Some(parent) = to.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let mut file = fs::File::create(&to).map_err(|e| e.to_string())?;
        std::io::copy(&mut entry, &mut file).map_err(|e| e.to_string())?;
        drop(file);
        set_exec(
            &to,
            manifest
                .files
                .iter()
                .find(|f| f.path == path)
                .is_some_and(|f| f.exec),
        )?;
    }
    let missing: Vec<_> = wanted
        .iter()
        .filter(|path| !seen.contains(**path))
        .collect();
    if !missing.is_empty() {
        return Err(crate::i18n::trf(
            "The payload archive is missing {path}.",
            &[("path", missing[0])],
        ));
    }
    let manifest_path = dir.join(MANIFEST);
    fs::write(&manifest_path, manifest_bytes).map_err(|e| e.to_string())?;
    set_exec(&manifest_path, false)?;
    Ok(())
}

fn reject_link<R: Read + Seek>(entry: &zip::read::ZipFile<'_, R>) -> Result<(), String> {
    // Unix mode's file-type bits: a symbolic link is 0o120000.
    if entry
        .unix_mode()
        .is_some_and(|mode| mode & 0o170000 == 0o120000)
    {
        return Err(crate::i18n::trf(
            "The payload archive entry {name} is a link; links are never allowed.",
            &[(
                "name",
                &entry.name().map(|n| n.into_owned()).unwrap_or_default(),
            )],
        ));
    }
    Ok(())
}

#[cfg(unix)]
fn set_exec(path: &Path, exec: bool) -> Result<(), String> {
    use std::os::unix::fs::PermissionsExt;
    let mode = if exec { 0o755 } else { 0o644 };
    fs::set_permissions(path, fs::Permissions::from_mode(mode)).map_err(|e| e.to_string())
}

#[cfg(not(unix))]
fn set_exec(_path: &Path, _exec: bool) -> Result<(), String> {
    Ok(())
}

fn remove_partials(root: &Path) {
    for entry in fs::read_dir(root).into_iter().flatten().flatten() {
        if entry.file_name().to_string_lossy().starts_with(".partial-") {
            let _ = remove_dir(&entry.path());
        }
    }
}

fn remove_dir(path: &Path) -> Result<(), String> {
    match fs::remove_dir_all(path) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}

/// Installs the payload embedded in this launcher, if it has one and none is installed.
pub fn install_embedded() -> Result<Option<(Manifest, PathBuf)>, String> {
    let Some(bytes) = embedded() else {
        return Ok(None);
    };
    if let Some((manifest, dir)) = choose(&root(), None) {
        if verify_dir(&dir).is_ok() {
            return Ok(Some((manifest, dir)));
        }
    }
    install(&root(), std::io::Cursor::new(bytes)).map(Some)
}

/// The payload archive compiled into the launcher by `HORIZON_PAYLOAD_ZIP`. An empty archive
/// (the build script writes one when no payload was given) means no payload is embedded.
pub fn embedded() -> Option<&'static [u8]> {
    let bytes = include_bytes!(concat!(env!("OUT_DIR"), "/payload.zip"));
    (bytes.len() > 22).then_some(&bytes[..])
}

/// Removes payload folders that are not whole or that `keep` does not name. A payload a game
/// runs from is left for the next start. Returns the keys removed.
pub fn prune(root: &Path, keep: Option<&str>) -> Vec<String> {
    remove_partials(root);
    let keep = keep.map(str::to_owned);
    let mut removed = Vec::new();
    for entry in fs::read_dir(root).into_iter().flatten().flatten() {
        let name = entry.file_name().to_string_lossy().into_owned();
        if keep.as_deref() == Some(name.as_str()) {
            continue;
        }
        let path = entry.path();
        if verify_dir(&path).is_ok() {
            if in_use(&path) {
                continue;
            }
            if fs::remove_dir_all(&path).is_ok() {
                removed.push(name);
            }
        } else if fs::remove_dir_all(&path).is_ok() {
            removed.push(name);
        }
    }
    removed
}

fn in_use(dir: &Path) -> bool {
    #[cfg(windows)]
    return crate::windows_runtime::in_use(dir);
    #[cfg(not(windows))]
    {
        let _ = dir;
        false
    }
}

/// Makes a version folder the rest of the launcher can play: the marker `installed()` reads,
/// the payload's `research-lock.json` when it carries one, and the Java exporters its preparer
/// compiles. The payload itself is untouched.
pub fn ensure_version(manifest: &Manifest) -> Result<String, String> {
    ensure_version_in(&root(), &crate::backend::version_dir(&manifest.tag), manifest)?;
    Ok(manifest.tag.clone())
}

fn ensure_version_in(payload_root: &Path, dir: &Path, manifest: &Manifest) -> Result<(), String> {
    let payload = payload_root.join(&manifest.key);
    fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    if !dir.join(".installed").is_file() {
        fs::write(dir.join(".installed"), "").map_err(|e| e.to_string())?;
    }
    let lock = dir.join("research-lock.json");
    if !lock.is_file() {
        let from_payload = payload.join("research-lock.json");
        if from_payload.is_file() {
            fs::copy(from_payload, lock).map_err(|e| e.to_string())?;
        }
    }
    let sources: Vec<&PayloadFile> = manifest
        .files
        .iter()
        .filter(|file| is_exporter_source(&file.path))
        .collect();
    if !sources.is_empty() {
        // The preparer hashes and compiles this tree, so it must be exactly this payload's
        // sources, not a mix left by an older one.
        let marker = dir.join(".payload-key");
        let current = fs::read_to_string(&marker).ok();
        if current.as_deref() != Some(manifest.key.as_str()) {
            let tree = dir.join(EXPORTER_SOURCES);
            remove_dir(&tree)?;
            for file in sources {
                let to = dir.join(Path::new(&file.path));
                if let Some(parent) = to.parent() {
                    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
                }
                fs::copy(payload.join(file.path()), &to).map_err(|e| e.to_string())?;
            }
            fs::write(&marker, &manifest.key).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

/// Whether a payload path is one of the Java sources `horizon-prepare` compiles.
fn is_exporter_source(path: &str) -> bool {
    path.strip_prefix(EXPORTER_SOURCES)
        .is_some_and(|rest| rest.starts_with('/'))
}


/// A payload file's bytes by manifest path, for the packaging tool.
pub fn read_file(dir: &Path, path: &str) -> Result<Vec<u8>, String> {
    fs::read(dir.join(Path::new(path))).map_err(|e| e.to_string())
}

/// The payload's `horizon-prepare`, when one is installed for `tag`: preparation still runs the
/// build's own preparer, never an older version's.
pub fn preparer_for(tag: &str) -> Option<PathBuf> {
    let (manifest, dir) = choose(&root(), Some(tag))?;
    if manifest.tag != tag {
        return None;
    }
    let name = exec_name("horizon-prepare");
    manifest
        .files
        .iter()
        .find(|file| file.path == name)
        .map(|file| dir.join(file.path()))
        .filter(|path| path.is_file())
}

/// Makes sure the payload this launch needs is installed and whole, and that its version stub
/// exists. The embedded payload is installed on first use; a damaged one is replaced from it.
pub fn prepare_for_launch() -> Result<Option<(Manifest, PathBuf)>, String> {
    let root = root();
    let selected = crate::backend::Settings::load().selected;
    if let Some((_, dir)) = choose(&root, selected.as_deref()) {
        match verify_dir(&dir) {
            Ok(manifest) => {
                ensure_version(&manifest)?;
                return Ok(Some((manifest, dir)));
            }
            // A damaged install is replaced whole from the embedded copy, not patched.
            Err(_) => remove_dir(&dir)?,
        }
    }
    let Some((manifest, dir)) = install_embedded()? else {
        return Ok(None);
    };
    ensure_version(&manifest)?;
    Ok(Some((manifest, dir)))
}

/// Builds `out` from the programs in `input`, the exporter sources under `sources`, and the
/// manifest that describes them: what the release workflow embeds in the launcher and
/// `payload install` reads.
pub fn pack(input: &Path, sources: &Path, tag: &str, out: &Path) -> Result<Manifest, String> {
    let names = [
        exec_name("horizon-client"),
        exec_name("horizon-ctl"),
        exec_name("horizon-prepare"),
        exec_name("horizon-server"),
        "research-lock.json".to_owned(),
    ];
    let mut files = Vec::new();
    for name in names {
        let path = input.join(&name);
        if !path.is_file() {
            if name == "research-lock.json" {
                continue;
            }
            return Err(crate::i18n::trf(
                "The payload folder has no {name}.",
                &[("name", &name)],
            ));
        }
        let bytes = fs::read(&path).map_err(|e| e.to_string())?;
        files.push(PayloadFile {
            path: name.clone(),
            sha256: Sha256::digest(&bytes)
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect(),
            size: bytes.len() as u64,
            exec: name != "research-lock.json",
        });
    }
    // The preparer compiles these Java exporters from its root; a fresh home has no checkout.
    let tree = sources.join(EXPORTER_SOURCES);
    let mut java = BTreeSet::new();
    walk(&tree, &tree, &mut java).map_err(|e| {
        crate::i18n::trf(
            "The exporter sources at {folder} are not readable: {error}",
            &[
                ("folder", &tree.display().to_string()),
                ("error", &e),
            ],
        )
    })?;
    java.retain(|path| path.extension().is_some_and(|e| e == "java"));
    if java.is_empty() {
        return Err(crate::i18n::trf(
            "The payload has no exporter sources under {folder}.",
            &[("folder", &tree.display().to_string())],
        ));
    }
    for path in java {
        let relative = path.to_string_lossy().replace('\\', "/");
        let manifest_path = format!("{EXPORTER_SOURCES}/{relative}");
        let bytes = fs::read(tree.join(&path)).map_err(|e| e.to_string())?;
        files.push(PayloadFile {
            path: manifest_path,
            sha256: Sha256::digest(&bytes)
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect(),
            size: bytes.len() as u64,
            exec: false,
        });
    }
    files.sort_by(|a, b| a.path.cmp(&b.path));
    let entry = exec_name("horizon-client");
    let program = fs::read(input.join(&entry)).map_err(|e| e.to_string())?;
    let level = horizon_mods::api_level::read_mark(&program).ok_or_else(|| {
        crate::i18n::trf(
            "{program} carries no mod API mark, so it is not a Horizon game program.",
            &[("program", &entry)],
        )
    })?;
    let manifest = Manifest::new(tag, level, &entry, files);
    manifest.check()?;
    if let Some(parent) = out.parent().filter(|p| !p.as_os_str().is_empty()) {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let partial = out.with_extension("partial");
    let _ = fs::remove_file(&partial);
    let write = || -> Result<(), String> {
        let file = fs::File::create(&partial).map_err(|e| e.to_string())?;
        let mut zip = zip::ZipWriter::new(file);
        let exec = zip::write::SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Deflated)
            .unix_permissions(0o755);
        let data = zip::write::SimpleFileOptions::default()
            .compression_method(zip::CompressionMethod::Deflated)
            .unix_permissions(0o644);
        for file in &manifest.files {
            let options = if file.exec { exec } else { data };
            zip.start_file(&file.path, options)
                .map_err(|e| e.to_string())?;
            let from = if is_exporter_source(&file.path) {
                sources.join(file.path())
            } else {
                input.join(file.path())
            };
            let bytes = fs::read(from).map_err(|e| e.to_string())?;
            std::io::Write::write_all(&mut zip, &bytes).map_err(|e| e.to_string())?;
        }
        zip.start_file(MANIFEST, data).map_err(|e| e.to_string())?;
        let bytes = serde_json::to_vec(&manifest).map_err(|e| e.to_string())?;
        std::io::Write::write_all(&mut zip, &bytes).map_err(|e| e.to_string())?;
        zip.finish().map_err(|e| e.to_string())?;
        fs::rename(&partial, out).map_err(|e| e.to_string())
    };
    if let Err(e) = write() {
        let _ = fs::remove_file(&partial);
        return Err(e);
    }
    Ok(manifest)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn file(path: &str, bytes: &[u8], exec: bool) -> PayloadFile {
        PayloadFile {
            path: path.to_owned(),
            sha256: Sha256::digest(bytes)
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect(),
            size: bytes.len() as u64,
            exec,
        }
    }

    fn make_manifest(files: Vec<PayloadFile>) -> Manifest {
        let entry = files[0].path.clone();
        Manifest::new("nightly", horizon_mods::api_level::LEVEL, &entry, files)
    }

    fn marked(level: u32) -> Vec<u8> {
        let mut program = vec![0u8; 32];
        let mut mark = *b"horizon-mod-api-level:0000;";
        let digits = format!("{level:04}");
        mark[22..26].copy_from_slice(digits.as_bytes());
        program.extend_from_slice(&mark);
        program
    }

    #[test]
    fn the_key_pins_the_canonical_manifest() {
        let program = marked(horizon_mods::api_level::LEVEL);
        let mut manifest = make_manifest(vec![file("horizon-client.exe", &program, true)]);
        manifest.seal();
        // Independent value: sha256 of the exact canonical bytes below, first 16 hex.
        let canonical = format!(
            "{{\"entry\":\"horizon-client.exe\",\"files\":[{{\"exec\":true,\"path\":\"horizon-client.exe\",\"sha256\":\"{}\",\"size\":{}}}],\"game_version\":\"26.3\",\"mod_api_level\":{},\"platform\":\"{}\",\"preparer_output_version\":{},\"schema\":1,\"tag\":\"nightly\"}}",
            manifest.files[0].sha256,
            manifest.files[0].size,
            manifest.mod_api_level,
            platform(),
            horizon_prepare::OUTPUT_VERSION,
        );
        let expected: String = Sha256::digest(canonical.as_bytes())[..8]
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect();
        assert_eq!(manifest.key, expected);
        assert_eq!(manifest.computed_key(), expected);
    }

    #[test]
    fn unknown_fields_are_rejected() {
        let program = marked(horizon_mods::api_level::LEVEL);
        let manifest = make_manifest(vec![file("horizon-client.exe", &program, true)]);
        let text = serde_json::to_string(&manifest).unwrap();
        let with_extra = text.replacen('{', "{\"surprise\":true,", 1);
        assert!(Manifest::parse(with_extra.as_bytes())
            .unwrap_err()
            .contains("surprise"));
    }

    #[test]
    fn paths_must_stay_inside_the_payload() {
        for path in ["../evil", "/abs", "C:/abs", "a\\b", "a//b", "./a", "a/../b"] {
            assert!(check_path(path).is_err(), "{path}");
        }
        for path in [
            "horizon-client.exe",
            "lib/native.dll",
            "native-data/mod/table",
        ] {
            assert!(check_path(path).is_ok(), "{path}");
        }
    }

    #[test]
    fn duplicate_paths_are_rejected() {
        let program = marked(horizon_mods::api_level::LEVEL);
        let mut manifest = make_manifest(vec![
            file("horizon-client.exe", &program, true),
            file("horizon-client.exe", &program, true),
        ]);
        manifest.seal();
        assert!(manifest.check().unwrap_err().contains("twice"));
    }

    #[test]
    fn another_platform_or_game_version_is_refused() {
        let program = marked(horizon_mods::api_level::LEVEL);
        let mut manifest = make_manifest(vec![file("horizon-client.exe", &program, true)]);
        manifest.platform = "aarch64-unknown-linux-gnu".into();
        manifest.seal();
        assert!(manifest.check().unwrap_err().contains("built for"));
        let mut manifest = make_manifest(vec![file("horizon-client.exe", &program, true)]);
        manifest.game_version = "1.21".into();
        manifest.seal();
        assert!(manifest.check().unwrap_err().contains("serves Minecraft"));
    }

    #[test]
    fn a_changed_file_fails_verification() {
        let program = marked(horizon_mods::api_level::LEVEL);
        let manifest = make_manifest(vec![
            file("horizon-client.exe", &program, true),
            file("horizon-ctl.exe", b"tool", true),
        ]);
        let dir = temp("changed");
        fs::create_dir_all(&dir).unwrap();
        let mut zip_bytes = Vec::new();
        {
            let mut zip = zip::ZipWriter::new(std::io::Cursor::new(&mut zip_bytes));
            let options = zip::write::SimpleFileOptions::default();
            zip.start_file("horizon-client.exe", options).unwrap();
            zip.write_all(&program).unwrap();
            zip.start_file("horizon-ctl.exe", options).unwrap();
            zip.write_all(b"tool").unwrap();
            zip.start_file(MANIFEST, options).unwrap();
            zip.write_all(&serde_json::to_vec(&manifest).unwrap())
                .unwrap();
            zip.finish().unwrap();
        }
        let (_, dir) = install(&dir, std::io::Cursor::new(&zip_bytes)).unwrap();
        assert_eq!(verify_dir(&dir).unwrap().key, manifest.key);
        fs::write(dir.join("horizon-ctl.exe"), b"evil").unwrap();
        assert!(verify_dir(&dir).is_err());
        // Reinstalling repairs the damaged folder.
        install(dir.parent().unwrap(), std::io::Cursor::new(&zip_bytes)).unwrap();
        assert!(verify_dir(&dir).is_ok());
        let _ = fs::remove_dir_all(dir.parent().unwrap());
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn an_archive_entry_outside_the_payload_is_refused() {
        let program = marked(horizon_mods::api_level::LEVEL);
        let manifest = make_manifest(vec![file("horizon-client.exe", &program, true)]);
        let root = temp("escape");
        fs::create_dir_all(&root).unwrap();
        let mut zip_bytes = Vec::new();
        {
            let mut zip = zip::ZipWriter::new(std::io::Cursor::new(&mut zip_bytes));
            let options = zip::write::SimpleFileOptions::default();
            zip.start_file("../outside", options).unwrap();
            zip.write_all(b"no").unwrap();
            zip.start_file("horizon-client.exe", options).unwrap();
            zip.write_all(&program).unwrap();
            zip.start_file(MANIFEST, options).unwrap();
            zip.write_all(&serde_json::to_vec(&manifest).unwrap())
                .unwrap();
            zip.finish().unwrap();
        }
        assert!(install(&root, std::io::Cursor::new(&zip_bytes)).is_err());
        assert!(!root.join("outside").exists());
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn choose_prefers_the_selected_tag_and_then_the_newest() {
        let root = temp("choose");
        fs::create_dir_all(&root).unwrap();
        let install_one = |tag: &str| {
            let program = marked(horizon_mods::api_level::LEVEL);
            let mut manifest = make_manifest(vec![file("horizon-client.exe", &program, true)]);
            manifest.tag = tag.into();
            manifest.seal();
            let dir = root.join(&manifest.key);
            fs::create_dir_all(&dir).unwrap();
            fs::write(dir.join("horizon-client.exe"), &program).unwrap();
            fs::write(dir.join(MANIFEST), serde_json::to_vec(&manifest).unwrap()).unwrap();
            manifest
        };
        let one = install_one("nightly");
        std::thread::sleep(std::time::Duration::from_millis(20));
        let two = install_one("nightly-2");
        assert_eq!(choose(&root, None).unwrap().0.key, two.key);
        assert_eq!(choose(&root, Some("nightly")).unwrap().0.key, one.key);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn pack_carries_the_exporter_sources_preparation_compiles() {
        let root = temp("pack-sources");
        let input = root.join("programs");
        let sources = root.join("repo");
        fs::create_dir_all(&input).unwrap();
        let program = marked(horizon_mods::api_level::LEVEL);
        fs::write(input.join(exec_name("horizon-client")), &program).unwrap();
        for name in ["horizon-ctl", "horizon-prepare", "horizon-server"] {
            fs::write(input.join(exec_name(name)), b"tool").unwrap();
        }
        fs::write(input.join("research-lock.json"), b"{}").unwrap();
        let parity = sources.join(EXPORTER_SOURCES).join("dev/horizonlab/parity");
        fs::create_dir_all(&parity).unwrap();
        fs::write(parity.join("VanillaHeightmapOracle.java"), b"class O {}").unwrap();
        let out = root.join("payload.zip");
        let manifest = pack(&input, &sources, "nightly", &out).unwrap();
        let expected =
            format!("{EXPORTER_SOURCES}/dev/horizonlab/parity/VanillaHeightmapOracle.java");
        assert!(manifest
            .files
            .iter()
            .any(|file| file.path == expected && !file.exec));
        let mut zip = zip::ZipArchive::new(fs::File::open(&out).unwrap()).unwrap();
        assert!(zip.by_name(&expected).is_ok());
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn a_version_gets_exactly_the_payloads_exporter_sources() {
        let root = temp("version-sources");
        let payload_root = root.join("payload");
        let version = root.join("versions/nightly");
        let program = marked(horizon_mods::api_level::LEVEL);
        let java = format!("{EXPORTER_SOURCES}/dev/horizonlab/parity/A.java");
        let write_payload = |manifest: &Manifest| {
            let dir = payload_root.join(&manifest.key);
            for file in &manifest.files {
                let to = dir.join(file.path());
                fs::create_dir_all(to.parent().unwrap()).unwrap();
                fs::write(to, file.path.as_bytes()).unwrap();
            }
        };
        let one = make_manifest(vec![
            file("horizon-client.exe", &program, true),
            file(&java, b"one", false),
        ]);
        write_payload(&one);
        ensure_version_in(&payload_root, &version, &one).unwrap();
        assert_eq!(fs::read(version.join(&java)).unwrap(), java.as_bytes());
        // A source only an older payload had must not survive into the next one.
        fs::write(version.join(EXPORTER_SOURCES).join("Old.java"), b"old").unwrap();
        let two = make_manifest(vec![
            file("horizon-client.exe", &program, true),
            file(&java, b"two", false),
        ]);
        assert_ne!(one.key, two.key);
        write_payload(&two);
        ensure_version_in(&payload_root, &version, &two).unwrap();
        assert_eq!(fs::read(version.join(&java)).unwrap(), java.as_bytes());
        assert!(!version.join(EXPORTER_SOURCES).join("Old.java").exists());
        let _ = fs::remove_dir_all(root);
    }

    fn temp(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("horizon-payload-{name}-{}", std::process::id()))
    }
}
