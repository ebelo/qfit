import hashlib,json,sys
from pathlib import Path
sys.path[:0]=['/tests_directory','/tests_directory/qfit']
from qgis.core import QgsApplication,Qgis
from qgis.PyQt.QtCore import QT_VERSION_STR,PYQT_VERSION_STR
from qgis.PyQt.QtWidgets import QDialog,QFormLayout,QComboBox,QLabel
from tests.qgis_app import get_shared_qgis_app
from qfit.ui.widgets.activity_type_selector import ActivityTypeSelector
app=get_shared_qgis_app(QgsApplication)
app.setStyle('Fusion')
runtime=sys.argv[1]
root=Path('/evidence')/runtime
root.mkdir(exist_ok=True)
report={'runtime':runtime,'qgis':Qgis.QGIS_VERSION,'qt':QT_VERSION_STR,'pyqt':PYQT_VERSION_STR,
        'candidate_commit':'cb4b6ef5487f673022a88c9a546f8923773dde5d',
        'baseline_commit':'2d73f5584c4ad90b2ffc108e9af6408bf45e805b',
        'baseline_control':'Stock QComboBox, as declared by baseline qfit_dockwidget_base.ui; isolated control demonstration, not a full baseline dock capture.',
        'options':['All','Hike','Run','Walk'],'style':'Fusion','size':[420,120],
        'logical_dpi':app.primaryScreen().logicalDotsPerInch(),'captures':[]}
for role in ('before','after'):
    dialog=QDialog()
    dialog.setWindowTitle('Activity type filters')
    form=QFormLayout(dialog)
    selector=QComboBox(dialog) if role=='before' else ActivityTypeSelector(dialog)
    if role=='before':
        selector.addItems(report['options'])
        selector.setCurrentText('Hike')
    else:
        selector.setOptions(report['options'])
        selector.setSelectedTypes(['Hike','Walk'])
        assert selector.selectedTypes()==('Hike','Walk')
    form.addRow('Activity type' if role=='before' else 'Activity types',selector)
    form.addRow(QLabel('Choose types, then click Apply filters.'))
    dialog.resize(420,120)
    dialog.show()
    app.processEvents()
    for repeat in range(2):
        path=root/f'{runtime}-{role}-{repeat}.png'
        picture=dialog.grab()
        assert not picture.isNull() and picture.save(str(path))
        report['captures'].append({'file':path.name,'role':role,'repeat':repeat,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    if role=='after':
        selector.showPopup()
        app.processEvents()
        path=root/f'{runtime}-checkbox-popup.png'
        assert selector.view().window().grab().save(str(path))
        selector.hidePopup()
    dialog.close()
(root/'manifest.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='captures'}))
