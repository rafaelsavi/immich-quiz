from datetime import date

from src.models import (
    BaseGameConfig,
    FilterDisplayMeta,
    GameFilterConfig,
    GameRulesConfig,
    LeaderboardQuery,
    PeopleMode,
    PhotoFilterScope,
    format_filter_summary,
)


def test_format_filter_summary() -> None:
    # Full library (no filters)
    is_custom, summary = format_filter_summary()
    assert is_custom == 0
    assert summary == 'Full Library'

    # Filter with album
    is_custom, summary = format_filter_summary(album_names=['Europe 2023'])
    assert is_custom == 1
    assert summary == 'Europe 2023'

    # Single filter category with up to 2 items (limit is 2)
    is_custom, summary = format_filter_summary(countries=['Italy', 'France'])
    assert is_custom == 1
    assert summary == 'Italy, France'

    # Filter with countries & dates (multiple categories -> limit is 1)
    is_custom, summary = format_filter_summary(
        countries=['Italy', 'France'],
        min_date=date(2022, 1, 1),
        max_date=date(2023, 12, 31),
    )
    assert is_custom == 1
    assert '2 countries' in summary
    assert '2022/01 - 2023/12' in summary

    # Multiple categories with multiple items (2 countries, 2 cities, 2 persons -> all collapsed to count)
    is_custom, summary = format_filter_summary(
        countries=['Italy', 'France'],
        cities=['Rome', 'Paris'],
        person_names=['Alice', 'Bob'],
    )
    assert is_custom == 1
    assert summary == '2 countries • 2 cities • 2 people'

    # Multiple categories with 1 element each (displayed as names)
    is_custom, summary = format_filter_summary(
        countries=['Italy'],
        cities=['Rome'],
        person_names=['Alice'],
    )
    assert is_custom == 1
    assert summary == 'Italy • Rome • Alice'

    # Testing BaseGameConfig.format_filter_summary method
    config_default = BaseGameConfig()
    assert config_default.format_filter_summary() == (0, 'Full Library')
    assert config_default.format_filter_tooltip() is None

    config_custom = BaseGameConfig(
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
    assert '2 cities' in summ
    assert '2 people' in summ
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
        person_names=['Charlie'],
        people_mode=PeopleMode.ANY,
    )
    single_tooltip = single_person_config.format_filter_tooltip()
    assert single_tooltip == 'People: Charlie'

    any_people_config = BaseGameConfig(
        person_names=['Charlie', 'Dana'],
        people_mode=PeopleMode.ANY,
    )
    any_tooltip = any_people_config.format_filter_tooltip()
    assert any_tooltip == 'People (Any): Charlie, Dana'

    # Testing Portuguese language support
    is_cust_pt, summ_pt = config_custom.format_filter_summary(language='PT')
    assert is_cust_pt == 1
    assert '3 países' in summ_pt
    assert '2 cidades' in summ_pt
    assert '2 pessoas' in summ_pt
    assert 'Compartilhadas' in summ_pt

    tooltip_pt = config_custom.format_filter_tooltip(language='PT')
    assert tooltip_pt is not None
    assert 'Países: Japan, Italy, France' in tooltip_pt
    assert 'Cidades: Tokyo, Rome' in tooltip_pt
    assert 'Pessoas (Juntas): Alice, Bob' in tooltip_pt
    assert 'Datas: 2022/01 – 2023/12' in tooltip_pt
    assert 'Fotos Compartilhadas: Incluídas' in tooltip_pt

    assert single_person_config.format_filter_tooltip(language='PT') == 'Pessoa: Charlie'
    any_people_config = BaseGameConfig(
        person_names=['Charlie', 'Dana'],
        people_mode=PeopleMode.ANY,
    )
    assert any_people_config.format_filter_tooltip(language='PT') == 'Pessoas (Qualquer): Charlie, Dana'
    assert config_default.format_filter_summary(language='PT') == (0, 'Toda a Biblioteca')


def test_filter_display_meta_album_names() -> None:
    # Test setting list album_names
    meta = FilterDisplayMeta(album_names=['Japan 2024', 'Korea 2024'])
    assert meta.album_names == ['Japan 2024', 'Korea 2024']

    # Test empty meta
    meta_empty = FilterDisplayMeta()
    assert meta_empty.album_names == []
    assert meta_empty.person_names == []


