//! Embeds Horizon's icon (`packaging/icons/horizon.ico`) in the Windows executables, as icon
//! resource 1: Explorer and the task bar show it, and the window takes it as its icon.
fn main() {
    let dir = std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default();
    let ico = format!("{dir}/../packaging/icons/horizon.ico");
    println!("cargo:rerun-if-changed={ico}");
    #[cfg(windows)]
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        let mut resource = winresource::WindowsResource::new();
        resource.set_icon(&ico);
        if let Err(e) = resource.compile() {
            panic!("embedding {ico}: {e}");
        }
    }
    // The payload archive is compiled into the launcher (HORIZON_PAYLOAD_ZIP). Without one,
    // an empty file keeps `include_bytes!` valid and `payload::embedded()` says there is none.
    let out = std::env::var("OUT_DIR").expect("cargo gives OUT_DIR");
    let target = format!("{out}/payload.zip");
    println!("cargo:rerun-if-env-changed=HORIZON_PAYLOAD_ZIP");
    match std::env::var_os("HORIZON_PAYLOAD_ZIP").filter(|path| !path.is_empty()) {
        Some(path) => {
            println!("cargo:rerun-if-changed={}", path.to_string_lossy());
            std::fs::copy(&path, &target)
                .unwrap_or_else(|e| panic!("copying {}: {e}", path.to_string_lossy()));
        }
        None => std::fs::write(&target, b"").expect("writing the empty payload marker"),
    }
}
