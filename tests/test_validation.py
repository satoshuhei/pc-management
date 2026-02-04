import pytest

from app.models import AssetStatus
from app.validation import ValidationError, validate_asset_integrity, validate_request_integrity


def test_asset_tag_required():
    with pytest.raises(ValidationError):
        validate_asset_integrity(
            asset_tag=" ",
            hostname=None,
            status=AssetStatus.INV,
            current_user=None,
            notes=None,
        )


def test_asset_tag_length_limit():
    with pytest.raises(ValidationError):
        validate_asset_integrity(
            asset_tag="A" * 51,
            hostname=None,
            status=AssetStatus.INV,
            current_user=None,
            notes=None,
        )


def test_hostname_length_limit():
    with pytest.raises(ValidationError):
        validate_asset_integrity(
            asset_tag="AST-1",
            hostname="h" * 64,
            status=AssetStatus.INV,
            current_user=None,
            notes=None,
        )


def test_asset_use_requires_current_user():
    with pytest.raises(ValidationError):
        validate_asset_integrity(
            asset_tag="AST-1",
            hostname=None,
            status=AssetStatus.USE,
            current_user=" ",
            notes=None,
        )


def test_asset_notes_length_limit():
    with pytest.raises(ValidationError):
        validate_asset_integrity(
            asset_tag="AST-1",
            hostname=None,
            status=AssetStatus.INV,
            current_user=None,
            notes="n" * 5001,
        )


def test_request_lengths():
    with pytest.raises(ValidationError):
        validate_request_integrity(requester="r" * 129, note=None)

    with pytest.raises(ValidationError):
        validate_request_integrity(requester=None, note="n" * 1001)
