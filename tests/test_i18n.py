from datetime import date

from src.i18n import SupportedLanguage, t, translate
from src.models import BaseGameConfig, PeopleMode


def test_supported_language_from_str() -> None:
    assert SupportedLanguage.EN == 'en-US'
    assert SupportedLanguage.PT == 'pt-BR'
    assert SupportedLanguage.from_str('EN') == SupportedLanguage.EN
    assert SupportedLanguage.from_str('en') == SupportedLanguage.EN
    assert SupportedLanguage.from_str('en-US') == SupportedLanguage.EN
    assert SupportedLanguage.from_str('en_us') == SupportedLanguage.EN
    assert SupportedLanguage.from_str('PT') == SupportedLanguage.PT
    assert SupportedLanguage.from_str('pt') == SupportedLanguage.PT
    assert SupportedLanguage.from_str('pt-BR') == SupportedLanguage.PT
    assert SupportedLanguage.from_str('pt_br') == SupportedLanguage.PT
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
    # Single category config (limit is 2)
    single_cat_config = BaseGameConfig(
        countries=['France', 'Germany'],
    )
    is_cust_single, sum_single_en = single_cat_config.format_filter_summary(language='EN')
    assert is_cust_single == 1
    assert sum_single_en == 'France, Germany'

    is_cust_single_pt, sum_single_pt = single_cat_config.format_filter_summary(language='PT')
    assert is_cust_single_pt == 1
    assert sum_single_pt == 'France, Germany'

    # Multi-category config (limit is 1)
    config = BaseGameConfig(
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
    assert '2 cities' in sum_en
    assert '2 people' in sum_en
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
    assert '2 cidades' in sum_pt
    assert '2 pessoas' in sum_pt
    assert 'Compartilhadas' in sum_pt

    tip_pt = config.format_filter_tooltip(language='PT')
    assert tip_pt is not None
    assert 'Países: France, Germany, Spain' in tip_pt
    assert 'Cidades: Paris, Berlin' in tip_pt
    assert 'Pessoas (Juntas): Alice, Bob' in tip_pt
    assert 'Datas: 2023/01 – 2024/06' in tip_pt
    assert 'Fotos Compartilhadas: Incluídas' in tip_pt


def test_parse_accept_language() -> None:
    from src.i18n import parse_accept_language

    assert parse_accept_language('pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7') == SupportedLanguage.PT
    assert parse_accept_language('en-US,en;q=0.9,pt;q=0.8') == SupportedLanguage.EN
    assert parse_accept_language('fr-FR,fr;q=0.9,pt-BR;q=0.8') == SupportedLanguage.PT
    assert parse_accept_language('fr-FR,fr;q=0.9,en-US;q=0.8') == SupportedLanguage.EN
    assert parse_accept_language('fr-FR,de-DE;q=0.9', default=SupportedLanguage.PT) == SupportedLanguage.PT
    assert parse_accept_language('', default=SupportedLanguage.PT) == SupportedLanguage.PT
    assert parse_accept_language(None, default=SupportedLanguage.EN) == SupportedLanguage.EN


def test_backend_catalog_key_parity() -> None:
    from src.i18n import CATALOGS

    en_keys = set(CATALOGS[SupportedLanguage.EN].keys())
    pt_keys = set(CATALOGS[SupportedLanguage.PT].keys())

    missing_in_pt = en_keys - pt_keys
    missing_in_en = pt_keys - en_keys

    assert not missing_in_pt, f'Keys present in EN but missing in PT: {missing_in_pt}'
    assert not missing_in_en, f'Keys present in PT but missing in EN: {missing_in_en}'


def test_frontend_catalog_key_parity() -> None:
    import re
    from pathlib import Path

    i18n_js_path = Path(__file__).parent.parent / 'static' / 'js' / 'modules' / 'i18n.js'
    assert i18n_js_path.exists()
    content = i18n_js_path.read_text(encoding='utf-8')

    en_match = re.search(r'"en-US":\s*\{(.*?)\n\s*\},', content, re.DOTALL)
    pt_match = re.search(r'"pt-BR":\s*\{(.*?)\n\s*\},', content, re.DOTALL)

    assert en_match is not None, 'Could not locate "en-US" dictionary in i18n.js'
    assert pt_match is not None, 'Could not locate "pt-BR" dictionary in i18n.js'

    en_block = en_match.group(1)
    pt_block = pt_match.group(1)

    key_regex = re.compile(r'^\s*"([^"]+)":', re.MULTILINE)
    en_keys = set(key_regex.findall(en_block))
    pt_keys = set(key_regex.findall(pt_block))

    missing_in_pt = en_keys - pt_keys
    missing_in_en = pt_keys - en_keys

    assert not missing_in_pt, f'Frontend keys present in en-US but missing in pt-BR: {missing_in_pt}'
    assert not missing_in_en, f'Frontend keys present in pt-BR but missing in en-US: {missing_in_en}'
    assert len(en_keys) > 50, f'Expected at least 50 translation keys, found {len(en_keys)}'
