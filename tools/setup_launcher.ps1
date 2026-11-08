# Developer bootstrap for this offline fork. Runtime/player code remains in Rust.
# Run from a checkout: powershell -ExecutionPolicy Bypass -File tools/setup_launcher.ps1
[CmdletBinding()]
param(
    [string]$MinecraftDir,
    [ValidateRange(1, 32)][int]$Jobs = 4,
    [switch]$BuildOnly,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This setup command is for Windows.' }
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$toolchain = '1.95.0-x86_64-pc-windows-msvc'

function Quote-NativeArgument {
    param([string]$Value)
    if ($Value -and $Value -notmatch '[\s"]') { return $Value }
    $escaped = [regex]::Replace($Value, '(\\*)"', [Text.RegularExpressions.MatchEvaluator]{
        param($match)
        return ('\' * (2 * $match.Groups[1].Value.Length + 1)) + '"'
    })
    $escaped = [regex]::Replace($escaped, '(\\+)$', [Text.RegularExpressions.MatchEvaluator]{
        param($match)
        return '\' * (2 * $match.Value.Length)
    })
    return '"' + $escaped + '"'
}

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments, [switch]$Capture)
    # GUI-subsystem EXEs can return early under PowerShell's call operator. Explicitly wait
    # and drain both pipes concurrently, keeping stderr out of machine-readable stdout.
    $process = [Diagnostics.Process]::new()
    $process.StartInfo.FileName = $Program
    $process.StartInfo.Arguments = ($Arguments | ForEach-Object { Quote-NativeArgument $_ }) -join ' '
    $process.StartInfo.WorkingDirectory = (Get-Location).Path
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
    $process.StartInfo.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
    try {
        $process.Start() | Out-Null
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $output = $stdout.GetAwaiter().GetResult()
        $errors = $stderr.GetAwaiter().GetResult()
        if ($errors) { Write-Host $errors.TrimEnd() }
        if (!$Capture -or $process.ExitCode -ne 0) { if ($output) { Write-Host $output.TrimEnd() } }
        if ($process.ExitCode -ne 0) { throw "$Program failed (exit $($process.ExitCode)). See its output above." }
        if ($Capture) { return $output }
    } finally { $process.Dispose() }
}

function Install-Winget {
    param([string]$Id, [string[]]$Extra = @())
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (!$winget) { throw "Install Microsoft's App Installer (winget), then rerun setup to install $Id." }
    Write-Host "Installing missing prerequisite: $Id"
    Invoke-Checked $winget.Source (@('install', '--id', $Id, '--exact', '--silent', '--source', 'winget',
        '--accept-source-agreements', '--accept-package-agreements') + $Extra)
}

function Find-Fxc {
    if ($env:GPUI_FXC_PATH -and (Test-Path -LiteralPath $env:GPUI_FXC_PATH)) { return $env:GPUI_FXC_PATH }
    $command = Get-Command fxc.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $bin = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    foreach ($sdk in @(Get-ChildItem $bin -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending)) {
        $fxc = Join-Path $sdk.FullName 'x64\fxc.exe'
        if (Test-Path -LiteralPath $fxc) { return $fxc }
    }
}

function Find-Msvc {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $vswhere) {
        return Invoke-Checked $vswhere @('-utf8', '-latest', '-products', '*', '-requires',
            'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath') -Capture
    }
}

function Find-Java {
    param([int]$Major, [string]$Minecraft)
    $candidates = @()
    if ($env:JAVA_HOME) { $candidates += Join-Path $env:JAVA_HOME 'bin\java.exe' }
    $command = Get-Command java.exe -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    foreach ($vendor in @('Eclipse Adoptium', 'Java', 'Microsoft', 'Zulu', 'BellSoft', 'Amazon Corretto', 'OpenJDK')) {
        $parent = Join-Path $env:ProgramFiles $vendor
        $candidates += @(Get-ChildItem $parent -Directory -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName 'bin\java.exe' })
    }
    foreach ($folder in @($Minecraft, (Join-Path $env:APPDATA '.minecraft')) | Select-Object -Unique) {
        if ($folder) {
            $candidates += @(Get-ChildItem (Join-Path $folder 'runtime') -Recurse -Filter java.exe -File -ErrorAction SilentlyContinue |
                ForEach-Object FullName)
        }
    }
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (!(Test-Path -LiteralPath $candidate)) { continue }
        $previous = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try { $version = (& $candidate -version 2>&1 | ForEach-Object ToString) -join "`n" }
        finally { $ErrorActionPreference = $previous }
        if ($LASTEXITCODE -eq 0 -and $version -match 'version "([0-9]+)[.\-"]' -and [int]$Matches[1] -ge $Major) {
            return Split-Path (Split-Path $candidate)
        }
    }
}

$variables = @('CARGO_INCREMENTAL', 'CARGO_PROFILE_DEV_DEBUG', 'CARGO_BUILD_JOBS',
    'HORIZON_LAUNCHER_NO_SELF_UPDATE', 'HORIZON_SERVER_JAR', 'GPUI_FXC_PATH', 'JAVA_HOME')
