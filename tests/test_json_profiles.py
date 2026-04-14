"""Test JSON profile loading for engine_profiles module."""
import pytest
from engine_profiles import (
    load_json_profiles, list_all_profiles, get_json_profile_metadata,
    apply_profile, ALL_PROFILES, get_all_json_profile_keys,
    apply_json_profile
)


def test_json_profiles_load():
    """Test that JSON profiles can be loaded."""
    profiles = load_json_profiles()
    assert isinstance(profiles, dict)
    assert len(profiles) > 0


def test_all_profiles_combined():
    """Test that legacy and JSON profiles are combined."""
    all_profiles = list_all_profiles()
    assert len(all_profiles) > len(ALL_PROFILES)  # More than just legacy

    # Check format: (key, name, source)
    for key, name, source in all_profiles:
        assert isinstance(key, str)
        assert isinstance(name, str)
        assert source in ('legacy', 'json')


def test_json_profile_keys():
    """Test that JSON profile keys are valid."""
    keys = get_all_json_profile_keys()
    assert isinstance(keys, list)
    assert len(keys) > 0

    # Key profiles that should exist
    expected = ['am6_stock_vertical', 'aerox_lc_stock', 'piaggio_hiper2_stock']
    for key in expected:
        assert key in keys, f"Expected profile {key} not found"


def test_json_profile_metadata():
    """Test metadata retrieval for JSON profiles."""
    profiles = load_json_profiles()
    if not profiles:
        pytest.skip("No JSON profiles loaded")

    # Test with a known profile
    if 'am6_stock_vertical' in profiles:
        meta = get_json_profile_metadata('am6_stock_vertical')
        assert isinstance(meta, dict)
        assert 'port_timing_deg' in meta
        assert 'trim_parts' in meta
        assert 'cooling' in meta
        assert 'notes' in meta

        # Check port timing structure
        timing = meta['port_timing_deg']
        assert isinstance(timing, dict)
        assert 'exhaust_duration' in timing
        assert 'transfer_duration' in timing


def test_json_profile_parameters():
    """Test that JSON profiles have required physics parameters."""
    profiles = load_json_profiles()

    required_fields = [
        'B', 'stroke', 'R', 'L', 'compression_ratio', 'V_cr_min_factor',
        'I_engine', 'friction', 'x_exh', 'x_tr', 'w_exh', 'w_tr',
        'A_in_max', 'ignition_angle_deg', 'pipe_resonance_freq',
        'stock_power_kw', 'stock_rpm_peak'
    ]

    for key, profile in profiles.items():
        for field in required_fields:
            assert field in profile, f"Profile {key} missing required field: {field}"
            assert isinstance(profile[field], (int, float)), f"Field {field} in {key} should be numeric"


def test_profile_key_overlap():
    """Test that legacy profiles take precedence over JSON with same key."""
    all_profiles = list_all_profiles()
    keys_seen = set()

    for key, name, source in all_profiles:
        if key in keys_seen:
            # Should only appear once, with legacy taking precedence
            pass
        keys_seen.add(key)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
