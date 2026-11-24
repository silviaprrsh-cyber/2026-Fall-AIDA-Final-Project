# Static fallback: Red Deer River viewer

**Synthetic demonstration only. These are not live river observations or verified flood predictions.**

Use this page if the local viewer is unavailable. The values below were reproduced offline using the deployment service's synthetic input generator and frozen V4 weights with the source-only adapter. The fixed mock issue time was **2026-11-20 03:42:15 UTC**. No provider or database was queried.

## Inputs shown in the viewer / 客户端显示的输入

| Input | Synthetic value | Observation time (UTC) |
| --- | ---: | --- |
| Dickson Dam (05CB007) | 50.180 m³/s | 03:40 |
| Little Red Deer (05CB001) | 7.828 m³/s | 03:40 |
| Medicine River (05CC007) | 2.968 m³/s | 03:40 |
| Red Deer (05CC002) | 69.900 m³/s | 03:40 |
| Red Deer Regional Airport rain | 0.0 mm | 02:00–03:00 completed hour |

The viewer displays the terminal gauge reading as an observation. Showing it on the screen does not mean it serves as an input to the source-only depth estimates.

## P06 terminal depth proxy / 末站水深代理

| Group | Valid time (UTC) | Complete synthetic inputs | Exact 03:40 Little Red Deer input removed |
| --- | --- | --- | --- |
| Current | 03:40 | 1.237 m | 1.237 m |
| +3 hours | 06:40 | 1.225 m | 1.225 m |
| +9 hours | 12:40 | 1.228 m | Unavailable |

In the second scenario the Little Red Deer tile can show its older **03:35** reading (**7.833 m³/s**), but that reading cannot stand in for the exact slot needed by the +9 h estimate. All +9 h estimates become unavailable, not zero. This is software-behaviour evidence, not validation of lead time or accuracy. The displayed P06 proxy is not measured field depth.

**中文提示：** 这是固定时刻的合成演示结果。移除 Little Red Deer 的 03:40 读数后，显示区仍可展示 03:35 的旧读数，但 +9 小时所需的精确时点没有收到，因此该组全部不可用，不能填零。此表不证明实际预报精度或预警提前量。

References: [Server demo guide](../courses/AIDA-2156/deployment/server/README.md) · [Viewer guide](../courses/AIDA-2156/deployment/client/README.md) · [Presentation notes](CLASS-PRESENTATION-NOTES.md) · [中文讲稿](CLASS-PRESENTATION-NOTESCN.md).
