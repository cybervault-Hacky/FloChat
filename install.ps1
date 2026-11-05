# FloChat installer for Windows PowerShell.
#
# Conservative by design:
#   * never requires administrator privileges
#   * never changes the PowerShell execution policy
#   * never modifies system Python or installs unrelated software
#   * never deletes your files; the only directory it creates is .\.venv
#   * never reports success it has not verified by running the CLI
#
# If PowerShell blocks this script, run it for the current process only:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
# That changes nothing permanently and needs no administrator rights.
#
# Exit codes: 0 installed, 1 installation failed, 2 unusable usage/environment,
#             3 unsupported platform.

$ErrorActionPreference = 'Stop'
$MinMajor = 3
$MinMinor = 10
$ExitUnsupported = 3
$ExitFailed = 1
$ExitUsage = 2

function Write-Say {
    param([string]$Message)
    Write-Host $Message
}

function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host '==>' -ForegroundColor White -NoNewline
    Write-Host " $Message"
}

function Write-Ok {
    param([string]$Message)
    Write-Host '  ok ' -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Note {
    param([string]$Message)
    Write-Host '  -- ' -ForegroundColor DarkGray -NoNewline
    Write-Host $Message
}

function Write-Warn {
    param([string]$Message)
    Write-Host '  !! ' -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

# Write-Fail <what failed> <why> <what to do next>
function Write-Fail {
    param([string]$What, [string]$Why = '', [string]$Next = '')
    Write-Host ''
    Write-Host 'FAILED ' -ForegroundColor Red -NoNewline
    Write-Host $What
    if ($Why) { Write-Host "  Why:    $Why" }
    if ($Next) { Write-Host "  Next:   $Next" }
}

# Run a native command and return $true only when it exited 0.
function Invoke-Native {
    param([string]$FilePath, [string[]]$Arguments)
    $output = & $FilePath @Arguments 2>&1
    $code = $LASTEXITCODE
    return [pscustomobject]@{ Ok = ($code -eq 0); Output = ($output -join "`n"); Code = $code }
}

function Get-PythonInfo {
    <# Find an interpreter that satisfies the minimum version; never assume `python`. #>
    $candidates = @(
        @{ Exe = 'py'; Args = @('-3', '-c') },
        @{ Exe = 'python'; Args = @('-c') },
        @{ Exe = 'python3'; Args = @('-c') }
    )
    $probe = 'import sys; print("%d.%d" % sys.version_info[:2])'
    foreach ($candidate in $candidates) {
        $existing = Get-Command $candidate.Exe -ErrorAction SilentlyContinue
        if (-not $existing) { continue }
        $result = Invoke-Native -FilePath $candidate.Exe -Arguments ($candidate.Args + @($probe))
        if (-not $result.Ok) { continue }
        $versionText = ($result.Output -split "`n" | Where-Object { $_ -match '^\d+\.\d+$' } | Select-Object -First 1)
        if (-not $versionText) { continue }
        $parts = $versionText.Split('.')
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        if ($major -gt $MinMajor -or ($major -eq $MinMajor -and $minor -ge $MinMinor)) {
            $prefix = @()
            if ($candidate.Exe -eq 'py') { $prefix = @('-3') }
            return [pscustomobject]@{
                Ok      = $true
                Exe     = $candidate.Exe
                Prefix  = $prefix
                Version = $versionText
            }
        }
    }
    return [pscustomobject]@{ Ok = $false; Exe = $null; Prefix = @(); Version = $null }
}

function Test-VenvSupport {
    param([string]$Exe, [string[]]$Prefix)
    $result = Invoke-Native -FilePath $Exe -Arguments ($Prefix + @('-c', 'import venv'))
    return $result.Ok
}

Write-Step 'FloChat installer'

# --- 1. platform ------------------------------------------------------------
$platformIsWindows = $true
if ($null -ne $IsWindows) { $platformIsWindows = $IsWindows } elseif ($env:OS -ne 'Windows_NT') { $platformIsWindows = $false }
if (-not $platformIsWindows) {
    Write-Fail "This installer is for Windows; this system reports something else." `
        'install.ps1 only targets Windows PowerShell.' `
        'On Linux, macOS, or Termux run ./install.sh instead.'
    exit $ExitUnsupported
}
Write-Ok "Platform: Windows $([System.Environment]::OSVersion.Version) ($env:PROCESSOR_ARCHITECTURE)"

# --- 2. PowerShell version --------------------------------------------------
$psVersion = $PSVersionTable.PSVersion
if ($psVersion.Major -lt 5) {
    Write-Fail "PowerShell $psVersion is too old." `
        'FloChat needs PowerShell 5.1 or newer (Windows PowerShell 5.1 ships with Windows 10/11).' `
        'Update Windows PowerShell, or install PowerShell 7 from Microsoft.'
    exit $ExitUsage
}
Write-Ok "PowerShell $psVersion"

# --- 3. project directory ---------------------------------------------------
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path (Join-Path $Root 'pyproject.toml')) -or
    -not (Test-Path (Join-Path $Root 'src\flochat'))) {
    Write-Fail "This does not look like the FloChat repository: $Root" `
        'pyproject.toml or src\flochat is missing; the clone may be incomplete.' `
        'Clone the full repository again and run .\install.ps1 from its root.'
    exit $ExitUsage
}
Write-Ok "Project directory: $Root"

