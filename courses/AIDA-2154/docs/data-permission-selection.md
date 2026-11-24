# Data authority, selection and attribution
Reviewed 2026-11-13. This is the CV-specific record, not approval to distribute unrelated survey archives.

## Selected inputs and source identity
- Sentinel-2 L2A from Copernicus Data Space Ecosystem (CDSE), acquired previously through the authenticated processing API. No acquisition was performed for the release work.
- Nine fixed GIS points: P01-P05 and 05CB001, 05CB007, 05CC002, 05CC007. The local QGIS layers defined location selection; the package does not redistribute government survey originals or the full GIS project.
- Native 10 m RGB/NIR crops, 61 x 61 pixels. SCL quality is a resampled 20 m product, not independent reference truth. Values are reflectance / 10000, clipped to [0,1] for the saved dataset.
- 2,322 automatic masks were screened, then same-point/day duplicates and boundary dates removed. Final 1,009 samples: 708/169/132 train/validation/test. The selection summary and dataset manifest contain actual dates, rejection counts, source paths and SHA-256 values.
- The saved dataset is derived imagery plus automatic labels, not a personally collected recording. Visual checks identified errors, but image detail was insufficient for reliable boundary verification and independent reference masks.
- Earliest retained training date is 2016-05-02; last retained test date is 2026-10-20. These dates supersede the old 2025-2026 acquisition-only description.

## Permission check
Official CDSE terms, section 3, distinguish Sentinel data from other portal content:
https://dataspace.copernicus.eu/terms-and-conditions
The linked European Commission legal notice permits reproduction, distribution and modification of Sentinel data, subject to its terms and attribution, without a suitability warranty:
https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice

Attribution for derived crops and figures: Contains modified Copernicus Sentinel data [2016-2026].
This finding applies to Sentinel data, not arbitrary CDSE website graphics, third-party datasets, account records or credentials. Links were read on 2026-11-13; no new agreement was accepted. The course repository records the river proposal as approved as submitted. The supplied October 4 feedback recommends bounded historical work and treats unvalidated CV as an optional extension; no later approval is invented.

## Package boundary and privacy
The local candidate includes the frozen derived arrays needed to replay CNN evaluation, model, manifests, code and selected evidence. It does not include authentication files, API receipts, downloaded source archives, private correspondence, PostgreSQL data or Alberta survey originals. Derived hydrometric comparisons are retained as reported analytical evidence; raw hydrometry and GIS regeneration are outside the minimal replay package. No external upload or D2L submission has occurred. The owner still checks final D2L scope and permissions before submission.

Human-approved labels remain unavailable. Clear-looking imagery does not establish true river width. Lack of sufficient clarity/resolution makes the current output unsuitable for the prediction model.

## Hydrometric analysis attribution
The retained derived comparison uses Water Level and Flow observations from Environment and Climate Change Canada (Environment Canada), Wateroffice: https://wateroffice.ec.gc.ca/ . Source CSV identities are retained in the width summary. The official disclaimer permits copying/distribution with attribution, prohibits resale of bundled raw information, and warns that near-real-time records are preliminary: https://wateroffice.ec.gc.ca/disclaimer_info_e.html . General non-commercial reproduction conditions: https://www.canada.ca/en/transparency/terms.html . Read 2026-11-13. This classroom analysis is not an official Government of Canada product; no endorsement is implied. Raw station archives are not included in the candidate.
