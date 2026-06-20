"""Tests for EvidenceManager."""

import json
import os
import tempfile

from core.evidence.manager import EvidenceManager, EvidenceEntry
from core.evidence.runners import RunResult


def test_record_and_get_latest():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = EvidenceManager(tmp)
        result = RunResult(exit_code=0, stdout="ok", stderr="", elapsed=0.5, command="test-cmd")
        entry = mgr.record("build", result)
        assert entry.passed is True
        assert entry.tool_name == "build"

        latest = mgr.get_latest("build")
        assert latest is not None
        assert latest.passed is True
        assert latest.stdout == "ok"


def test_get_latest_missing():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = EvidenceManager(tmp)
        assert mgr.get_latest("nonexistent") is None


def test_record_failure():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = EvidenceManager(tmp)
        result = RunResult(exit_code=1, stdout="", stderr="error!", elapsed=0.3, command="test-cmd")
        entry = mgr.record("lint", result)
        assert entry.passed is False
        assert entry.exit_code == 1
        assert mgr.latest_passed("lint") is False


def test_get_all_entries():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = EvidenceManager(tmp)
        for i in range(3):
            r = RunResult(exit_code=i, stdout=f"run{i}", stderr="", elapsed=0.1, command="test")
            mgr.record("test", r)
        entries = mgr.get_all("test")
        assert len(entries) == 3
        assert entries[-1].exit_code == 2


def test_latest_passed():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = EvidenceManager(tmp)
        assert mgr.latest_passed("build") is False  # no evidence yet
        r = RunResult(exit_code=0, stdout="", stderr="", elapsed=0.1, command="build")
        mgr.record("build", r)
        assert mgr.latest_passed("build") is True


def test_build_conditions():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = EvidenceManager(tmp)
        mgr.record("build", RunResult(exit_code=0, stdout="", stderr="", elapsed=0.1, command="build"))
        mgr.record("lint", RunResult(exit_code=0, stdout="", stderr="", elapsed=0.1, command="lint"))
        mgr.record("test", RunResult(exit_code=1, stdout="", stderr="fail", elapsed=0.1, command="test"))

        conditions = mgr.build_conditions()
        assert conditions.all_pass() is False
        failures = conditions.failures()
        assert len(failures) == 1
        assert failures[0].name == "test"


def test_clear():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = EvidenceManager(tmp)
        mgr.record("build", RunResult(exit_code=0, stdout="", stderr="", elapsed=0.1, command="build"))
        assert mgr.get_latest("build") is not None
        mgr.clear()
        assert mgr.get_latest("build") is None


def test_evidence_dir_created():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = EvidenceManager(tmp)
        assert mgr.evidence_dir.exists()
        assert mgr.evidence_dir.name == "evidence"
        assert mgr.evidence_dir.parent.name == ".orca"