# --- 4. git (informational) -------------------------------------------------
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    $gitVersion = Invoke-Native -FilePath 'git' -Arguments @('--version')
    Write-Ok ($gitVersion.Output.Trim())
} else {
    Write-Warn 'Git is not installed. FloChat will work, but updates need it.'
    Write-Note 'Install Git from https://git-scm.com/download/win (no restart needed).'
}

# --- 5. python --------------------------------------------------------------
Write-Step 'Checking Python'
$python = Get-PythonInfo
if (-not $python.Ok) {
    Write-Fail 'No Python 3.10 or newer was found on PATH.' `
        'Python is missing, or only an older version is installed.' `
        'Install Python 3.10+ from https://www.python.org/downloads/windows/ (tick "Add python.exe to PATH"), then reopen PowerShell and run this installer again.'
    exit $ExitUsage
}
Write-Ok "Python $($python.Version) ($($python.Exe))"

if (-not (Test-VenvSupport -Exe $python.Exe -Prefix $python.Prefix)) {
    Write-Fail 'This Python cannot create virtual environments.' `
        'The venv module is missing from this Python installation.' `
        'Repair the Python installation (re-run its installer and choose "Repair").'
    exit $ExitUsage
}
Write-Ok 'Virtual environments are available'

# --- 6. install -------------------------------------------------------------
Write-Step 'Preparing the environment'
$Venv = Join-Path $Root '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'

if (Test-Path $Venv) {
    if (-not (Test-Path $VenvPython)) {
        Write-Fail "The existing environment at $Venv is incomplete." `
            'It has no Scripts\python.exe; the previous install may have been interrupted.' `
            "Remove it with: Remove-Item -Recurse -Force '$Venv'   then run this installer again."
        exit $ExitFailed
    }
    Write-Ok "Reusing the existing environment at $Venv"
} else {
    Write-Note "Creating an isolated environment at $Venv"
    $created = Invoke-Native -FilePath $python.Exe -Arguments ($python.Prefix + @('-m', 'venv', $Venv))
    if (-not $created.Ok) {
        Write-Fail 'Could not create the Python environment.' `
            "venv failed: $($created.Output)" `
            'Repair the Python installation, then run this installer again.'
        exit $ExitFailed
    }
    Write-Ok 'Environment created'
}

Write-Step 'Installing FloChat and its dependencies'
$pip = Invoke-Native -FilePath $VenvPython -Arguments @('-m', 'pip', '--version')
if (-not $pip.Ok) {
    Write-Fail 'pip is not available in the environment.' `
        'ensurepip may be missing or disabled.' `
        "Repair Python, remove '$Venv', and run this installer again."
    exit $ExitFailed
}

$pipUpgrade = Invoke-Native -FilePath $VenvPython -Arguments @('-m', 'pip', 'install', '--quiet', '--upgrade', 'pip>=26.2')
if (-not $pipUpgrade.Ok) {
    Write-Fail 'Could not install the required packaging tool (pip >=26.2).' `
        'Older bundled versions have published security advisories.' `
        'Check network/proxy or use a trusted compatible wheel; do not bypass this check.'
    exit $ExitFailed
}

$install = Invoke-Native -FilePath $VenvPython -Arguments @('-m', 'pip', 'install', '--quiet', '-e', $Root)
if (-not $install.Ok) {
    Write-Fail 'Installing FloChat failed.' `
        "pip reported: $($install.Output)" `
        'Check your network or proxy settings, then run this installer again.'
    exit $ExitFailed
}
Write-Ok 'FloChat installed into the environment'

# --- 7. verify --------------------------------------------------------------
Write-Step 'Verifying the installation'
$version = Invoke-Native -FilePath $VenvPython -Arguments @('-m', 'flochat.cli', '--version')
if (-not $version.Ok) {
    $tail = ($version.Output -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 3) -join ' | '
    Write-Fail 'FloChat installed but does not run.' `
        "The CLI exited with an error: $tail" `
        "Run: '$VenvPython' -m flochat.cli doctor   for details."
    exit $ExitFailed
}
Write-Ok "Verified: $($version.Output.Trim())"

$doctor = Invoke-Native -FilePath $VenvPython -Arguments @('-m', 'flochat.cli', 'doctor')
if (-not $doctor.Ok) {
    Write-Warn "Installation works, but 'doctor' reported problems."
    Write-Note "Run: '$VenvPython' -m flochat.cli doctor   to see them."
}

# --- 8. summary -------------------------------------------------------------
Write-Step 'Done'
Write-Say 'Start FloChat from this directory with:'
Write-Say "  cd `"$Root`" ; .\start.ps1"
Write-Say ''
Write-Say 'Or activate the environment yourself:'
Write-Say "  & '$Venv\Scripts\Activate.ps1' ; flochat doctor"
Write-Say ''
Write-Note 'No administrator rights were needed, and no system settings were changed.'
Write-Note 'Installs the terminal CLI, including the local Comment Manager.'
Write-Note 'YouTube needs OAuth setup and individual approval. Floating UI is optional: see Phase 06 setup in README.md. No automatic startup or posting.'
exit 0
