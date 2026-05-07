import io
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from pipelines.worldgen_v2 import ot_client


def test_build_url_includes_bbox_and_dataset_and_key():
    url = ot_client.build_url(
        dataset="COP30",
        bbox=(-117.0, 36.1, -116.6, 36.5),
        api_key="TEST_KEY",
    )
    assert "COP30" in url or "demtype=COP30" in url
    assert "south=36.1" in url
    assert "west=-117" in url or "west=-117.0" in url
    assert "API_Key=TEST_KEY" in url


def test_fetch_dem_calls_get_with_built_url(tmp_path):
    fake_arr = np.linspace(100, 2000, 64 * 64, dtype=np.float32).reshape(64, 64)
    fake_resp = MagicMock(status_code=200, content=b"<geotiff bytes>")
    fake_resp.raise_for_status = MagicMock()

    with patch("pipelines.worldgen_v2.ot_client.requests.get", return_value=fake_resp) as g, \
         patch("pipelines.worldgen_v2.ot_client._parse_geotiff", return_value=fake_arr):
        arr = ot_client.fetch_dem(
            dataset="COP30",
            bbox=(-117.0, 36.1, -116.6, 36.5),
            api_key="TEST_KEY",
        )
    g.assert_called_once()
    assert arr.shape == (64, 64)


def test_fetch_dem_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENTOPOGRAPHY_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENTOPOGRAPHY_API_KEY"):
        ot_client.fetch_dem(dataset="COP30", bbox=(0, 0, 1, 1), api_key=None)
