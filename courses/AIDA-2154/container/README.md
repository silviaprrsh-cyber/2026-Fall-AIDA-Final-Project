# Windows-only CV inference container

This independent CV engineering artifact is not an operational river-width model. No output is approved for downstream prediction. Existing failure evidence remains valid.

## Windows backend and runtime
The image is `mcr.microsoft.com/windows/servercore:ltsc2022`, not Linux. Use the Docker Windows container engine; no WSL or Linux distribution is required by this project. Hyper-V isolation runs a Windows kernel and supports the Server Core guest boundary on the Windows desktop. Do not switch to Linux containers to run these commands.

Python 3.13.11 x64 matches the recorded host Python micro version. Its official Python Software Foundation installer and Microsoft VC++ 14.44.35211 runtime were downloaded and their Authenticode signatures verified before their SHA-256 values were pinned in `install-runtime.ps1`. The image build downloads those official URLs and refuses a checksum mismatch. The script installs prerequisites inside the image only, never on the host. The Python micro version is retained for experiment reproduction, not a claim of being the newest maintenance release. Build records should include the resolved base-image digest and installed versions.

## Input and output contract
- `--model`: trusted `best_model.pt` from the database-view training run, including weights, training-only normalization and configuration.
- `--input`: NPZ `x` float32 N x 4 x 61 x 61 reflectance in [0,1], red/green/blue/NIR; `valid` bool N x 61 x 61. Inference needs quality flags, not water labels.
- `--output`: a new output directory; old evidence is never overwritten. Mask values are 0 non-water, 1 estimated water, 255 unknown. Invalid probabilities are NaN.
- Limits: at most 4096 samples, four CPU threads, batches of 16 and threshold 0.5. The image has no PostgreSQL or external service dependency at inference.

## Build
From the repository root, first confirm `docker info --format '{{.OSType}}'` prints `windows`. Create a NEW minimal context first:
```powershell
$Context = "courses/AIDA-2154/data/processed/cv_container_20261113/build_context_NEW"
python -B courses/AIDA-2154/container/prepare_context.py --output $Context
docker build --isolation=hyperv -f "$Context/container/Dockerfile" -t aida2154-cv:windows-local $Context
```
Do NOT use the full course directory as the build context. `prepare_context.py` copies exactly five named build inputs and a root `.dockerignore`; raw data, .env, SQL credentials and checkpoints never enter that directory. This protects classic Windows builders even if Dockerfile-specific ignore behavior differs. The script refuses an existing context and prints file hashes. Build downloads only the official base image, verified runtime installers and packages; runtime inference needs no network.

## Run
From the repository root, use the retained database-produced checkpoint and 132-image inference input. Select a NEW output directory:
```powershell
$InputDir = (Resolve-Path 'courses/AIDA-2154/data/processed/cv_container_20261113/database_model_verification').Path
$OutputDir = Join-Path (Get-Location) 'courses/AIDA-2154/data/processed/cv_container_20261113/windows_inference_NEW'
if (Test-Path -LiteralPath $OutputDir) { throw 'Choose a new output directory' }
New-Item -ItemType Directory -Path $OutputDir | Out-Null
docker run --rm --isolation=hyperv --network none --cpu-count 4 --memory 4g --mount "type=bind,source=$InputDir,target=C:\input,readonly" --mount "type=bind,source=$OutputDir,target=C:\output" aida2154-cv:windows-local --model C:/input/best_model.pt --input C:/input/inference_input.npz --output C:/output/run_NEW
```

`ContainerUser` is the non-administrator Windows identity. Linux-only options such as UID 10001, tmpfs, capability flags and no-new-privileges are intentionally absent. Only the dedicated output mount is writable; the container's temporary system layer remains writable because Windows does not provide the same Linux read-only-root workflow. Do not mount the entire repository or Docker named pipe. If a mount permission problem occurs, inspect it rather than broadly changing host permissions.

## Shared architecture and evidence
`src/cv_tools/model.py` is the single model definition. Training imports it; host inference loads it; the image copies that exact source as `C:/app/cv_model.py`. Seven inference tests and four existing CNN tests passed before this Windows packaging change. Original and database-trained checkpoint valid probabilities matched exactly for 132 test images, with 1,739 unknown pixels retained. A host copy-layout test is not a Docker execution.

Mount-ready model/input and host results: `data/processed/cv_container_20261113/database_model_verification/`. Shared-module checks: `data/processed/cv_container_20261113/shared_model_refactor_verification/`. Official-installer verification: `data/processed/cv_container_20261113/windows_build_prerequisites/`.

## Actual Windows verification (2026-11-13)
Windows image build and container inference PASSED. The local image ID is `sha256:6357eafb81bcf6b577b3e1d99f6ed1ae82290c18606acb58fe71bcf9980024ef` (Windows/amd64, 5,983,068,037 bytes, about 5.98 decimal GB). The resolved Server Core LTSC2022 base digest is `sha256:f1a914079973258061ddbc95a9af579eab2ee252a6fddb254b1be5d769761acd`.

The container ran as `ContainerUser`, with Hyper-V isolation, network `none`, four CPUs and 4 GiB memory limit. It exited 0. All 132 test masks matched host output exactly; maximum valid-pixel probability difference was 0, and 1,739 unknown pixels remained unknown. This proves engineering portability/parity for this Windows run, not independent water-width accuracy.

The image contains code/dependencies only, no checkpoint or input imagery. The retained model/input directory was mounted read-only; output used a separate writable mount. `image_contents_and_packages.txt` records the actual application-file and package inventory. No image registry push or full image tar export was performed. Rebuilds can resolve different base-tag revisions, so retain the recorded digest with this result.

Evidence is in `data/processed/cv_container_20261113/windows_container_verification/`: verification.json, image/container inspections, build logs, run.log, run_01 predictions and image inventory. Failed first-attempt build contexts/logs remain as diagnostics; build_context_v2 is the successful minimal context. Eight inference/context tests pass. The original CV failure report and downstream-use prohibition are unchanged.

Official references: [Python release](https://www.python.org/downloads/release/python-31311/), [Windows base images](https://learn.microsoft.com/en-us/virtualization/windowscontainers/manage-containers/container-base-images), [Windows isolation](https://learn.microsoft.com/en-us/virtualization/windowscontainers/manage-containers/hyperv-container).

## Two-part Windows container delivery

Obtain both binary parts from the course `outputs` directory: `AIDA2154-CV-Windows-20261113.zip.part001` (1,321,342,227 bytes) and `AIDA2154-CV-Windows-20261113.zip.part002` (1,321,342,226 bytes). Each is strictly below 2,000,000,000 bytes; neither can be extracted independently. Follow the [two-part delivery and startup guide](../outputs/README.md): verify the part hashes, join them in order using streaming PowerShell, verify the reconstructed ZIP against the original SHA-256, then extract it and run `./run.ps1` from the package folder. The guide contains the canonical commands and hashes.

The reconstructed package contains the full saved image, external model weights, scripts and two synthetic smoke-test samples, not real source imagery. It requires a compatible licensed Windows host, Docker Windows container mode and Server Core LTSC2022 Hyper-V isolation; no host Python/PostgreSQL is required. The earlier extracted-package test passed on the same development computer, not a second clean machine. The original full ZIP is retained locally and Git-ignored; the two delivery parts are not ignored. Nothing has been uploaded or submitted. This handoff remains separate from the historical review package and pending formal course submission.
