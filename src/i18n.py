from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SupportedLanguage(str, Enum):
    """Supported application languages."""

    EN = 'en-US'
    PT = 'pt-BR'

    @classmethod
    def from_str(
        cls,
        value: str | SupportedLanguage | None,
        default: SupportedLanguage | None = None,
    ) -> SupportedLanguage:
        """Parse language code case-insensitively with default fallback."""
        fallback = default if default is not None else cls.EN
        if not value:
            return fallback
        if isinstance(value, cls):
            return value
        normalized = str(value).strip().lower().replace('_', '-')
        if normalized.startswith('pt'):
            return cls.PT
        if normalized.startswith('en'):
            return cls.EN
        try:
            return cls(str(value).strip())
        except ValueError:
            return fallback


LOCALES_DIR = Path(__file__).parent.parent / 'locales'


def _load_locale_catalog(lang_code: str) -> dict[str, Any]:
    file_path = LOCALES_DIR / f'{lang_code}.json'
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            logger.warning('Failed to load locale file %s: %s', file_path, exc)
    return {}


# Centralized Message Catalogs loaded from locales/
CATALOGS: dict[SupportedLanguage, dict[str, Any]] = {
    SupportedLanguage.EN: _load_locale_catalog(SupportedLanguage.EN.value),
    SupportedLanguage.PT: _load_locale_catalog(SupportedLanguage.PT.value),
}


def translate(key: str, lang: str | SupportedLanguage | None = None, *args: Any, **kwargs: Any) -> str:
    """Look up a translation string by key with language normalization, pluralization, and fallback."""
    language_enum = SupportedLanguage.from_str(lang)
    catalog = CATALOGS.get(language_enum) or CATALOGS[SupportedLanguage.EN]
    raw = catalog.get(key)
    if raw is None and language_enum != SupportedLanguage.EN:
        raw = CATALOGS[SupportedLanguage.EN].get(key)

    if raw is None:
        return key

    if isinstance(raw, dict) and ('one' in raw or 'other' in raw):
        count = args[0] if args else (kwargs.get('count', 0))
        try:
            num = int(count)
            rule = 'one' if num == 1 else 'other'
        except (ValueError, TypeError):
            rule = 'other'
        template = raw.get(rule) or raw.get('other', '')
        return template.replace('{count}', str(count)).replace('{0}', str(count))

    if callable(raw):
        if args or kwargs:
            return str(raw(*args, **kwargs) if args else raw(**kwargs))
        return str(raw())

    if isinstance(raw, str):
        res = raw
        if args:
            for idx, arg in enumerate(args):
                res = res.replace(f'{{{idx}}}', str(arg))
        if kwargs:
            for k, v in kwargs.items():
                res = res.replace(f'{{{k}}}', str(v))
        return res

    return str(raw)


t = translate


def parse_accept_language(
    header: str | None,
    default: str | SupportedLanguage | None = None,
) -> SupportedLanguage:
    """Parse an HTTP Accept-Language header and resolve to best matching SupportedLanguage.

    Supports quality weights, e.g. 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'.
    """
    fallback = SupportedLanguage.from_str(default) if default is not None else SupportedLanguage.EN
    if not header or not header.strip():
        return fallback

    items: list[tuple[float, str]] = []
    for part in header.split(','):
        part = part.strip()
        if not part:
            continue
        params = part.split(';')
        tag = params[0].strip().lower().replace('_', '-')
        if not tag:
            continue
        q = 1.0
        for param in params[1:]:
            param_clean = param.strip()
            if param_clean.startswith('q='):
                try:
                    q = float(param_clean[2:].strip())
                except ValueError:
                    q = 0.0
        items.append((q, tag))

    # Sort descending by quality weight
    items.sort(key=lambda x: x[0], reverse=True)

    for _, tag in items:
        if tag == '*':
            continue
        if tag.startswith('pt'):
            return SupportedLanguage.PT
        if tag.startswith('en'):
            return SupportedLanguage.EN

    return fallback
