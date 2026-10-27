# `datamart_notifications.py`

File: `API/datamart_notifications.py`

## Purpose

Anonymous Datamart file notifications; no directory polling or URL following.

## Defined functions/classes

`DatamartNotifications`

## Direct imports

- `__future__: annotations`
- `pika`
- `rdr.storage: log, now`
- `re`
- `ssl`
- `threading`
- `uuid: uuid4`

## Calls

`log`, `now`, `pika.BlockingConnection`, `pika.ConnectionParameters`, `pika.PlainCredentials`, `pika.SSLOptions`, `re.search`, `self.accept`, `self.connected.clear`, `self.connected.is_set`, `self.connected.set`, `self.pending.add`, `self.pending.remove`, `self.ready.is_set`, `self.ready.set`, `self.ready.wait`, `self.stop.is_set`, `self.stop.wait`, `self.thread.join`, `self.thread.start`, `ssl.create_default_context`, `threading.Event`, `threading.Lock`, `threading.Thread`, `uuid4`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/datamart_notifications.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
