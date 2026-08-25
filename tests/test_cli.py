import sys

import pytest

from toraiz_dump.cli import autodetect_ports, main


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


def test_version_option(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["toraiz-dump", "--version"])

    with pytest.raises(SystemExit, match="0"):
        main()

    assert capsys.readouterr().out == "toraiz-dump 0.2.0\n"
