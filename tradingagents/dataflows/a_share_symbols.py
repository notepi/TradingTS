"""A-share ticker normalization helpers for Tushare citydata mode."""

from __future__ import annotations

import re

SH_PREFIXES = ("600", "601", "603", "605", "688", "689", "900")
SZ_PREFIXES = ("000", "001", "002", "003", "200", "300", "301")

_BARE_TICKER_RE = re.compile(r"^\d{6}$")
_QUALIFIED_TICKER_RE = re.compile(r"^(?P<code>\d{6})\.(?P<suffix>SH|SZ|SS)$")

VALIDATION_MESSAGE = (
    "Please enter an A-share ticker like 600519.SH, 000001.SZ, 688333.SH, "
    "688333.SS, or a bare 6-digit mainland code."
)


def infer_a_share_exchange(code: str) -> str | None:
    """Infer exchange suffix for a 6-digit mainland ticker."""
    if code.startswith(SH_PREFIXES):
        return "SH"
    if code.startswith(SZ_PREFIXES):
        return "SZ"
    return None


def normalize_a_share_symbol(symbol: str) -> str:
    """Normalize and validate an A-share ticker for Tushare citydata mode."""
    raw = symbol.strip().upper()
    if not raw:
        raise ValueError(VALIDATION_MESSAGE)

    bare_match = _BARE_TICKER_RE.fullmatch(raw)
    if bare_match:
        suffix = infer_a_share_exchange(raw)
        if suffix is None:
            raise ValueError(VALIDATION_MESSAGE)
        return f"{raw}.{suffix}"

    qualified_match = _QUALIFIED_TICKER_RE.fullmatch(raw)
    if not qualified_match:
        raise ValueError(VALIDATION_MESSAGE)

    code = qualified_match.group("code")
    suffix = qualified_match.group("suffix")
    normalized_suffix = "SH" if suffix == "SS" else suffix
    expected_suffix = infer_a_share_exchange(code)

    if expected_suffix is None or expected_suffix != normalized_suffix:
        raise ValueError(VALIDATION_MESSAGE)

    return f"{code}.{normalized_suffix}"
