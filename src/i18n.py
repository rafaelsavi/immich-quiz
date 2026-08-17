"""Internationalization (i18n) and localization support for immich-quiz."""

from __future__ import annotations

from enum import Enum
from typing import Any


class SupportedLanguage(str, Enum):
    """Supported application languages."""

    EN = 'EN'
    PT = 'PT'

    @classmethod
    def from_str(cls, value: str | SupportedLanguage | None, default: SupportedLanguage = EN) -> SupportedLanguage:
        """Parse language code case-insensitively with default fallback."""
        if not value:
            return default
        if isinstance(value, cls):
            return value
        normalized = str(value).strip().upper()
        if normalized.startswith('PT'):
            return cls.PT
        if normalized.startswith('EN'):
            return cls.EN
        try:
            return cls(normalized)
        except ValueError:
            return default


# Centralized Message Catalogs
CATALOGS: dict[SupportedLanguage, dict[str, Any]] = {
    SupportedLanguage.EN: {
        'filters.full_library': 'Full Library',
        'filters.albums_count': lambda count: f'{count} albums' if count != 1 else '1 album',
        'filters.countries_count': lambda count: f'{count} countries' if count != 1 else '1 country',
        'filters.cities_count': lambda count: f'{count} cities' if count != 1 else '1 city',
        'filters.people_count': lambda count: f'{count} people' if count != 1 else '1 person',
        'filters.date_range': lambda min_d, max_d: f'{min_d} - {max_d}',
        'filters.date_from': lambda min_d: f'from {min_d}',
        'filters.date_until': lambda max_d: f'until {max_d}',
        'filters.shared': 'Shared',
        # Tooltip items
        'tooltip.album': 'Album',
        'tooltip.albums': 'Albums',
        'tooltip.countries': 'Countries',
        'tooltip.cities': 'Cities',
        'tooltip.people': 'People',
        'tooltip.person_single': 'People',
        'tooltip.people_all': 'People (All together)',
        'tooltip.people_any': 'People (Any)',
        'tooltip.dates_range': lambda min_d, max_d: f'Dates: {min_d} – {max_d}',
        'tooltip.dates_from': lambda min_d: f'Dates: from {min_d}',
        'tooltip.dates_until': lambda max_d: f'Dates: until {max_d}',
        'tooltip.shared': 'Shared Photos: Included',
    },
    SupportedLanguage.PT: {
        'filters.full_library': 'Toda a Biblioteca',
        'filters.albums_count': lambda count: f'{count} álbuns' if count != 1 else '1 álbum',
        'filters.countries_count': lambda count: f'{count} países' if count != 1 else '1 país',
        'filters.cities_count': lambda count: f'{count} cidades' if count != 1 else '1 cidade',
        'filters.people_count': lambda count: f'{count} pessoas' if count != 1 else '1 pessoa',
        'filters.date_range': lambda min_d, max_d: f'{min_d} - {max_d}',
        'filters.date_from': lambda min_d: f'a partir de {min_d}',
        'filters.date_until': lambda max_d: f'até {max_d}',
        'filters.shared': 'Compartilhadas',
        # Tooltip items
        'tooltip.album': 'Álbum',
        'tooltip.albums': 'Álbuns',
        'tooltip.countries': 'Países',
        'tooltip.cities': 'Cidades',
        'tooltip.people': 'Pessoas',
        'tooltip.person_single': 'Pessoa',
        'tooltip.people_all': 'Pessoas (Juntas)',
        'tooltip.people_any': 'Pessoas (Qualquer)',
        'tooltip.dates_range': lambda min_d, max_d: f'Datas: {min_d} – {max_d}',
        'tooltip.dates_from': lambda min_d: f'Datas: a partir de {min_d}',
        'tooltip.dates_until': lambda max_d: f'Datas: até {max_d}',
        'tooltip.shared': 'Fotos Compartilhadas: Incluídas',
    },
}


def translate(key: str, lang: str | SupportedLanguage | None = None, *args: Any, **kwargs: Any) -> str:
    """Look up a translation string by key with language normalization and fallback."""
    language_enum = SupportedLanguage.from_str(lang)
    catalog = CATALOGS.get(language_enum) or CATALOGS[SupportedLanguage.EN]
    raw = catalog.get(key)
    if raw is None and language_enum != SupportedLanguage.EN:
        raw = CATALOGS[SupportedLanguage.EN].get(key)

    if raw is None:
        return key

    if callable(raw):
        if args or kwargs:
            return str(raw(*args, **kwargs) if args else raw(**kwargs))
        return str(raw())

    return str(raw)


t = translate
