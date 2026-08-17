from src.models import (
    BaseGameConfig,
    PeopleMode,
    format_filter_summary
)
from datetime import date


def test_format_filter_summary() -> None:
    # Full library (no filters)
    is_custom, summary = format_filter_summary()
    assert is_custom == 0
    assert summary == 'Full Library'

    # Filter with album
    is_custom, summary = format_filter_summary(album_name='Europe 2023')
    assert is_custom == 1
    assert summary == 'Europe 2023'

    # Filter with countries & dates
    is_custom, summary = format_filter_summary(
        countries=['Italy', 'France'],
        min_date=date(2022, 1, 1),
        max_date=date(2023, 12, 31),
    )
    assert is_custom == 1
    assert 'Italy, France' in summary
    assert '2022/01 - 2023/12' in summary

    # Testing BaseGameConfig.format_filter_summary method
    config_default = BaseGameConfig(library_name='default')
    assert config_default.format_filter_summary() == (0, 'Full Library')
    assert config_default.format_filter_tooltip() is None

    config_custom = BaseGameConfig(
        library_name='default',
        countries=['Japan', 'Italy', 'France'],
        cities=['Tokyo', 'Rome'],
        person_names=['Alice', 'Bob'],
        people_mode=PeopleMode.ALL,
        min_date=date(2022, 1, 1),
        max_date=date(2023, 12, 31),
        include_shared=True,
    )
    is_cust, summ = config_custom.format_filter_summary()
    assert is_cust == 1
    assert '3 countries' in summ
    assert 'Tokyo, Rome' in summ
    assert 'Alice, Bob' in summ
    assert 'Shared' in summ

    tooltip = config_custom.format_filter_tooltip()
    assert tooltip is not None
    assert 'Countries: Japan, Italy, France' in tooltip
    assert 'Cities: Tokyo, Rome' in tooltip
    assert 'People (All together): Alice, Bob' in tooltip
    assert 'Dates: 2022/01 – 2023/12' in tooltip
    assert 'Shared Photos: Included' in tooltip

    # Testing single person and ANY mode
    single_person_config = BaseGameConfig(
        library_name='default',
        person_names=['Charlie'],
        people_mode=PeopleMode.ANY,
    )
    single_tooltip = single_person_config.format_filter_tooltip()
    assert single_tooltip == 'People: Charlie'

    any_people_config = BaseGameConfig(
        library_name='default',
        person_names=['Charlie', 'Dana'],
        people_mode=PeopleMode.ANY,
    )
    any_tooltip = any_people_config.format_filter_tooltip()
    assert any_tooltip == 'People (Any): Charlie, Dana'

    # Testing Portuguese language support
    is_cust_pt, summ_pt = config_custom.format_filter_summary(language='PT')
    assert is_cust_pt == 1
    assert '3 países' in summ_pt
    assert 'Compartilhadas' in summ_pt

    tooltip_pt = config_custom.format_filter_tooltip(language='PT')
    assert tooltip_pt is not None
    assert 'Países: Japan, Italy, France' in tooltip_pt
    assert 'Cidades: Tokyo, Rome' in tooltip_pt
    assert 'Pessoas (Juntas): Alice, Bob' in tooltip_pt
    assert 'Datas: 2022/01 – 2023/12' in tooltip_pt
    assert 'Fotos Compartilhadas: Incluídas' in tooltip_pt

    assert single_person_config.format_filter_tooltip(language='PT') == 'Pessoa: Charlie'
    assert any_people_config.format_filter_tooltip(language='PT') == 'Pessoas (Qualquer): Charlie, Dana'
    assert config_default.format_filter_summary(language='PT') == (0, 'Toda a Biblioteca')

