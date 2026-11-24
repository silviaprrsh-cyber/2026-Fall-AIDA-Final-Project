# docs

**Standalone course report (Word):** [English](eda-project-report.docx) · [中文版](eda-project-reportCN.docx)

Use this folder only for the evidence described in the current D2L instructions for this course. Add a short note here when you place files in the folder. Do not add restricted data or credentials.

## Red Deer River: final V4 documentation

[中文索引](READMECN.md) · [Course README](../README.md)

> **Research only. Do not use V4 for real flood warnings, emergency response or safety decisions.** The final historical test does not justify those uses. The frozen V4 60/20/20 checkpoint is the study reference. The optional later Dickson guard and the matching/weather refits are separately documented experiments, not replacements.

| Topic | English | 中文 |
|---|---|---|
| Raw sources, units, keys and archive evidence | [Data sources](DATA_SOURCES.md) | [数据来源与格式](DATA_SOURCESCN.md) |
| Split dates, processing rationale and data flow | [Data pipeline](DATA_PIPELINE.md) | [数据划分与处理流程](DATA_PIPELINECN.md) |
| Experiments, metrics, V4 choice and limitations | [Model experiments](MODEL_EXPERIMENTS.md) | [模型实验](MODEL_EXPERIMENTSCN.md) |
| Later input and matching improvement attempts | [Data improvement](DATA_IMPROVEMENT.md) | [数据改进实验](DATA_IMPROVEMENTCN.md) |

The [frozen-route](frozen-route-experiment.md) and [tail-model](tail-model-experiment.md) reports are earlier supporting experiments; their different targets, protocols or cohorts should not be used as final V4 metrics.

## Current package: Windows server and receiver

The local release files are the [private Windows server ZIP](../deployment/dist/RedDeerRiver-Server-Windows-Private.zip) and the [single-file Windows client EXE](../deployment/dist/RedDeerRiver.exe). See the [server operator guide](../deployment/server/README.md), [client guide](../deployment/client/README.md) and [v1 HTTP contract](../deployment/server/WIRE.md). These are local build artifacts, not publicly hosted downloads. The server and a dedicated managed PostgreSQL database are **prepared for cloud deployment, not deployed**. Keep the server ZIP private; it contains the pinned model.

The server starts collecting on its own. It fetches official ECCC observations, writes to its isolated PostgreSQL schema, and publishes a read-only `/api/v1/snapshot` (initial 84-hour fetch, then 3-hour overlap every 10 minutes by default). The client opens by double-click without Python or a terminal; enter a server **base URL** in its UI, without recompiling. The internal HTTP listener defaults to `127.0.0.1:8765` (`--port` or `RDR_PORT`); the external HTTPS proxy and the database have independent ports. Only the server connects to PostgreSQL.

The viewer distinguishes four observed station flows and the airport rain observation from modeled depths at the current target bin, +3 h and +9 h. P01–P05 are unverified internal model outputs; P06 is a terminal water-depth proxy. +9 h requires the exact Little Red Deer observation for the current five-minute grid slot to have been received at issuance; a late or missing input means unavailable, not an estimated upstream discharge. Synthetic demo mode is separate from live observations. The package uses frozen V4 weights with a source-only adapter, not the historical training View, and is **not for real flood warning, response or safety decisions**.

## D2L delivery and demonstration

[Submission manifest](../submission-manifest.txt), [runtime](../requirements-eda.lock.txt), and [clean replay](../output/clean-copy-replay.txt). These document a local EDA replay, not an assembled upload. The optional V4 demonstration is separate.
