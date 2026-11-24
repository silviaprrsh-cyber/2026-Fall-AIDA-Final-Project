# outputs

Use this folder only for the evidence described in the current D2L instructions for this course. Add a short note here when you place files in the folder. Do not add restricted data or credentials.

## Current contents
The cv_gap_fill, cv_material_screening and cv_material_diversity folders are dated historical acquisition/material-review evidence. They are not the current final training set or approved ground truth. Current final experiment figures and numeric equivalents remain beside their frozen data under ../data/processed/point_cnn_20261113, point_width_validation_20261113 and cv_release_20261113. The candidate copies selected figures and tables, not the whole historical outputs tree. The course README is the entry point.


## Engineering replay evidence

The PostgreSQL replay reports are retained under ../data/processed/cv_pipeline_20261113. This outputs directory does not receive credentials, database dumps or a duplicate raw imagery library.

## Two-part Windows container delivery

Current recipient files are **both binary parts** listed below: `AIDA2154-CV-Windows-20261113.zip.part001` and `AIDA2154-CV-Windows-20261113.zip.part002`. Obtain both, then follow the reconstruction and startup steps below. The original complete `AIDA2154-CV-Windows-20261113.zip`, **2,642,684,453 bytes (2.64 GB)**, and its Downloads copy are retained locally as the reference, not the current delivery method. Only the full ZIP is Git-ignored; the two parts are not ignored. No file has been uploaded or submitted.

Original/reconstructed ZIP SHA-256: `e47a51fcb4a116ddf2ca43d9b4269fd8b5efa1845abc604333a24e09bed62713`.

After reconstruction, the ZIP contains a complete Docker-save TAR, the unchanged trained checkpoint, `run.ps1`, English/Chinese instructions and two synthetic inputs with expected outputs. No original satellite data, point coordinates or credentials are included. This is an inference handoff, separate from the frozen classroom review package.

First verify and join both parts, then verify the reconstructed ZIP's SHA-256 before extracting and running `./run.ps1` in PowerShell. Use the complete commands below rather than trying to extract either part. The recipient needs a licensed, compatible Windows host, Docker in Windows container mode and Hyper-V isolation for **Windows Server Core LTSC2022**; not Linux/WSL. Allow approximately 25 GB disk and 4 GiB available memory. Python and PostgreSQL are not required on the host. Model/input mounts are read-only and inference has no network. Follow the bundled licensing notes; Windows client use is for development/testing.

Verification: all 13 image layers passed SHA checks, Docker load succeeded, all 12 extracted files matched, and the script ran from an extracted directory outside this checkout. Both synthetic samples matched host masks, validity flags and probabilities exactly. This was tested on the same development computer, not a second clean machine. The CV suitability conclusion is unchanged.

## Two-part delivery and startup (2026-11-14)

The original ZIP is retained unchanged. Its two binary parts are listed below; **each is strictly smaller than 2,000,000,000 bytes (2 GB)**. These are not independent ZIP archives and cannot be extracted separately. Obtain both parts and keep their filenames and order.

| Part | Exact bytes | SHA-256 |
|---|---:|---|
| [`AIDA2154-CV-Windows-20261113.zip.part001`](AIDA2154-CV-Windows-20261113.zip.part001) | 1,321,342,227 | `9d029889eb46d64553e0421b7d7459f4d37e246dd5ff67d5727846eb520bd165` |
| [`AIDA2154-CV-Windows-20261113.zip.part002`](AIDA2154-CV-Windows-20261113.zip.part002) | 1,321,342,226 | `5b403835d398d9b100d2132b03146c672fae21a06423136714ffa22dfc65cc38` |

The two part files were re-read in order with buffered streaming I/O: their combined 2,642,684,453 bytes reproduce the original SHA-256 above exactly. This split does not rebuild the Docker image, change the weights or update the README inside the existing ZIP. No file has been uploaded or submitted.

### 1. Reconstruct and verify the ZIP
Place only the two parts in a new folder and open PowerShell in that folder. If you already have the complete original ZIP, skip reconstruction and use step 2, which verifies it again. The commands below check each part, join them using an 8 MiB buffer (not `ReadAllBytes`), and verify the complete ZIP. Existing files are never overwritten. If a copy is interrupted, keep the source parts and retry in a different empty folder.