def test_models_hierarchy_and_rules_validation() -> None:
    from pydantic import ValidationError
    import pytest
    from src.models import GameRulesConfig, PhotoFilterScope, GameFilterConfig, GameMode, RoundLength

    # PhotoFilterScope default values
    scope = PhotoFilterScope(album_ids=['a1'], countries=['Japan'])
    assert scope.album_ids == ['a1']
    assert scope.countries == ['Japan']
    assert scope.cities == []
    assert scope.person_ids == []
    assert scope.include_shared is False

    # GameRulesConfig validation
    rules = GameRulesConfig(round_count=10, location_mode=True, date_mode=False)
    assert rules.round_count == 10
    assert rules.location_mode is True
    assert rules.date_mode is False

    # Invalid round count
    with pytest.raises(ValidationError):
        GameRulesConfig(round_count=7)

    # Invalid modes (neither location nor date)
    with pytest.raises(ValidationError):
        GameRulesConfig(location_mode=False, date_mode=False)

    # BaseGameConfig combines both
    config = BaseGameConfig(
        libraries=['main'],
        album_names=['Holiday'],
        round_count=20,
        round_length=RoundLength.seconds_30,
        game_mode=GameMode.pinpoint,
    )
    assert isinstance(config, PhotoFilterScope)
    assert isinstance(config, FilterDisplayMeta)
    assert isinstance(config, GameRulesConfig)
    assert isinstance(config, GameFilterConfig)
    assert config.libraries == ['main']
    assert config.album_names == ['Holiday']
    assert config.round_count == 20


def test_multi_album_filter_summary_and_tooltip() -> None:
    # Single album
    is_cust, summary = format_filter_summary(album_names=['Summer 2024'])
    assert is_cust == 1
    assert summary == 'Summer 2024'

    # Two albums (single category -> lists both)
    is_cust, summary = format_filter_summary(album_names=['Summer 2024', 'Winter 2024'])
    assert is_cust == 1
    assert summary == 'Summer 2024, Winter 2024'

    # Three albums (single category -> collapses to count)
    is_cust, summary = format_filter_summary(album_names=['Trip 1', 'Trip 2', 'Trip 3'])
    assert is_cust == 1
    assert summary == '3 albums'

    # Three albums in PT
    is_cust, summary_pt = format_filter_summary(album_names=['Trip 1', 'Trip 2', 'Trip 3'], language='PT')
    assert is_cust == 1
    assert summary_pt == '3 álbuns'

    # Multiple categories including albums
    is_cust, summary = format_filter_summary(
        album_names=['Trip 1', 'Trip 2'],
        countries=['Italy'],
    )
    assert is_cust == 1
    assert summary == '2 albums • Italy'

    # Tooltip with albums
    config = BaseGameConfig(album_names=['Trip 1', 'Trip 2', 'Trip 3'])
    tooltip = config.format_filter_tooltip()
    assert tooltip == 'Albums: Trip 1, Trip 2, Trip 3'

    tooltip_pt = config.format_filter_tooltip(language='PT')
    assert tooltip_pt == 'Álbuns: Trip 1, Trip 2, Trip 3'


def test_leaderboard_query_model() -> None:
    from src.models import LeaderboardQuery, BaseGameConfig

    config = BaseGameConfig(
        libraries=['main', 'backup'],
        album_ids=['alb-1'],
        countries=['Italy'],
        round_count=10,
        include_shared=True,
    )
    query = LeaderboardQuery.from_config(config)
    assert query.libraries == ['main', 'backup']
    assert query.album_ids == ['alb-1']
    assert query.countries == ['Italy']
    assert query.rounds == 10
    assert query.include_shared is True
    assert query.exact_filter_match is True

    # Test normalization from comma-separated string inputs
    query_str = LeaderboardQuery(
        countries='France, Italy, Germany',
        cities='Paris, Rome',
        person_ids='p1, p2',
    )
    assert query_str.countries == ['France', 'Italy', 'Germany']
    assert query_str.cities == ['Paris', 'Rome']
    assert query_str.person_ids == ['p1', 'p2']

