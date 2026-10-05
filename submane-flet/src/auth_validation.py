"""会員登録とログインの入力を検証する．正式な方針はAPI担当と合わせる．"""

import re

from validation import ValidationError

MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128
_LOCAL_PART = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+")
_DOMAIN_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


def normalize_email(value: str) -> str:
    """基本的なASCIIメール形式を確認し，前後空白と大文字小文字をそろえる．"""
    email = value.strip() if isinstance(value, str) else ""
    if len(email) > 254 or email.count("@") != 1:
        raise ValueError("メールアドレスの形式を確認してください．")
    local, domain = email.split("@")
    labels = domain.split(".")
    if (
        not 1 <= len(local) <= 64 or not _LOCAL_PART.fullmatch(local)
        or local.startswith(".") or local.endswith(".") or ".." in local
        or len(labels) < 2 or any(not _DOMAIN_LABEL.fullmatch(label) for label in labels)
    ):
        raise ValueError("メールアドレスの形式を確認してください．")
    return email.casefold()


def validate_credentials(email: str, password: str, *, is_sign_up=False,
                         confirmation: str | None = None) -> dict[str, str]:
    """パスワードは切り詰めたり空白を削除したりせず，そのまま返す．"""
    errors = {}
    try:
        clean_email = normalize_email(email)
    except ValueError as exc:
        clean_email = ""
        errors["email"] = str(exc)
    if not isinstance(password, str) or not password:
        errors["password"] = "パスワードを入力してください．"
    elif len(password) > MAX_PASSWORD_LENGTH:
        errors["password"] = f"パスワードは{MAX_PASSWORD_LENGTH}文字以内で入力してください．"
    elif is_sign_up and len(password) < MIN_PASSWORD_LENGTH:
        errors["password"] = f"パスワードは{MIN_PASSWORD_LENGTH}文字以上で入力してください．"
    if is_sign_up and confirmation is not None and confirmation != password:
        errors["password_confirmation"] = "パスワードが一致しません．"
    if errors:
        raise ValidationError(errors)
    return {"email": clean_email, "password": password}
