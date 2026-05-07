import pytest
from pipelines.worldgen_v2 import presets


def test_quality_good_has_expected_knobs():
    q = presets.load_quality("good")
    assert q.dem_size == 2048
    assert q.mesh_subdiv == 512
    assert q.collision_res == 256
    assert q.shader == "topdown"
    assert q.triplanar_strength == 0.0


def test_quality_max_uses_topdown_until_hextile_lands():
    q = presets.load_quality("max")
    assert q.shader == "topdown"


def test_unknown_quality_rejected():
    with pytest.raises(KeyError):
        presets.load_quality("ultra")


def test_camera_character_far_is_km_scale():
    cam = presets.load_camera("character")
    assert cam.far >= 50000


def test_biome_preset_has_palette_for_default_biomes():
    bp = presets.load_biome_palette("desert")
    assert isinstance(bp.albedo_rgb, tuple)
    assert len(bp.albedo_rgb) == 3
    for c in bp.albedo_rgb:
        assert 0 <= c <= 255
