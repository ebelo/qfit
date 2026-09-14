"""Projection provenance and actual browser-capture behavior regressions."""
import copy
import json
import shutil
import subprocess
from pathlib import Path

import tempfile
import unittest

from tests import _path  # noqa: F401

from qfit.validation import mapbox_outdoors_comparison as comparison


def _node(script, payload):
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('Node.js is needed to execute the browser JavaScript regression')
    result = subprocess.run([node, '-e', script], input=json.dumps(payload),
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def _check_source_projection_and_context(preset, projection):
    source = {'version': 8, 'projection': {'name': 'globe'}, 'sources': {}, 'layers': []}
    original = copy.deepcopy(source)
    html = comparison.build_mapbox_gl_html(
        camera=next(iter(comparison.PRESETS[preset].cameras.values())),
        style_definition=source, reference_projection=projection)
    result = _node(r"""
const fs = require('fs'), vm = require('vm');
const html = JSON.parse(fs.readFileSync(0, 'utf8'));
let options; const events = {};
const context = {window: {devicePixelRatio: 2}, mapboxgl: {version: '3.10.0', Map: function(value) {
  options = value;
  return {on: (event, callback) => {events[event] = callback;}, once: () => {},
    getProjection: () => ({name: options.projection || 'globe'}),
    getCenter: () => ({toArray: () => [7.1, 46.2]}), getZoom: () => 5.25,
    getBearing: () => 0, getPitch: () => 0, getBounds: () => ({toArray: () => [[1,2],[3,4]]}),
    getCanvas: () => ({width: 1280, height: 900}), loaded: () => true,
    areTilesLoaded: () => true, queryRenderedFeatures: () => [1,2,3]};
}}};
vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
context.window.startQfitMapboxComparison('unit-credential');
const clean = context.window.qfitMapboxSnapshot();
events.error({error: 'unit-credential must never be copied to provenance'});
console.log(JSON.stringify({options, clean, failed: context.window.qfitMapboxSnapshot()}));
""", html)
    assert source == original
    assert result['options']['style'] == source
    assert result['options'].get('projection') == ('mercator' if projection == 'mercator' else None)
    context = result['clean']
    assert context['reference_projection'] == projection
    assert context['source_projection'] == {'name': 'globe'}
    assert context['actual_projection']['name'] == ('globe' if projection == 'source' else 'mercator')
    assert context['center'] == [7.1, 46.2]
    assert context['zoom'] == 5.25  # actual, not requested camera z5
    assert context['canvas_size_pixels'] == [1280, 900]
    assert context['device_pixel_ratio'] == 2
    assert context['rendered_feature_count'] == 3
    assert result['failed']['map_error_count'] == 1
    assert 'unit-credential' not in json.dumps(result)


def _check_capture_completeness(state, valid):
    result = _node(r"""
const fs = require('fs'), vm = require('vm');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const writes = [], errors = [];
const runtime = {map_error_count: 0, map_loaded: true, tiles_loaded: true, ...payload.state};
const page = {setContent: async () => {}, waitForFunction: async () => {},
  evaluate: async (fn, value) => value ? undefined : runtime,
  screenshot: async () => {writes.push('png');}};
const browser = {newPage: async () => page, version: () => 'Chromium test',
  close: async () => {writes.push('closed');}};
const context = {require: name => name === 'playwright' ? {chromium: {launch: async () => browser}} :
  name === 'fs' ? {readFileSync: () => JSON.stringify({credential:'unit', html:'',runtimePath:'runtime.json'}),
    writeFileSync: (path, value) => {writes.push(JSON.parse(value));}} : require(name),
  process: {argv:['node','test','out.png','1280','900','1000',''],env:{},exit: () => {}},
  console: {error: value => errors.push(value)}};
(async () => {await vm.runInNewContext(payload.script, context);
  console.log(JSON.stringify({writes,errors}));})();
""", {'script': comparison.build_node_playwright_capture_script(), 'state': state})
    if valid:
        assert result['errors'] == []
        assert result['writes'][0] == 'png'
        assert result['writes'][1]['browser_version'] == 'Chromium test'
    else:
        assert result['errors'] == ['Browser map is incomplete; capture rejected.']
        assert result['writes'] == ['closed']


def _check_projection_manifest(tmp_path):
    args = comparison.build_parser().parse_args(['--preset', 'light', '--all-cameras',
                                                '--reference-projection', 'mercator'])
    camera = next(iter(comparison.LIGHT_CAMERAS.values()))
    command = comparison._single_camera_subprocess_command(args=args, camera=camera, output_root=tmp_path)
    assert command[command.index('--reference-projection') + 1] == 'mercator'
    config = comparison._comparison_config(args=args, camera=camera, token='unit-secret', output_root=tmp_path)
    assert config.reference_projection == 'mercator'
    snapshot = {'reference_projection': 'mercator', 'source_projection': {'name': 'globe'},
                'actual_projection': {'name': 'mercator'}, 'zoom': 5.25}
    def browser(*, output_path, browser_runtime_path, reference_projection, **_kwargs):
        assert reference_projection == 'mercator'
        output_path.write_bytes(b'unit-png')
        browser_runtime_path.write_text(json.dumps(snapshot))
    config = comparison.dataclasses.replace(config, qgis=False)
    result = comparison.run_comparison(config, browser_renderer=browser, style_fetcher=lambda *_: {
        'version': 8, 'projection': {'name': 'globe'}, 'sources': {}, 'layers': []})
    manifest = json.loads(result.paths.manifest_json.read_text())
    assert manifest['browser_runtime'] == snapshot
    assert manifest['reference_projection'] == 'mercator'
    assert manifest['captured']['browser_runtime'] is True
    assert Path(manifest['outputs']['browser_runtime']).name == 'browser-runtime.json'
    assert json.loads(result.paths.mapbox_source_style_json.read_text())['projection']['name'] == 'globe'
    assert 'unit-secret' not in result.paths.manifest_json.read_text()


class BrowserContextTests(unittest.TestCase):
    def test_source_projection_and_actual_context(self):
        for preset in ('light', 'outdoors'):
            for projection in ('source', 'mercator'):
                with self.subTest(preset=preset, projection=projection):
                    _check_source_projection_and_context(preset, projection)

    def test_capture_completeness_and_artifact_order(self):
        for state, valid in (({}, True), ({'map_error_count': 1}, False),
                             ({'map_loaded': False}, False), ({'tiles_loaded': False}, False)):
            with self.subTest(state=state):
                _check_capture_completeness(state, valid)

    def test_projection_cli_subprocess_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            _check_projection_manifest(Path(directory))

    def test_default_projection_and_invalid_api_value(self):
        self.assertEqual(comparison.build_parser().parse_args([]).reference_projection, 'source')
        with self.assertRaisesRegex(ValueError, 'Reference projection'):
            comparison.build_mapbox_gl_html(camera=next(iter(comparison.LIGHT_CAMERAS.values())),
                                           reference_projection='guess')
