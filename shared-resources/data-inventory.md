# Shared data inventory

Snapshot reviewed 2026-11-08. Counts are archived evidence, not live availability. Full raw archives remain local and ignored.

| Input | Location | Identity / use | Limits |
|---|---|---|---|
| ECCC Wateroffice unit observations | `courses/AIDA-2156/data/processed/model_unit_history/20261103T070414Z/` | 1,350,764 parameter records; 95,053 screened candidate origins; UTC observation time, station, parameter, quality and provenance. | Not independent samples; revisions and missing periods; daily archive is backup only. |
| ECCC water/weather responses | `courses/AIDA-2156/data/sources/` | Source-specific originals; the dated ETL snapshot had 6,572 water rows and 927 weather rows. | This ETL snapshot differs from the unit-history training dataset. Missing rainfall is not zero. |
| Alberta flood surveys / NRCan river geometry | `courses/AIDA-2362/data/sources/` and `courses/AIDA-2362/project/` | Current map has 229 section lines and four selected river features. | Source CRS and vertical datum must be retained per layer; no universal gauge-zero conversion verified. |
| Sentinel-2 | `courses/AIDA-2154/data/processed/satellite_history/` | 955 historical rasters; active `dickson_to_05CC002/image_index.json` selects 775 and flags 389 candidates. | Apply active mask; clouds/ice/invalid pixels and 10 m scale constrain CV. |
| Derived PostgreSQL views | `shared-resources/config/postgres_dataset.json` | Dataset `0f36881e431d09661a2009558431f482955e6e4384dd37a10a2340c9e8f1d57b`; 60/20/20 and 80/20 candidate views. | Local service not bundled; arrival alignment reduces usable counts; old models are historical. |

Exact input hashes are retained in course validation reports and acquisition metadata. Permission conditions are summarized in `provenance-and-permissions.md`; an inventory is not redistribution authorization.

## CV inventory update 2026-11-13

The dated archive windows above remain stage records. The current independent CV database registers 1,442 source image files and 2,322 point samples dated 2016-05-02 through 2026-11-04, with irregular coverage. The frozen train/validation/test counts are 708/169/132; the final test acquisition is 2026-10-20. Source identity and permissions are documented in the [CV data record](../courses/AIDA-2154/docs/data-permission-selection.md). The database replay made no new satellite API requests.

## Retained V4 and deployment data

The retained AIDA 2156 V4 60/20/20 training View supplied 146,319 rows after View-level screening, distinct from all counts above. Its fixed historical test has 27,256 rows. See [V4 sources](../courses/AIDA-2156/docs/DATA_SOURCES.md) and [data processing](../courses/AIDA-2156/docs/DATA_PIPELINE.md) for selection, gauge-depth proxy and lookback. The stage label is not measured depth; provider issue-time availability is unproven for the archived training data. CV widths and lake-level features are not part of frozen V4.

The separate [research deployment](../courses/AIDA-2156/deployment/server/README.md) ingests four station flow feeds and one airport hourly rainfall feed into a dedicated PostgreSQL schema, not the historical fitting View. Local tests do not establish all feeds are currently available or any package is running in the cloud. The display is not for flood alerts or decisions.
