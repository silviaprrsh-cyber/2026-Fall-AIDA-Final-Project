# Red Deer River Research Receiver for Windows

**COURSE DEMO ONLY. Do not use this receiver for actual flood forecasts, warnings, emergency response, evacuations, river operations, or other safety decisions.**

## Start the receiver

1. Double-click the standalone **RedDeerRiver.exe**; nothing needs to be extracted. The optional **RedDeerRiver-Client-Windows.zip** contains the same EXE and this English guide. Do not use the private server ZIP as a client; it is only for deployment operators. The program was tested on Windows 11 with the built-in .NET Framework 4.8/4.8.1. There is no Python, installer, or additional app dependency. The executable is unsigned; on a managed computer, follow your administrator’s software approval rules.
2. If the service is on the same computer on its default port, leave the address at `http://127.0.0.1:8765`. If it is in the cloud or on another computer, enter the service address in **Server base URL** and select **Connect**. The same EXE works for both.
3. The client refreshes automatically every 60 seconds. Use **Refresh now** for an immediate check. No client rebuild is needed when the host or port changes. The backend has its own provider collection schedule.

### Where to change the address or port

| Service address | What to enter in **Server base URL** |
| --- | --- |
| Local service, default port 8765 | `http://127.0.0.1:8765` |
| Local service on a different port, for example 8780 | `http://127.0.0.1:8780` |
| Private remote service, standard HTTPS port 443 | `https://host.example` |
| Private remote service, custom HTTPS port 8443 | `https://host.example:8443` |

The receiver appends the fixed read-only route `/api/v1/snapshot` for you. Do not type the route, credentials, query strings or fragments into the field. `host.example` is a placeholder, not a configured host. Remote services require HTTPS with a valid certificate. Plain HTTP is permitted on local loopback only. Redirects are not followed. The public-facing or private HTTPS proxy port and the loopback backend port are separate; use the TLS endpoint provided by the operator. Changing the field does not change any server, proxy or database configuration.

For an operator-managed default, set the client-process environment variable `RDR_SERVER_URL` before launching. If the operator requires a bearer token, use the approved secret channel and provide it via the client-process environment variable `RDR_API_TOKEN`, never the URL or chat. The app does not store or display the token. Its token is used only at the startup URL; to authenticate to a different host or port, close the app and launch with that service's URL and token in a new process.

## What the receiver shows

- **Observed river discharge (m³/s):** the latest available reading and its UTC observation timestamp for Dickson Dam Tunnel Outlet (05CB007), Little Red Deer River near the Mouth (05CB001), Medicine River near Eckville (05CC007), and Red Deer River at Red Deer (05CC002). These latest observations are shown separately from the older records used by the model.
- **Regional airport precipitation (mm):** Red Deer Regional A (3025484), a single station, not full-basin rainfall. The provider, accumulation period and observation, period-end and retrieval times are shown when available.
- **Current time:** estimated depth at the current target time from routed, lagged records, not measured depth.
- **+3 hours / +9 hours:** experimental future-target depth estimates only when all source values required by the chosen route were available at issuance. In particular, +9 hours may need the current-grid Little Red Deer River reading; if it was not available at issuance, no model number is shown for that target. Travel time and source latency limit the possible horizon. No future upstream discharge or rainfall is guessed or filled in for projections; these tabs are not verified flood-forecast lead times.
- **P01–P05** are unverified latent intermediate values, not measured depths. **P06** is a terminal, gauge-stage-derived water-depth proxy, not surveyed depth. Each tab shows its own UTC target and generated time, separate from the service snapshot and receiver contact timestamps.

**DEMO** uses synthetic measurements. **LIVE** means data retrieved from providers, not a guarantee of timeliness or validity. An actual reported zero is numeric; **Missing**, **Unavailable**, or a dash is not zero. **Stale** marks a late provider record. **Cached** means old values are retained after a failed request or were served from a stale/unavailable backend; they are not current. If no prior data are available, the receiver shows blanks and an English connection or availability message.

## If the receiver cannot connect

Check the address and the service port. For local use, start the companion server if it is not running. For remote use, check the private endpoint, its TLS certificate and any required authorization with the server operator. If a connection succeeds but some estimates are unavailable, inspect the status and the reason in the relevant tab; do not replace missing measurements with zero.
