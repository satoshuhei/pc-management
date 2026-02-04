import pytest

from app.transition_service import TransitionError, apply_asset_transition, apply_request_transition


def test_apply_request_transition_allowed():
    apply_request_transition(from_status=None, to_status="RQ", actor="tester")


def test_apply_request_transition_denied():
    with pytest.raises(TransitionError):
        apply_request_transition(from_status="RQ", to_status="RP", actor="tester")


def test_apply_asset_transition_allowed():
    apply_asset_transition(from_status="INV", to_status="READY", actor="tester")


def test_apply_asset_transition_denied():
    with pytest.raises(TransitionError):
        apply_asset_transition(from_status="INV", to_status="USE", actor="tester")
