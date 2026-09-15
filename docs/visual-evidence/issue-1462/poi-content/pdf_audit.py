"""Rasterize actual PDFs at96DPI and report explicit named repeat pairs."""
import collections,json,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parent;rows=[];placed=[]
for v in ('3','4'):
 for camera in ('cairo-museum-z14','geneva-streets-z18-light'):
  for variant in ('before-pdf','after-pdf'):
   folder=P/v/camera/variant
   for name in ('pdf150','pdf150-repeat'):
    pdf=folder/(name+'.pdf');png=folder/(name+'.png')
    subprocess.run(['pdftoppm','-r','96','-singlefile','-png',str(pdf),str(folder/name)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['pdftotext','-layout',str(pdf),str(folder/(name+'.txt'))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    assert Image.open(png).size==(1280,900),Image.open(png).size
   a=np.asarray(Image.open(folder/'pdf150.png').convert('RGB')).astype(float)
   b=np.asarray(Image.open(folder/'pdf150-repeat.png').convert('RGB')).astype(float)
   rows.append({'runtime':v,'camera':camera,'variant':variant,'a':str((folder/'pdf150.png').relative_to(P)),
                'b':str((folder/'pdf150-repeat.png').relative_to(P)),'changed_pixels':int(np.any(a!=b,axis=2).sum()),
                'max_channel_delta':int(np.abs(a-b).max()),'normalized_mae':float(np.abs(a-b).mean()/255),
                'context':json.loads((folder/'pdf150-context.json').read_text())})
   labels=json.loads((folder/'placed-labels.json').read_text());groups=collections.defaultdict(list)
   for label in labels:groups[label['provider_id']].append(label['text'])
   placed.append({'runtime':v,'camera':camera,'variant':variant,'scope':'PNG companion actual position records; curved labels may emit many records with the same full text. Counts are not label counts. Not PDF text extraction or native/source feature-ID equivalence',
                  'groups':dict(groups),'position_record_count':len(labels)})
  panel=Image.new('RGB',(1140,335),'white');draw=ImageDraw.Draw(panel)
  for i,(path,label) in enumerate([(P/'reference-mercator'/camera/'mapbox.png','Mapbox PNG reference (context)'),(P/v/camera/'before-pdf/pdf150.png',f'QGIS{v} PDF150 Before @96DPI'),(P/v/camera/'after-pdf/pdf150.png',f'QGIS{v} PDF150 After @96DPI')]):
   panel.paste(Image.open(path).crop((900,570,1280,870) if camera=='geneva-streets-z18-light' else (450,310,830,610)),(i*380,35));draw.text((i*380+8,10),label,fill='black')
  panel.save(P/f'{camera}-qgis{v}-pdf150-crop.png')
(P/'pdf-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
(P/'placed-label-audit.json').write_text(json.dumps(placed,ensure_ascii=False,indent=2)+'\n')
for row in rows:print(row['runtime'],row['camera'],row['variant'],'repeat_changed_pixels',row['changed_pixels'])
for row in placed:print('placed',row['runtime'],row['camera'],row['variant'],{k:len(x) for k,x in row['groups'].items()})
