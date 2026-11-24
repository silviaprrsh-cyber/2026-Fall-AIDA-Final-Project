# Red Deer River research snapshot server (Windows)

[中文](READMECN.md) · [HTTP contract](WIRE.md)

**Research only. Do not use any output for actual flood alerts, evacuation, emergency response or safety decisions.** The standalone server contains the unchanged V4 60/20/20 weights, pinned by SHA-256. Its source-only arrival adapter is deliberately different from the historical View, which depended on terminal history. Neither the adapter's current-time estimate nor either later projection has been validated for real floods. P01–P05 are the six-block cascade's unverified internal depth outputs under the **same** feature snapshot, not separate per-point forecasts or validated per-point arrival times. P06 is the 05CC002 terminal depth proxy, not an observed field depth. The observed terminal discharge is shown but never read by inference.

## What runs where

- **Windows cloud VM:** one long-running collector and read-only HTTP service. It polls the existing official ECCC GeoMet products in the background whether or not a client is connected: hydro discharge (05CB007 Dickson, 05CB001 Little, 05CC007 Medicine, 05CC002 Red Deer) and one hourly airport precipitation series (3025484).
- **Managed PostgreSQL 15+:** deployment-specific database and schema `rdr_live_v1`. Poll → validate/normalize → transactionally store observations → read strictly as-of observations from PostgreSQL → compute and persist a current snapshot. Historical source archives, historical Views and their tables are not used by this service. Duplicate facts keep the first receipt; revisions are separate. Do not backdate historical receipts into this live pipeline.
- **Client:** reads the server's HTTPS reverse-proxy URL, never PostgreSQL. No source archive, schema user, database password or model weights are given to the client. The private server ZIP contains the actual weights; do not serve or publish the ZIP/folder.

## Why this release is a ZIP, not Docker

The deployment target is a general-purpose Windows x64 VM. The private ZIP supplies the Python service files, the pinned V4 weights and the dependency list. Running the service directly avoids requiring a compatible Windows container runtime and a separate image build and distribution step. The ZIP is not a bundled runtime: the operator must install Python and the listed dependencies, configure the PostgreSQL connection and backend listener, and set up HTTPS for remote clients. A container would still need environment-specific configuration and secrets. The separate AIDA 2154 CV image bundles its offline inference dependencies, a different packaging need. If a target platform only supports containers or the course requires one, a separate V4 service image can be added later.

## Start locally in demo mode

Use **Windows x64 and Python 3.13**. Extract the private server ZIP so the package is `server/`. Run these commands from its parent directory, or use the verified repository virtual environment at equivalent paths.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
.\.venv\Scripts\python.exe -B -m server.service --mode demo --once
.\.venv\Scripts\python.exe -B -m server.service --mode demo --port 8765
```

`--once` exits after printing one JSON document. Normal mode polls on startup and then every **600 s** by default (configurable from 300 to 3,600 s). Keep the service open and use a second shell:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/healthz
Invoke-RestMethod http://127.0.0.1:8765/api/v1/snapshot
```

Demo uses explicitly synthetic station observations and a memory implementation of the deployment store; it never contacts PostgreSQL or ECCC. It runs the actual immutable weights. With complete synthetic inputs, 0 h, +3 h and +9 h are numeric. Demo observation times/values are not live environmental data.

## Configure the deployment database and service

1. Prepare a **new** database for this deployment with PostgreSQL 15 or newer. Use a dedicated, private endpoint or restricted network and separate migration/runtime roles. Do not aim the server at the existing project database. Allow the VM outbound HTTPS to `api.weather.gc.ca` and TCP/TLS to the configured PostgreSQL host/port. Enable synchronized system time.
2. Inject the database connection into the service account's private environment as **`RDR_DEPLOYMENT_DSN`**. Named fields include `host=<DNS name>`, `port=<provider port>`, `dbname=<dedicated DB>`, `user=<role>`, a secret/password as required, and **`sslmode=verify-full`**. Set `sslrootcert=<provider CA path>` in that DSN or **`RDR_DB_SSLROOTCERT`** separately. The host must match the certificate. Provider-specific equivalents must retain peer and hostname verification; the package does not downgrade to `require`, `prefer` or disabling SSL. Never place secrets in code, installers, task arguments, logs, Git or the client.
3. With the migration role once, run `.\.venv\Scripts\python.exe -B -m server.service --mode live --init-db`. This creates only the versioned schema, `observation_versions`, `current_snapshot` and their indexes, then exits. No feed starts. The migration role needs CREATE on the new database/schema. The runtime role needs CONNECT, USAGE on `rdr_live_v1`, SELECT/INSERT on `observation_versions`, and SELECT/INSERT/UPDATE on `current_snapshot`; if the policy/provider checks identity sequence access, grant USAGE only on `observation_versions_version_id_seq`. The runtime must not be the old project DB owner or a cloud superuser.
4. Switch secrets to the runtime role, optionally set **`RDR_API_TOKEN`** (24–256 characters in the Bearer alphabet; a URL-safe random token is recommended) via the approved secret manager, then launch `.\.venv\Scripts\python.exe -B -m server.service --mode live`. Poll interval: `RDR_POLL_SECONDS`; per-source HTTP timeout: `RDR_SOURCE_TIMEOUT`; port: `RDR_PORT`. Only localhost binding is accepted. Logs omit DSNs, secret values, authorization headers and raw provider responses.
5. For a receiving client on another machine, place a HTTPS reverse proxy on the same VM, forwarding only the allowed snapshot route and administrative health route as appropriate. Use a certificate the client trusts, client authorization (or VPN/IP restrictions) and rate limits; require authorization at the proxy and configure the service bearer token for defense in depth. Do not publicly expose the backend port or open PostgreSQL to clients. Health can return HTTP 503 before the first committed cycle or on backend failure. A running service can report a partial source snapshot without being ready to estimate depths.

