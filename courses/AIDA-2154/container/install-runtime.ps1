$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$InstallerDir = 'C:/cv-build-installers'
New-Item -ItemType Directory -Path $InstallerDir -Force | Out-Null

function Install-VerifiedRuntime {
    param([string]$Url, [string]$Filename, [string]$Sha256, [string[]]$InstallerArguments)
    $Path = Join-Path $InstallerDir $Filename
    Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Path
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Sha256) {
        throw "Installer checksum mismatch: $Filename"
    }
    $Process = Start-Process -FilePath $Path -ArgumentList $InstallerArguments -Wait -PassThru -WindowStyle Hidden
    if ($Process.ExitCode -notin @(0, 3010)) {
        throw "Installer failed: $Filename exit $($Process.ExitCode)"
    }
    Remove-Item -LiteralPath $Path -Force
}

Install-VerifiedRuntime -Url 'https://download.visualstudio.microsoft.com/download/pr/e9604e21-4b79-4096-a4b3-1b63d4b55b4d/CC0FF0EB1DC3F5188AE6300FAEF32BF5BEEBA4BDD6E8E445A9184072096B713B/VC_redist.x64.exe' -Filename 'vc_redist.x64.exe' -Sha256 'CC0FF0EB1DC3F5188AE6300FAEF32BF5BEEBA4BDD6E8E445A9184072096B713B' -InstallerArguments @('/install', '/quiet', '/norestart')
Install-VerifiedRuntime -Url 'https://www.python.org/ftp/python/3.13.11/python-3.13.11-amd64.exe' -Filename 'python-3.13.11-amd64.exe' -Sha256 '30D4654B3EAC7DDFDF2682DB4C8DCB490F3055F4F33C6906D6B828F680152101' -InstallerArguments @('/quiet', 'InstallAllUsers=1', 'TargetDir=C:\Python', 'Include_pip=1', 'Include_test=0', 'Include_doc=0', 'Include_launcher=0', 'InstallLauncherAllUsers=0', 'PrependPath=0', 'Shortcuts=0')
& C:/Python/python.exe --version
if ($LASTEXITCODE -ne 0) { throw 'Python version check failed' }
Remove-Item -LiteralPath $InstallerDir