$saved = @{}
foreach ($key in $variables) { $saved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
Push-Location $repo
try {
    if (!(Find-Msvc) -or !(Find-Fxc)) {
        Install-Winget 'Microsoft.VisualStudio.2022.BuildTools' @('--override',
            '--wait --passive --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended')
    }
    $env:GPUI_FXC_PATH = Find-Fxc
    if (!(Find-Msvc) -or !$env:GPUI_FXC_PATH) { throw 'C++ tools or the Windows SDK are unavailable. Finish their installation/restart, then rerun setup.' }
    $rustup = Join-Path $env:USERPROFILE '.cargo\bin\rustup.exe'
    if (!(Test-Path -LiteralPath $rustup)) {
        $command = Get-Command rustup.exe -ErrorAction SilentlyContinue
        if ($command) { $rustup = $command.Source }
        else { Install-Winget 'Rustlang.Rustup' }
    }
    if (!(Test-Path -LiteralPath $rustup)) { throw 'rustup is unavailable. Finish its installation, then rerun setup.' }
    $installed = Invoke-Checked $rustup @('toolchain', 'list') -Capture
    if ($installed -notmatch [regex]::Escape($toolchain)) {
        Invoke-Checked $rustup @('toolchain', 'install', $toolchain, '--profile', 'minimal')
    }
    $env:CARGO_INCREMENTAL = '0'
    $env:CARGO_PROFILE_DEV_DEBUG = '0'
    $env:CARGO_BUILD_JOBS = "$Jobs"
    $env:HORIZON_LAUNCHER_NO_SELF_UPDATE = '1'
    Write-Host 'Building the offline launcher...'
    Invoke-Checked $rustup @('run', $toolchain, 'cargo', 'build', '--manifest-path', 'launcher/Cargo.toml', '--locked')
    $target = if ($env:CARGO_TARGET_DIR) { [IO.Path]::GetFullPath($env:CARGO_TARGET_DIR) } else { Join-Path $repo 'launcher\target' }
    $dist = Join-Path $repo 'dist'
    New-Item -ItemType Directory -Force $dist | Out-Null
    $launcher = Join-Path $dist 'horizon-launcher.exe'
    Copy-Item (Join-Path $target 'debug\horizon-launcher.exe') $launcher -Force
    Write-Host "Built: $launcher"
    if (!$BuildOnly) {
        $info = Invoke-Checked $launcher @('--json', 'settings') -Capture | ConvertFrom-Json
        if ($MinecraftDir) {
            Invoke-Checked $launcher @('settings', 'minecraft-dir', ([IO.Path]::GetFullPath($MinecraftDir))) -Capture | Out-Null
        } else { $MinecraftDir = $info.minecraft_dir }
        $tag = $info.selected_version
        if (!$tag) {
            Write-Host 'Installing a Horizon game build through the existing launcher...'
            $install = Invoke-Checked $launcher @('--json', 'install', 'latest') -Capture | ConvertFrom-Json
            $tag = $install.installed
            Invoke-Checked $launcher @('settings', 'selected-version', $tag) -Capture | Out-Null
        }
        $version = Join-Path (Join-Path $info.launcher_dir 'versions') $tag
        $pins = (Get-Content (Join-Path $version 'research-lock.json') -Raw | ConvertFrom-Json).minecraft
        $ready = $false
        $preparer = Join-Path $version 'horizon-prepare.exe'
        if (Test-Path -LiteralPath $preparer) {
            try {
                Invoke-Checked $preparer @('--check', '--root', $version) -Capture | Out-Null
                $ready = $true
            } catch { $ready = $false }
        }
        if (!$ready) {
            $java = Find-Java $pins.java_major $MinecraftDir
            if (!$java) {
                Install-Winget "EclipseAdoptium.Temurin.$($pins.java_major).JDK"
                $java = Find-Java $pins.java_major $MinecraftDir
            }
            if (!$java) { throw "Java $($pins.java_major) is unavailable. Finish its installation, then rerun setup." }
            $env:JAVA_HOME = $java
            $cache = Join-Path $info.launcher_dir 'server-jars'
            $jar = Join-Path $cache "$($pins.version).jar"
            $hash = $pins.server_sha1
            if ($hash -notmatch '^[a-f0-9]{40}$') { throw 'The installed build has an invalid server JAR checksum.' }
            if ($env:HORIZON_SERVER_JAR -and (Test-Path -LiteralPath $env:HORIZON_SERVER_JAR) -and
                (Get-FileHash $env:HORIZON_SERVER_JAR -Algorithm SHA1).Hash.ToLowerInvariant() -eq $hash) {
                $jar = $env:HORIZON_SERVER_JAR
            }
            if (!(Test-Path -LiteralPath $jar) -or (Get-FileHash $jar -Algorithm SHA1).Hash.ToLowerInvariant() -ne $hash) {
                Write-Host "Downloading the verified Minecraft $($pins.version) server JAR to your local cache..."
                New-Item -ItemType Directory -Force $cache | Out-Null
                $partial = "$jar.$([guid]::NewGuid().ToString('N')).partial"
                Invoke-WebRequest -UseBasicParsing -Uri "https://piston-data.mojang.com/v1/objects/$hash/server.jar" -OutFile $partial
                if ((Get-FileHash $partial -Algorithm SHA1).Hash.ToLowerInvariant() -ne $hash) { throw "Server JAR checksum mismatch: $partial" }
                Move-Item $partial $jar -Force
            }
            $env:HORIZON_SERVER_JAR = $jar
            $arguments = @('prepare', '--version', $tag)
            if ($MinecraftDir) { $arguments += @('--minecraft', $MinecraftDir) }
            try { Invoke-Checked $launcher $arguments }
            catch {
                if ($NoLaunch) { throw }
                Write-Warning "Preparation needs attention: $_ Use Home's Minecraft folder chooser, then Play again."
            }
        } else { Write-Host 'The selected game is already prepared.' }
        if (!$NoLaunch) {
            New-Item -ItemType Directory -Force $info.game_dir | Out-Null
            Start-Process -FilePath $launcher -WorkingDirectory $info.game_dir
        }
    }
} finally {
    Pop-Location
    foreach ($key in $variables) { [Environment]::SetEnvironmentVariable($key, $saved[$key], 'Process') }
}
