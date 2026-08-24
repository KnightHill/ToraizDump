import pytest

from toraiz_dump.cli import autodetect_ports


def test_autodetects_one_bidirectional_port():
    assert autodetect_ports(
        ["TORAIZ AS-1"], ["TORAIZ AS-1"]
    ) == ("TORAIZ AS-1", "TORAIZ AS-1")


def test_autodetects_separate_matching_ports():
    assert autodetect_ports(
        ["TORAIZ AS-1 MIDI In"], ["TORAIZ AS-1 MIDI Out"]
    ) == ("TORAIZ AS-1 MIDI In", "TORAIZ AS-1 MIDI Out")


def test_autodetect_rejects_missing_port_direction():
    with pytest.raises(RuntimeError, match="both TORAIZ"):
        autodetect_ports(["TORAIZ AS-1 MIDI In"], ["Other MIDI Out"])


def test_autodetect_rejects_ambiguous_devices():
    with pytest.raises(RuntimeError, match="multiple"):
        autodetect_ports(
            ["TORAIZ AS-1 MIDI In", "TORAIZ AS-1 MIDI In"],
            ["TORAIZ AS-1 MIDI Out", "TORAIZ AS-1 MIDI Out"],
        )
