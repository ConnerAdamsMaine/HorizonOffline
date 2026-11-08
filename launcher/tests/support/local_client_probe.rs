//! An independent game-process fixture: reports the actual argv/environment and build it ran.
//! It needs neither game data nor a graphics adapter.
fn main() {
    let args: Vec<_> = std::env::args().skip(1).collect();
    for arg in &args {
        println!("arg={arg}");
    }
    for key in [
        "HORIZON_SESSION_FILE",
        "HORIZON_ACCOUNT_SESSIONS",
        "HORIZON_LAUNCHER_EXE",
    ] {
        println!("{key}={}", std::env::var_os(key).is_some());
    }
    let executable = std::env::current_exe().unwrap();
    // macOS hardlinks the executable inside Horizon.app; Windows copies the marker beside it.
    let build = executable
        .ancestors()
        .find_map(|dir| std::fs::read_to_string(dir.join("build.txt")).ok())
        .unwrap();
    println!("build={build}");
    println!("cwd={}", std::env::current_dir().unwrap().display());
    eprintln!("fixture stderr");
    let fail = args.windows(2).any(|pair| pair == ["--name", "Fail"]);
    std::process::exit(if fail { 7 } else { 0 });
}
