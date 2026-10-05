"""Keep local camera auto-start and private production databases out of tests."""
import pytest

@pytest.fixture(autouse=True)
def isolated_local_profiles(tmp_path,monkeypatch):
 import sentinel.api as api
 from sentinel.storage.repository import Repository
 monkeypatch.setattr(api.settings,'camera_profile_path',str(tmp_path/'camera.json'))
 monkeypatch.setattr(api.settings,'detection_profile_path',str(tmp_path/'detection.json'))
 monkeypatch.setattr(api,'repo',Repository(str(tmp_path/'isolated.sqlite')))