## Where to change the port

| Port | Where to change it | Value used by the receiving client |
|---|---|---|
| Local server HTTP back end (default **8765**) | Pass `--port 8877` to `server.service`, or set the service environment variable `RDR_PORT=8877`. A command-line `--port` takes precedence. The back end binds only to `127.0.0.1`. | Same-machine demo: `http://127.0.0.1:8877`. For remote clients, update the reverse proxy's upstream to `http://127.0.0.1:8877`; clients need no URL change if the external address remains the same. |
| External HTTPS listener (normally **443**) | Change the listener's port in the VM's HTTPS reverse-proxy configuration. Keep its upstream pointed at the local back-end port. HTTPS with certificate verification and access control is required for remote clients; do not publish the raw back-end port. | Enter the HTTPS **base URL** in the receiving client, e.g. `https://server.example` on 443 or `https://server.example:8443` on 8443. No EXE rebuild is required. |
| PostgreSQL port (provider-specific; often **5432**) | Change `port=...` in the service's private `RDR_DEPLOYMENT_DSN` and maintain `sslmode=verify-full`. | None; the client never connects to PostgreSQL. |

For example, run `.\.venv\Scripts\python.exe -B -m server.service --mode demo --port 8877` and check `http://127.0.0.1:8877/healthz`. Restart the running service (or the Windows startup task) after changing its port or database settings; reload the HTTPS proxy if its listener or upstream changes. These are independent ports. Enter only the base URL in the client; do not append `/api/v1/snapshot` or `/healthz`. The **`/api/v1/snapshot`** path and required v1 fields retain their meaning for the same EXE. Only compatible additive v1 changes are appropriate; incompatible changes require a new API version. Verify the actual HTTPS URL and data response from the client network after deployment; this package was tested locally, not on a public endpoint.

## Continuity, startup and service recovery

On Windows Task Scheduler, the operator can create **one** startup task per deployed database: program is the deployment venv's `python.exe`; arguments are `-B -m server.service --mode live`; **Start in** is the package's parent directory. Use a dedicated non-admin service account, run whether logged on or not, do not start a second instance, enable restart after unexpected process failure, and make sure the account's secret injection is available on a non-interactive reboot. Do not put secrets in task arguments. Do not impose the default short maximum execution duration on a permanent task. Set a controlled log destination/rotation and monitor provider freshness, cycle age and instance health. This package does **not** register a local Windows service, alter firewall rules, set up a cloud account, or configure a public endpoint automatically.

Startup/restart requests **84 hours** of recent observations, sufficient only if all required hours/bins actually exist. Normal polls overlap the prior **3 hours**; repeated partial recovery triggers a bounded broader pull after about 12 failed-source cycles, while a full provider/DB outage backs off to at most 30 minutes per retry. The app keeps the last persisted snapshot and marks display values stale (default 1 h for flows, 3 h from the end of a rain bucket). Late/absent provider responses do not generate fake station readings. Once the snapshot age exceeds twice the normal interval plus one minute, cached depth estimates become unavailable. A service outage does not backfill periods outside the bounded recent window. Production monitoring and a retention policy for the dedicated DB should be set by the operator; this service does not purge historical observations automatically.

## What the three groups mean

- **0 h**: target is the current issuance timestamp rounded down to a five-minute UTC bin. Dickson/Little nominal propagation periods are **10h30 and 9h**. Medicine uses source-only prior-rise logic for 30–50h15 center travel and a ±3 h parcel-spread kernel. An incomplete Medicine candidate span or missing Little measurement stops the estimate. Dickson missing may be zero **inside this 0 h model** only and is traceable; the observed flow stays missing/null. Weather uses completed preceding source hours; missing historical rain is explicit zero fill for this group.
- **+3 h**: same algorithm and weights at the future validity bin, using only flow values and fully completed rain windows that were released/received at issuance. Required short-branch measured inputs and missing rain windows cannot be invented. The outputs are experimental; they are not a demonstration of real warning lead.
- **+9 h**: computed only when all required source measurements and completed rain windows were already available at issuance. The nominal 9 h Little Red Deer route requires its flow from the current five-minute grid slot. If publication or retrieval has not reached that slot, the estimate is **unavailable**. Projections depend on both river travel time and when the readings arrive; later upstream flow cannot be inferred from available observations. Missing flow is never replaced by zero or carried forward for a projection.

When tested on this Windows workstation, ECCC returned current-window Dickson and downstream observations plus older airport rain; the requested 80 h GeoMet test returned no usable Little or Medicine rows. This is an observed availability gap during that probe, **not** proof the stations are offline or zero, and it should produce unavailable depth values. The release checks below exercise the behavior without asserting persistent feed coverage.

## Verification

The checkout's automated tests exercise timing/provenance, no downstream influence or late input leakage, missing vs zero, stale/errors, HTTP/Bearer and repeated polling without any clients. Frozen-model demo uses the archived checkpoint hash. PostgreSQL schema initialization, as-of filtering, revisions and actual restart durability passed on a new isolated **Windows PostgreSQL 18.6** instance; no project DB or cloud DB was used. The local verification did not prove a real managed-DB TLS connection, every station's current availability or unattended cloud uptime.
