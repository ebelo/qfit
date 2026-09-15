"""Compare final-head road-name artifacts with the retained candidate evidence."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image
import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def difference(a, b):
    x = np.asarray(Image.open(a).convert('RGB'), dtype=np.int16)
    y = np.asarray(Image.open(b).convert('RGB'), dtype=np.int16)
    assert x.shape == y.shape
    d = np.abs(x - y)
    return {'changed_pixels': int(np.any(d, axis=2).sum()),
            'max_channel_delta': int(d.max()),
            'normalized_mae': float(d.mean() / 255)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--historical', type=Path, required=True)
    parser.add_argument('--final', type=Path, required=True)
    args = parser.parse_args()
    png, pdf = [], []
    for major in ('3', '4'):
        for folder in sorted((args.final / major).glob('*/after')):
            camera = folder.parent.name
            old = args.historical / major / camera / 'after'
            names = ('qgis.png', 'labels.json', 'runtime.json')
            row = {'runtime': major, 'camera': camera,
                   'comparisons': {n: {'historical': f'{major}/{camera}/after/{n}',
                                       'final': f'final-head/{major}/{camera}/after/{n}',
                                       'historical_sha256': digest(old / n),
                                       'final_sha256': digest(folder / n),
                                       'byte_identical': (old / n).read_bytes() == (folder / n).read_bytes()}
                                   for n in names}}
            row.update(difference(old / 'qgis.png', folder / 'qgis.png'))
            png.append(row)
        for folder in sorted((args.final / major).glob('*/pdf-after')):
            camera = folder.parent.name
            for path in sorted(folder.glob('*.pdf')):
                subprocess.run(['pdftoppm', '-r', '96', '-png', '-singlefile',
                                str(path), str(path.with_suffix(''))], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            old = args.historical / major / camera / 'pdf-after'
            row = {'runtime': major, 'camera': camera,
                   'historical_after_vs_final': difference(old / 'pdf150.png', folder / 'pdf150.png'),
                   'final_repeat': difference(folder / 'pdf150.png', folder / 'pdf150-repeat.png'),
                   'context_identical': (old / 'pdf150-context.json').read_bytes() == (folder / 'pdf150-context.json').read_bytes(),
                   'supporting_png_identical': (old / 'qgis.png').read_bytes() == (folder / 'qgis.png').read_bytes(),
                   'operands': {n: {'historical': f'{major}/{camera}/pdf-after/{n}',
                                    'final': f'final-head/{major}/{camera}/pdf-after/{n}',
                                    'historical_sha256': digest(old / n),
                                    'final_sha256': digest(folder / n)}
                                for n in ('pdf150.png', 'pdf150-repeat.png', 'qgis.png')}}
            pdf.append(row)
    result = {'png_cells': png, 'pdf_cells': pdf,
              'scope': 'Fresh final-head PNG identity and repeated PDF150 raster comparison at96DPI; no PDF-file identity, full-atlas or desktop claim.'}
    (args.final / 'render-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    assert len(png) == 34 and len(pdf) == 4
    print(json.dumps({'png_cells': len(png), 'all_png_bytes_identical': all(r['comparisons']['qgis.png']['byte_identical'] for r in png),
                      'all_labels_identical': all(r['comparisons']['labels.json']['byte_identical'] for r in png),
                      'all_runtime_identical': all(r['comparisons']['runtime.json']['byte_identical'] for r in png),
                      'pdf_cells': pdf}, indent=2))


if __name__ == '__main__':
    main()