```powershell
$ErrorActionPreference = 'Stop'
$parts = @(
    'AIDA2154-CV-Windows-20261113.zip.part001',
    'AIDA2154-CV-Windows-20261113.zip.part002'
)
$expectedSizes = @(1321342227L, 1321342226L)
$expectedPartHashes = @(
    '9d029889eb46d64553e0421b7d7459f4d37e246dd5ff67d5727846eb520bd165',
    '5b403835d398d9b100d2132b03146c672fae21a06423136714ffa22dfc65cc38'
)
for ($i = 0; $i -lt $parts.Count; $i++) {
    $parts[$i] = (Resolve-Path -LiteralPath $parts[$i]).Path
    if ((Get-Item -LiteralPath $parts[$i]).Length -ne $expectedSizes[$i]) {
        throw "Wrong part size: $($parts[$i])"
    }
    if ((Get-FileHash -LiteralPath $parts[$i] -Algorithm SHA256).Hash -ne $expectedPartHashes[$i]) {
        throw "Part checksum mismatch: $($parts[$i])"
    }
}
$zip = Join-Path (Get-Location).Path 'AIDA2154-CV-Windows-20261113.zip'
if (Test-Path -LiteralPath $zip) {
    throw 'ZIP already exists. Keep it; use a different folder to reconstruct.'
}
$destination = [System.IO.File]::Open(
    $zip, [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write, [System.IO.FileShare]::None
)
try {
    foreach ($part in $parts) {
        $source = [System.IO.File]::OpenRead($part)
        try { $source.CopyTo($destination, 8MB) }
        finally { $source.Dispose() }
    }
}
finally { $destination.Dispose() }

$expectedZipHash = 'e47a51fcb4a116ddf2ca43d9b4269fd8b5efa1845abc604333a24e09bed62713'
if ((Get-Item -LiteralPath $zip).Length -ne 2642684453L -or
    (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $expectedZipHash) {
    throw 'Reconstructed ZIP verification failed. Do not extract or run it.'
}
Write-Host 'ZIP verified. Both part files have been preserved.'
```

### 2. Extract and run the default smoke test
Use a licensed, compatible Windows host with Docker running in **Windows container mode**, supporting **Server Core LTSC2022 with Hyper-V isolation**. Linux containers/WSL mode cannot run this image. Allow approximately **25 GB free disk** for the parts, reconstructed ZIP, extraction and loaded image, plus **4 GiB available memory**. Host Python/PostgreSQL is not needed. Do not change host security or execution-policy settings to force the script to run.

Run the following from the folder containing the verified complete ZIP. It extracts into a new directory, enters the package's actual top-level folder and runs the bundled script:

```powershell
$ErrorActionPreference = 'Stop'
$zip = (Resolve-Path -LiteralPath '.\AIDA2154-CV-Windows-20261113.zip').Path
$expectedZipHash = 'e47a51fcb4a116ddf2ca43d9b4269fd8b5efa1845abc604333a24e09bed62713'
if ((Get-Item -LiteralPath $zip).Length -ne 2642684453L -or
    (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $expectedZipHash) {
    throw 'ZIP verification failed. Do not extract or run it.'
}
$extract = Join-Path (Get-Location).Path 'AIDA2154-CV-unpacked'
if (Test-Path -LiteralPath $extract) {
    throw 'Extraction folder already exists. Choose a new folder name.'
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $extract)
Set-Location -LiteralPath (Join-Path $extract 'AIDA2154-CV-Windows-20261113')
.\run.ps1
```

`run.ps1` checks package hashes, loads the saved image if needed, then runs inference and compares the **two synthetic samples** with their expected outputs. It does not train the model. Results are in the new `results-*/prediction/` subfolder as `predictions.npz` and `inference.json`. For your own input, follow the [container input contract](../container/README.md) and the bundled README; ordinary RGB/JPEG photographs cannot be passed directly.

The earlier container/smoke-test verification was on the same development computer, not a second clean machine. This splitting operation verified byte-for-byte reconstruction; it did not rerun Docker or establish real river-width accuracy. The original ZIP is Git-ignored and retained locally; the two delivery parts are not ignored. All three files remain untracked, and no upload or submission has been performed.
