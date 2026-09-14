"""Recompute named decoded-RGB PDF pairs from the published evidence tree."""
import argparse,hashlib,itertools,json
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence-root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();root=args.evidence_root;rows=[]
for version in ('3','4'):
    for camera in ('bern-urban-z12-light','geneva-urban-z14-light'):
        for dpi in (96,150,192):
            files={}
            for mode,prefix in (('pdfs-control','unwrapped'),('pdfs-trace','traced')):
                for suffix,state in (('','initial'),('-repeat','repeat')):
                    files[prefix+'_'+state]=Path(version)/camera/mode/f'pdf{dpi}{suffix}.png'
            pairs=[]
            for (left,lf),(right,rf) in itertools.combinations(files.items(),2):
                a=Image.open(root/lf).convert('RGB');b=Image.open(root/rf).convert('RGB')
                assert a.size==b.size==(1280,900)
                diff=ImageChops.difference(a,b)
                pair=dict(left=left,right=right,left_file=lf.as_posix(),right_file=rf.as_posix(),left_sha256=hashlib.sha256((root/lf).read_bytes()).hexdigest(),right_sha256=hashlib.sha256((root/rf).read_bytes()).hexdigest(),changed_pixels=sum(x!=(0,0,0) for x in diff.getdata()),normalized_mae=sum(ImageStat.Stat(diff).mean)/3/255,bbox=diff.getbbox())
                pairs.append(pair)
            rows.append(dict(runtime=version,camera=camera,pdf_export_dpi=dpi,pairs=pairs))
args.output.write_text(json.dumps(dict(method='Every unordered pair of the four published fixed96DPI Poppler RGB rasterizations; count a pixel once if any RGB channel differs. Filenames and SHA256 identify the exact operands.',rows=rows),indent=2)+'\n')
print('Verified',len(rows),'cells /',sum(len(row['pairs']) for row in rows),'named pairs')
