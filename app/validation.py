from __future__ import annotations

from app.models import AssetStatus


class ValidationError(ValueError):
    pass


def _trim(value: str | None) -> str:
    return (value or "").strip()


def validate_asset_integrity(
    *,
    asset_tag: str | None,
    hostname: str | None,
    status: AssetStatus | str,
    current_user: str | None,
    notes: str | None,
) -> None:
    tag = _trim(asset_tag)
    if not tag:
        raise ValidationError("資産タグは必須です。入力してください。")
    if len(tag) > 50:
        raise ValidationError("資産タグは50文字以内で入力してください。")

    host = _trim(hostname)
    if host and len(host) > 63:
        raise ValidationError("ホスト名は63文字以内で入力してください。")

    note_text = _trim(notes)
    if note_text and len(note_text) > 5000:
        raise ValidationError("メモは5000文字以内で入力してください。")

    status_value = status.value if isinstance(status, AssetStatus) else status
    if status_value == AssetStatus.USE.value:
        if not _trim(current_user):
            raise ValidationError("利用中の資産は利用者が必須です。入力してください。")


def validate_request_integrity(
    *,
    requester: str | None,
    note: str | None,
) -> None:
    requester_value = _trim(requester)
    if requester_value and len(requester_value) > 128:
        raise ValidationError("申請者は128文字以内で入力してください。")

    note_value = _trim(note)
    if note_value and len(note_value) > 1000:
        raise ValidationError("理由/メモは1000文字以内で入力してください。")
