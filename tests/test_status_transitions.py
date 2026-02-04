import pytest

from app.status_rules import (
    is_allowed_asset_transition,
    is_allowed_request_transition,
    list_allowed_asset_targets,
    list_allowed_request_targets,
)


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (None, "RQ"),
        ("NR", "RQ"),
        ("RQ", "OP"),
        ("OP", "RP"),
    ],
)
def test_request_transition_allowed(from_status, to_status):
    assert is_allowed_request_transition(from_status, to_status)


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (None, "OP"),
        ("RQ", "RP"),
        ("RP", "OP"),
        ("RP", "INV"),
    ],
)
def test_request_transition_denied(from_status, to_status):
    assert not is_allowed_request_transition(from_status, to_status)


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (None, "INV"),
        ("NR", "USE"),
        ("INV", "READY"),
        ("READY", "USE"),
        ("USE", "RET"),
        ("RET", "INV"),
        ("RET", "IT"),
        ("RET", "DIS"),
        ("IT", "READY"),
        ("USE", "AUD"),
        ("AUD", "INV"),
        ("LOST", "DIS"),
    ],
)
def test_asset_transition_allowed(from_status, to_status):
    assert is_allowed_asset_transition(from_status, to_status)


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        (None, "READY"),
        ("INV", "USE"),
        ("READY", "RET"),
        ("AUD", "READY"),
        ("IT", "DIS"),
        ("LOST", "READY"),
    ],
)
def test_asset_transition_denied(from_status, to_status):
    assert not is_allowed_asset_transition(from_status, to_status)


def test_list_allowed_targets_for_request():
    assert list_allowed_request_targets("RQ") == ["OP"]
    assert list_allowed_request_targets("NR") == ["RQ"]


def test_list_allowed_targets_for_asset():
    allowed_from_ret = list_allowed_asset_targets("RET")
    assert "INV" in allowed_from_ret
    assert "IT" in allowed_from_ret
    assert "DIS" in allowed_from_ret
    assert "AUD" in allowed_from_ret
