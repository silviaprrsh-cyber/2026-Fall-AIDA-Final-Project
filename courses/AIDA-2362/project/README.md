# project

Course code or run results for courses/AIDA-2362/project. See the course README for purpose, inputs, commands and limitations.

## Project modification history — 2026-11-04 (verified 2026-11-05)

The active movetest reach now ends at Red Deer station 05CC002. Retain P01–P05; remove P06–P11 and downstream Blindman/Waskasoo map inputs. The selected project data provide no comparable downstream observation constraint to validate the continuation to P11. This reduction limits unsupported extrapolation; it does not establish accuracy at retained targets. The filename `dickson_to_joffre.qgz` is retained for compatibility, but its layers and displayed endpoint now use 05CC002.

Source archives, previous model results and satellite acquisitions are retained. At the 2026-11-04 scope change, the map exports still showed the prior Joffre extent. The 2026-11-08 [presentation PDF](../outputs/Overhead%20view.pdf) and [PNG preview](map_overview.png) show the current 05CC002 scope; the [prior Joffre PDF](../data/processed/scope_history/Overhead_view_Joffre.pdf) and earlier checks remain historical evidence. Current GIS checks are `courses/AIDA-2362/data/reports/scope_05CC002.json` and `qgis_scope_05CC002.json`. The model already ends at 05CC002: its M06 link from P05 to the validation station remains; M06 is not prediction point P06. This map update does not retrain the model or replace PostgreSQL snapshots.
