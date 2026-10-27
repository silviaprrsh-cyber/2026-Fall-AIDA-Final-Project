"""Inspect copied Sentinel samples locally without acquisition or model training."""
from project_paths import resolve_runtime_path, archive_relative
import json
import numpy as np
import rasterio
from project_paths import DATA, WORKSPACE


def summarize(path):
    with rasterio.open(path) as src:
        quality = src.read()
        if quality.shape[0] < 2:
            raise ValueError('Expected SCL and dataMask bands')
        valid = quality[1] == 1
        return {'file': path.relative_to(WORKSPACE).as_posix(), 'crs': str(src.crs),
                'width': src.width, 'height': src.height, 'pixel_size': list(src.res),
                'valid_pixels': int(valid.sum()), 'total_pixels': int(valid.size),
                'cloud_shadow_pixels': int((valid & np.isin(quality[0], [3, 8, 9, 10])).sum()),
                'usable_data_present': bool(valid.any()),
                'note': 'Provider classification only; not trained project segmentation or accuracy evidence.'}


def main():
    rows = [summarize(p) for p in sorted((resolve_runtime_path(DATA/'sources/copernicus_sentinel2/raw/satellite')).glob('*/quality.tif'))]
    if not rows: raise SystemExit('No local satellite samples found')
    output = WORKSPACE/'courses/AIDA-2154/outputs/archive_inspection.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
