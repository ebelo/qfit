from pathlib import Path
import hashlib,itertools,json,subprocess
from PIL import Image,ImageChops,ImageDraw,ImageFont
P=Path(__file__).resolve().parent
rows=[]
for v in (3,4):
 root=P/f'{v}-final'
 report=json.loads((root/'report.json').read_text())
 for pdf in root.glob('*.pdf'):
  subprocess.run(['pdftoppm','-r','96','-png','-singlefile',str(pdf),str(pdf.with_suffix(''))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for kind in ('png','pdf'):
  for dpi in (96,150,192):
   names=[f'{kind}-{dpi}-{mode}-{rep}.png' for mode in ('plain','trace') for rep in (0,1)]
   ims=[Image.open(root/n).convert('RGB') for n in names]
   for im in ims:
    pixels=list(im.getdata());red=sum(r>2*g and r>2*b for r,g,b in pixels);blue=sum(b>2*r and b>2*g for r,g,b in pixels);green=sum(g>2*r and g>2*b for r,g,b in pixels)
    assert red>10 and green>10,'Blank/missing persistent features'
    assert (blue>10)==(v==4 and dpi>96),'Native zoom rule activation mismatch'
   for (name1,im1),(name2,im2) in itertools.combinations(zip(names,ims),2):
    diff=ImageChops.difference(im1,im2);count=sum(pixel!=(0,0,0) for pixel in diff.getdata())
    row=dict(version=v,kind=kind,dpi=dpi,left=name1,right=name2,left_sha256=hashlib.sha256((root/name1).read_bytes()).hexdigest(),right_sha256=hashlib.sha256((root/name2).read_bytes()).hexdigest(),changed_pixels=count)
    rows.append(row)
    assert count==0,row
 for kind in ('pdf','png'):
  ims=[Image.open(root/f'{kind}-{dpi}-plain-0.png').convert('RGB') for dpi in (96,150,192)]
  if kind=='png':ims=[im.resize((640,480),Image.Resampling.LANCZOS) for im in ims]
  out=Image.new('RGB',(1920,525),'white');draw=ImageDraw.Draw(out);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
  for i,(dpi,im) in enumerate(zip((96,150,192),ims)):
   out.paste(im,(i*640,45));draw.text((i*640+12,12),f'QGIS {v} synthetic {kind.upper()} / {dpi} DPI',font=font,fill='black')
  out.save(P/f'qgis{v}-{kind}-modes.png')
(P/'pair-audit.json').write_text(json.dumps(rows,indent=2)+'\n')
print('72 exact named pairs; all plain/traced/repeated pixels identical; expected blue-rule activation verified')
