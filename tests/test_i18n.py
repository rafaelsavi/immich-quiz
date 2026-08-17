from datetime import date

from src.i18n import SupportedLanguage, t, translate
from src.models import BaseGameConfig, PeopleMode


def test_supported_language_from_str() -> None:
    assert SupportedLanguage.from_str('EN') == SupportedLanguage.EN
    assert SupportedLanguage.from_str('en') == SupportedLanguage.EN
    assert SupportedLanguage.from_str('en-US') == SupportedLanguage.EN
    assert SupportedLanguage.from_str('PT') == SupportedLanguage.PT
    assert SupportedLanguage.from_str('pt') == SupportedLanguage.PT
    assert SupportedLanguage.from_str('pt-BR') == SupportedLanguage.PT
    assert SupportedLanguage.from_str(None) == SupportedLanguage.EN
    assert SupportedLanguage.from_str('unknown_lang') == SupportedLanguage.EN


def test_translate_key_fallback() -> None:
    # Direct translation
    assert translate('filters.full_library', SupportedLanguage.EN) == 'Full Library'
    assert translate('filters.full_library', SupportedLanguage.PT) == 'Toda a Biblioteca'

    # Fallback to key if unknown
    assert translate('unknown.nonexistent.key', SupportedLanguage.EN) == 'unknown.nonexistent.key'


def test_translate_callable_formatting() -> None:
    assert t('filters.albums_count', SupportedLanguage.EN, 1) == '1 album'
    assert t('filters.albums_count', SupportedLanguage.EN, 5) == '5 albums'
    assert t('filters.albums_count', SupportedLanguage.PT, 1) == '1 álbum'
    assert t('filters.albums_count', SupportedLanguage.PT, 5) == '5 álbuns'

    assert t('filters.people_count', SupportedLanguage.EN, 1) == '1 person'
    assert t('filters.people_count', SupportedLanguage.EN, 3) == '3 people'
    assert t('filters.people_count', SupportedLanguage.PT, 1) == '1 pessoa'
    assert t('filters.people_count', SupportedLanguage.PT, 3) == '3 pessoas'


def test_format_filter_summary_and_tooltip_i18n() -> None:
    config = BaseGameConfig(
        library_name='default',
        countries=['France', 'Germany', 'Spain'],
        cities=['Paris', 'Berlin'],
        person_names=['Alice', 'Bob'],
        people_mode=PeopleMode.ALL,
        min_date=date(2023, 1, 1),
        max_date=date(2024, 6, 1),
        include_shared=True,
    )

    # English output
    is_cust_en, sum_en = config.format_filter_summary(language='EN')
    assert is_cust_en == 1
    assert '3 countries' in sum_en
    assert 'Paris, Berlin' in sum_en
    assert 'Alice, Bob' in sum_en
    assert 'Shared' in sum_en

    tip_en = config.format_filter_tooltip(language='EN')
    assert tip_en is not None
    assert 'Countries: France, Germany, Spain' in tip_en
    assert 'Cities: Paris, Berlin' in tip_en
    assert 'People (All together): Alice, Bob' in tip_en
    assert 'Dates: 2023/01 – 2024/06' in tip_en
    assert 'Shared Photos: Included' in tip_en

    # Portuguese output
    is_cust_pt, sum_pt = config.format_filter_summary(language='PT')
    assert is_cust_pt == 1
    assert '3 países' in sum_pt
    assert 'Paris, Berlin' in sum_pt
    assert 'Alice, Bob' in sum_pt
    assert 'Compartilhadas' in sum_pt

    tip_pt = config.format_filter_tooltip(language='PT')
    assert tip_pt is not None
    assert 'Países: France, Germany, Spain' in tip_pt
    assert 'Cidades: Paris, Berlin' in tip_pt
    assert 'Pessoas (Juntas): Alice, Bob' in tip_pt
    assert 'Datas: 2023/01 – 2024/06' in tip_pt
    assert 'Fotos Compartilhadas: Incluídas' in tip_pt
