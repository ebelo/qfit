"""Verify immutable named PDF viewing-raster operands and recompute their metrics."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence', type=Path, required=True)
args = parser.parse_args()
root = args.evidence.resolve()
report = json.loads((root / 'pdf-audit.json').read_text())
for row in report['pairs']:
    images = []
    for operand in ('a', 'b'):
        path = (root / row[operand]).resolve()
        assert path.is_relative_to(root), 'Operand escapes evidence directory'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row[operand + '_sha256'], row[operand]
        images.append(Image.open(path).convert('RGB'))
    assert images[0].size == images[1].size
    difference = ImageChops.difference(*images)
    changed = sum(pixel != (0, 0, 0) for pixel in difference.getdata())
    mae = sum(ImageStat.Stat(difference).mean) / 3 / 255
    maximum = max(channel[1] for channel in difference.getextrema())
    assert changed == row['changed_pixels']
    assert abs(mae - row['normalized_mae']) < 1e-12
    assert maximum == row['max_channel_delta']
print(json.dumps({'verified_named_pairs': len(report['pairs']), 'viewing_dpi': report['viewing_dpi']}))
