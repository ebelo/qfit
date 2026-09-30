import sqlite3
from unittest.mock import Mock, patch

import pytest

from tests import _path  # noqa: F401
from qfit.activities.application.activity_name_refresh import parse_activity_ids, refresh_activity_names
from qfit.activities.domain.models import Activity
from qfit.providers.domain.provider import ProviderError
from qfit.sync_repository import SyncRepository


@pytest.fixture
def stored(tmp_path):
    path = str(tmp_path / "names.gpkg")
    repo = SyncRepository(path)
    repo.ensure_schema()
    activity = Activity(
        source="strava", source_activity_id="42", name="Old ride",
        start_date="2015-01-01T10:00:00Z", geometry_source="stream",
        geometry_points=[(46.5, 6.5), (46.6, 6.6)],
        details_json={"ingest_source": "strava_bulk_export", "stream_metrics": {
            "distance": [0, 100], "altitude": [500, 510], "watts": [100, 200]}},
    )
    repo.upsert_activities([activity], compress_detail_payloads=True,
                           sync_metadata={"provider": "strava", "is_full_sync": True})
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE activity_tracks(source TEXT, source_activity_id TEXT, name TEXT, geom BLOB);
            INSERT INTO activity_tracks VALUES ('strava', '42', 'Old ride', x'1234');
            CREATE TABLE activity_points(source TEXT, source_activity_id TEXT, name TEXT, watts REAL);
            INSERT INTO activity_points VALUES ('strava', '42', 'Old ride', 100);
            CREATE TABLE activity_atlas_pages(source TEXT, source_activity_id TEXT, name TEXT,
                page_number INTEGER, page_name TEXT, page_title TEXT, page_toc_label TEXT);
            INSERT INTO activity_atlas_pages VALUES ('strava','42','Old ride',7,'old','old','old');
            CREATE TABLE atlas_toc_entries(page_number INTEGER, page_title TEXT, toc_entry_label TEXT);
            INSERT INTO atlas_toc_entries VALUES (7,'old','old');
        ''')
    return repo, path


def snapshot(path, table):
    with sqlite3.connect(path) as db:
        return db.execute(f'SELECT * FROM "{table}"').fetchall()


def test_refresh_preserves_payload_geometry_metrics_and_watermark(stored):
    repo, path = stored
    before = repo.load_activity_record("strava", "42")
    payload = snapshot(path, "activity_detail_payloads")
    state = snapshot(path, "sync_state")
    result = repo.refresh_activity_names({"42": "Renamed ride", "99": "Not local"})
    assert result == {"updated": 1, "unchanged": 0, "not_stored": 1,
                      "names": {"42": "Renamed ride"}}
    after = repo.load_activity_record("strava", "42")
    assert {key: value for key, value in before.items() if key not in ("name", "summary_hash")} == {
        key: value for key, value in after.items() if key not in ("name", "summary_hash")}
    assert after["name"] == "Renamed ride"
    assert snapshot(path, "activity_detail_payloads") == payload
    assert snapshot(path, "sync_state") == state
    assert snapshot(path, "activity_tracks")[0][2:] == ("Renamed ride", b'\x12\x34')
    assert snapshot(path, "activity_points")[0][2:] == ("Renamed ride", 100)
    assert snapshot(path, "atlas_toc_entries")[0][1] == "Renamed ride"
    assert "Renamed ride" in snapshot(path, "atlas_toc_entries")[0][2]
    assert repo.refresh_activity_names({"42": "Renamed ride"})["unchanged"] == 1
    # Reconciliation hashes must remain consistent with the renamed stored data.
    assert after["summary_hash"] == repo._compute_summary_hash(after)


def test_cancel_rolls_back_registry_and_published_names(stored):
    repo, path = stored
    before = snapshot(path, "activity_registry")
    with pytest.raises(InterruptedError):
        repo.refresh_activity_names({"42": "New"}, cancelled=Mock(side_effect=[False, True]))
    assert snapshot(path, "activity_registry") == before
    assert snapshot(path, "activity_tracks")[0][2] == "Old ride"


def test_publication_failure_rolls_back(stored):
    repo, path = stored
    before = snapshot(path, "activity_registry")
    with patch('qfit.activities.infrastructure.geopackage.activity_name_publication.publish_activity_name',
               side_effect=sqlite3.OperationalError("locked")):
        with pytest.raises(sqlite3.OperationalError):
            repo.refresh_activity_names({"42": "New"})
    assert snapshot(path, "activity_registry") == before


def test_historical_fetch_is_unbounded_summary_only(stored):
    repo, path = stored
    provider = Mock(last_fetch_notice=None)
    provider.fetch_activities.return_value = [Activity(source="strava", source_activity_id="42", name="New")]
    result = refresh_activity_names(provider, path)
    assert result["updated"] == 1
    provider.fetch_activities.assert_called_once_with(
        per_page=200, max_pages=0, before=None, after=None,
        use_detailed_streams=False, cancelled=None, progress=None)
    provider.fetch_activity_name.assert_not_called()


def test_targeted_refresh_does_not_fetch_history(stored):
    repo, path = stored
    provider = Mock()
    provider.fetch_activity_name.return_value = "New"
    assert refresh_activity_names(provider, path, ("42",))["updated"] == 1
    provider.fetch_activity_name.assert_called_once_with("42")
    provider.fetch_activities.assert_not_called()


def test_incomplete_history_never_updates(stored):
    repo, path = stored
    provider = Mock(last_fetch_notice="Rate limit reached")
    provider.fetch_activities.return_value = [Activity(source="strava", source_activity_id="42", name="New")]
    with pytest.raises(ProviderError, match="No names were changed"):
        refresh_activity_names(provider, path)
    assert repo.load_activity_record("strava", "42")["name"] == "Old ride"


def test_targeted_error_never_updates_partial_results(stored):
    repo, path = stored
    provider = Mock()
    provider.fetch_activity_name.side_effect = ["New", ProviderError("not accessible")]
    with pytest.raises(ProviderError):
        refresh_activity_names(provider, path, ("42", "43"))
    assert repo.load_activity_record("strava", "42")["name"] == "Old ride"


def test_cancelled_fetch_never_updates(stored):
    repo, path = stored
    provider = Mock(last_fetch_notice=None)
    provider.fetch_activities.return_value = []
    with pytest.raises(InterruptedError):
        refresh_activity_names(provider, path, cancelled=lambda: True)


def test_empty_store_does_not_call_provider(tmp_path):
    provider = Mock()
    path = tmp_path / "absent.gpkg"
    with pytest.raises(ValueError, match="containing stored"):
        refresh_activity_names(provider, str(path))
    assert not path.exists()
    provider.fetch_activities.assert_not_called()


@pytest.mark.parametrize('text,expected', [('', ()), (' 42,042, 43 ', ('42', '43'))])
def test_parse_ids(text, expected):
    assert parse_activity_ids(text) == expected


@pytest.mark.parametrize('text', ['0', '-42', '42,,43', 'https://strava.com/activities/42', '４２'])
def test_reject_invalid_ids(text):
    with pytest.raises(ValueError):
        parse_activity_ids(text)
