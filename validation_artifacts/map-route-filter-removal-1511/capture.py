import json,sys
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,'/tests_directory')
sys.path.insert(0,'/tests_directory/qfit')
from qgis.core import QgsApplication,Qgis
from qgis.PyQt.QtCore import QDate,QT_VERSION_STR,PYQT_VERSION_STR
from qgis.PyQt.QtWidgets import QStyleFactory
from qfit.tests.qgis_app import get_shared_qgis_app
from qfit.tests.test_qgis_smoke import _FakeIface,_FakeQSettings
from qfit.configuration.application.settings_service import SettingsService
from qfit.configuration.infrastructure.credential_store import InMemoryCredentialStore
from qfit.ui.dockwidget_dependencies import build_dockwidget_dependencies
from qfit.qfit_dockwidget import QfitDockWidget
app=get_shared_qgis_app(QgsApplication)
app.setStyle(QStyleFactory.create('Fusion'))
settings=SettingsService(qsettings=_FakeQSettings(),credential_store=InMemoryCredentialStore())
iface=_FakeIface()
dock=QfitDockWidget(iface,dependencies=replace(build_dockwidget_dependencies(iface),settings=settings))
dock.dateFromEdit.setDate(QDate(2026,5,1));dock.dateToEdit.setDate(QDate(2026,5,31))
dock.activityTypeComboBox.setOptions(['All','Walk','Hike','Run'])
dock.activityTypeComboBox.setSelectedTypes(['Walk','Hike'])
group=dock.filterGroupBox
group.setParent(None)
group.setFixedSize(420,280)
group.show();app.processEvents()
path=Path('/evidence')/f'qgis{sys.argv[1]}-{sys.argv[2]}.png'
assert group.grab().save(str(path))
print(json.dumps({'image':path.name,'qgis':Qgis.QGIS_VERSION,'qt':QT_VERSION_STR,'pyqt':PYQT_VERSION_STR,'dimensions':[420,280],'route_selector_present':hasattr(dock,'detailedRouteStatusComboBox'),'scope':'Actual dock Map filters group detached for matched panel capture; no map render or Windows UI claim'}))
group.close();dock.close()
