from pathlib import Path
import hashlib,itertools,json,subprocess
from PIL import Image,ImageChops,ImageDraw,ImageFont
P=Path(__file__).resolve().parent
rows=[]
for v in (3,4):
 root=P/f'{v}-calibration'
 for pdf in root.glob('*.pdf'):
  subprocess.run(['pdftoppm','-r','96','-png','-singlefile',str(pdf),str(pdf.with_suffix(''))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for zoom in (12.25,12.9,13,13.1):
  for kind in ('png','pdf'):
   for dpi in (96,150,192):
    names=[f'z{zoom}-{kind}-{dpi}-{mode}-{rep}.png' for mode in ('plain','trace') for rep in (0,1)]
    ims=[Image.open(root/n).convert('RGB') for n in names]
    for im in ims:
     pixels=list(im.getdata());red=sum(r>2*g and r>2*b for r,g,b in pixels);blue=sum(b>2*r and b>2*g for r,g,b in pixels);green=sum(g>2*r and g>2*b for r,g,b in pixels)
     assert red>10 and green>10
     assert (blue>10)==(zoom>13),(v,zoom,dpi,kind,blue)
    for (n1,i1),(n2,i2) in itertools.combinations(zip(names,ims),2):
     diff=ImageChops.difference(i1,i2);count=sum(pixel!=(0,0,0) for pixel in diff.getdata())
     rows.append(dict(version=v,source_zoom=zoom,kind=kind,dpi=dpi,left=n1,right=n2,left_sha256=hashlib.sha256((root/n1).read_bytes()).hexdigest(),right_sha256=hashlib.sha256((root/n2).read_bytes()).hexdigest(),changed_pixels=count))
     assert count==0,rows[-1]
 font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
 out=Image.new('RGB',(1920,525),'white');d=ImageDraw.Draw(out)
 for i,z in enumerate((12.9,13,13.1)):
  out.paste(Image.open(root/f'z{z}-pdf-150-plain-0.png'),(i*640,45));d.text((i*640+12,12),f'Rejected QGIS {v} calibration / z{z} / PDF150',font=font,fill='black')
 out.save(P/f'qgis{v}-calibration-triplet.png')
(P/'calibration-pairs.json').write_text(json.dumps(rows,indent=2)+'\n')
print('288 exact named pairs; all repeated/traced pixels identical; blue incorrectly absent at nominal z13')
