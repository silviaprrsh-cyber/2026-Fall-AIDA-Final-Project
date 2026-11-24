# Compute and reproduction evidence
Measured 2026-11-13 on Windows, Python 3.13.11, PyTorch 2.15.0+cpu, 4 PyTorch CPU threads. The host exposes 22 logical CPUs; no GPU was used.

| Run | Wall time | CPU time | Peak resident memory |
|---|---:|---:|---:|
| Original training/evaluation | 93.57 s | Not recorded | Not recorded |
| Frozen inference replay, complete workflow | 6.0094 s | 3.1094 s | 440,422,400 bytes (420.02 MiB) |
| Unchanged 40-epoch training replay, wrapper | 78.0578 s | 224.1094 s | 560,390,144 bytes (534.43 MiB) |

The inference-only portion is 0.3309 s for 132 images, excluding imports and preparation. The training function internally reported 75.13 s; wrapper timing includes additional work. Windows GetProcessMemoryInfo PeakWorkingSetSize measures the entire replay process lifetime, including imported libraries, not only tensors. CPU time can exceed wall time with multiple threads. These are single-machine observations, not performance guarantees.

The original run was not retrospectively assigned a memory value. The new replay used unchanged frozen data/configuration, selected epoch 40 again, reproduced all test counts and produced the exact original model SHA-256 57659d1f5acfe621b81996b5745d4d3d92c9c6c782f9facab71bd7db3d369b32. Original evidence remains unchanged. No further model optimization was performed.

Evidence:
- data/processed/cv_release_20261113/evaluation/evaluation.json
- data/processed/cv_release_20261113/training_replay/resources.json
- data/processed/cv_release_20261113/training_replay/result.json

Six mask, four CNN and four geometry/statistics tests passed. An upstream Rasterio/Affine deprecation warning was emitted; no test failed. The clean extracted-package replay record is retained alongside the local candidate, not claimed as a fresh operating-system dependency install.
