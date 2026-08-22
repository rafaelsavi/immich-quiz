from datetime import date

from src.models import (
    BaseGameConfig,
    FilterDisplayMeta,
    GameFilterConfig,
    PeopleMode,
)


def test_format_filter_summary() -> None:
    # Full library (no filters)
    is_custom, summary = GameFilterConfig().format_filter_summary()
    assert is_custom == 0
    assert summary == 'Full Library'

    # Filter with album
    is_custom, summary = GameFilterConfig(album_names=['Europe 2023']).format_filter_summary()
    assert is_custom == 1
    assert summary == 'Europe 2023'

    # Single filter category with up to 2 items (limit is 2)
    is_custom, summary = GameFilterConfig(countries=['Italy', 'France']).format_filter_summary()
    assert is_custom == 1
    assert summary == 'Italy, France'

    # Filter with countries & dates (multiple categories -> limit is 1)
    is_custom, summary = GameFilterConfig(
        countries=['Italy', 'France'],
        min_date=date(2022, 1, 1),
        max_date=date(2023, 12, 31),
    ).format_filter_summary()
    assert is_custom == 1
    assert '2 countries' in summary
    assert '2022/01 - 2023/12' in summary

    # Multiple categories with multiple items (2 countries, 2 cities, 2 persons -> all collapsed to count)
    is_custom, summary = GameFilterConfig(
        countries=['Italy', 'France'],
        cities=['Rome', 'Paris'],
        person_names=['Alice', 'Bob'],
    ).format_filter_summary()
    assert is_custom == 1
    assert summary == '2 countries • 2 cities • 2 people'

    # Multiple categories with 1 element each (displayed as names)
    is_custom, summary = GameFilterConfig(
        countries=['Italy'],
        cities=['Rome'],
        person_names=['Alice'],
    ).format_filter_summary()
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
    import pytest
    from pydantic import ValidationError

    from src.models import (
        BaseGameConfig,
        FilterDisplayMeta,
        GameFilterConfig,
        GameMode,
        GameRulesConfig,
        MatchConfig,
        PhotoFilterScope,
        RoundLength,
    )

    # PhotoFilterScope default values
    scope = PhotoFilterScope(album_ids=['a1'], countries=['Japan'])
    assert scope.album_ids == ['a1']
    assert scope.countries == ['Japan']
    assert scope.cities == []
    assert scope.person_ids == []
    assert scope.include_shared is False

    # GameRulesConfig pure values
    rules = GameRulesConfig(round_count=10, location_mode=True, date_mode=False)
    assert rules.round_count == 10
    assert rules.location_mode is True
    assert rules.date_mode is False

    # BaseGameConfig validates round count
    with pytest.raises(ValidationError):
        BaseGameConfig(round_count=7)

    # BaseGameConfig validates modes (neither location nor date)
    with pytest.raises(ValidationError):
        BaseGameConfig(location_mode=False, date_mode=False)

    # MatchConfig accepts any historical round count without validation error
    historic = MatchConfig(round_count=7, location_mode=True, date_mode=False)
    assert historic.round_count == 7

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
    is_cust, summary = GameFilterConfig(album_names=['Summer 2024']).format_filter_summary()
    assert is_cust == 1
    assert summary == 'Summer 2024'

    # Two albums (single category -> lists both)
    is_cust, summary = GameFilterConfig(album_names=['Summer 2024', 'Winter 2024']).format_filter_summary()
    assert is_cust == 1
    assert summary == 'Summer 2024, Winter 2024'

    # Three albums (single category -> collapses to count)
    is_cust, summary = GameFilterConfig(album_names=['Trip 1', 'Trip 2', 'Trip 3']).format_filter_summary()
    assert is_cust == 1
    assert summary == '3 albums'

    # Three albums in PT
    is_cust, summary_pt = GameFilterConfig(
        album_names=['Trip 1', 'Trip 2', 'Trip 3']
    ).format_filter_summary(language='PT')
    assert is_cust == 1
    assert summary_pt == '3 álbuns'

    # Multiple categories including albums
    is_cust, summary = GameFilterConfig(
        album_names=['Trip 1', 'Trip 2'],
        countries=['Italy'],
    ).format_filter_summary()
    assert is_cust == 1
    assert summary == '2 albums • Italy'

    # Tooltip with albums
    config = BaseGameConfig(album_names=['Trip 1', 'Trip 2', 'Trip 3'])
    tooltip = config.format_filter_tooltip()
    assert tooltip == 'Albums: Trip 1, Trip 2, Trip 3'

    tooltip_pt = config.format_filter_tooltip(language='PT')
    assert tooltip_pt == 'Álbuns: Trip 1, Trip 2, Trip 3'


def test_leaderboard_query_model() -> None:
    from datetime import date

    from src.models import BaseGameConfig, LeaderboardQuery, PlayMode

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

    # Test new query filter fields
    q_extended = LeaderboardQuery(
        play_mode=PlayMode.challenge,
        challenge_id='ch_123',
        played_after=date(2025, 1, 1),
        played_before=date(2025, 1, 31),
    )
    assert q_extended.play_mode == PlayMode.challenge
    assert q_extended.challenge_id == 'ch_123'
    assert q_extended.played_after == date(2025, 1, 1)
    assert q_extended.played_before == date(2025, 1, 31)


def test_leaderboard_entry_model_validation() -> None:
    from datetime import datetime, timezone

    import pytest
    from pydantic import ValidationError

    from src.models import GameMode, LeaderboardEntry, MatchConfig, PlayMode, RoundLength

    config = MatchConfig(
        round_count=5,
        round_length=RoundLength.minute_1,
        location_mode=True,
        date_mode=True,
        game_mode=GameMode.pinpoint,
        libraries=['main'],
    )

    valid_entry = LeaderboardEntry(
        match_id='m-test',
        played_at=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        player_name='Rafael',
        total_score=950,
        max_possible_score=1000,
        accuracy_pct=95.0,
        rank=1,
        is_winner=True,
        game_mode=GameMode.pinpoint,
        rounds=5,
        play_mode=PlayMode.local,
        is_custom_filtered=False,
        config=config,
        total_time_seconds=23.5,
        duration_seconds=60.0,
    )
    assert valid_entry.match_id == 'm-test'
    assert valid_entry.accuracy_pct == 95.0
    assert valid_entry.rank == 1
    assert valid_entry.total_time_seconds == 23.5
    assert valid_entry.config.round_count == 5

    # Missing mandatory fields raise ValidationError
    with pytest.raises(ValidationError):
        LeaderboardEntry(  # type: ignore[call-arg]
            match_id='m-bad',
            played_at=datetime.now(timezone.utc),
            player_name='Test',
        )

    # Negative total_score raises ValidationError
    with pytest.raises(ValidationError):
        LeaderboardEntry(
            match_id='m-bad',
            played_at=datetime.now(timezone.utc),
            player_name='Test',
            total_score=-10,
            max_possible_score=1000,
            accuracy_pct=0.0,
            rank=1,
            is_winner=False,
            game_mode=GameMode.pinpoint,
            rounds=5,
            play_mode=PlayMode.local,
            is_custom_filtered=False,
            config=config,
        )

    # accuracy_pct > 100.0 raises ValidationError
    with pytest.raises(ValidationError):
        LeaderboardEntry(
            match_id='m-bad',
            played_at=datetime.now(timezone.utc),
            player_name='Test',
            total_score=1500,
            max_possible_score=1000,
            accuracy_pct=150.0,
            rank=1,
            is_winner=False,
            game_mode=GameMode.pinpoint,
            rounds=5,
            play_mode=PlayMode.local,
            is_custom_filtered=False,
            config=config,
        )

    # rank < 1 raises ValidationError
    with pytest.raises(ValidationError):
        LeaderboardEntry(
            match_id='m-bad',
            played_at=datetime.now(timezone.utc),
            player_name='Test',
            total_score=500,
            max_possible_score=1000,
            accuracy_pct=50.0,
            rank=0,
            is_winner=False,
            game_mode=GameMode.pinpoint,
            rounds=5,
            play_mode=PlayMode.local,
            is_custom_filtered=False,
            config=config,
        )


def test_sync_state_and_map_bounds_validation() -> None:
    import pytest
    from pydantic import ValidationError

    from src.models import MapBounds, SyncStateResponse

    # Valid SyncStateResponse
    sync_ok = SyncStateResponse(total_assets=100, synced_assets=50, last_sync_duration_seconds=12.5)
    assert sync_ok.total_assets == 100
    assert sync_ok.synced_assets == 50
    assert sync_ok.last_sync_duration_seconds == 12.5

    # Negative total_assets
    with pytest.raises(ValidationError):
        SyncStateResponse(total_assets=-1)

    # Negative synced_assets
    with pytest.raises(ValidationError):
        SyncStateResponse(synced_assets=-5)

    # Negative sync duration
    with pytest.raises(ValidationError):
        SyncStateResponse(last_sync_duration_seconds=-0.5)

    # Valid MapBounds
    bounds_ok = MapBounds(min_lat=-45.0, max_lat=45.0, min_lng=-120.0, max_lng=120.0)
    assert bounds_ok.min_lat == -45.0
    assert bounds_ok.max_lat == 45.0

    # Latitude out of bounds
    with pytest.raises(ValidationError):
        MapBounds(min_lat=-91.0, max_lat=45.0, min_lng=0.0, max_lng=10.0)
    with pytest.raises(ValidationError):
        MapBounds(min_lat=0.0, max_lat=91.0, min_lng=0.0, max_lng=10.0)

    # Longitude out of bounds
    with pytest.raises(ValidationError):
        MapBounds(min_lat=0.0, max_lat=10.0, min_lng=-181.0, max_lng=10.0)
    with pytest.raises(ValidationError):
        MapBounds(min_lat=0.0, max_lat=10.0, min_lng=0.0, max_lng=181.0)

    # Inverted min/max bounds
    with pytest.raises(ValidationError):
        MapBounds(min_lat=50.0, max_lat=10.0, min_lng=0.0, max_lng=10.0)
    with pytest.raises(ValidationError):
        MapBounds(min_lat=0.0, max_lat=10.0, min_lng=50.0, max_lng=10.0)


def test_option_and_date_range_validation() -> None:
    import pytest
    from pydantic import ValidationError

    from src.models import CityOption, DateRangeOption, PersonOption

    # Valid options
    p = PersonOption(id=' p1 ', name=' Alice ')
    assert p.id == 'p1'
    assert p.name == 'Alice'

    c = CityOption(name=' Rome ')
    assert c.name == 'Rome'

    # Empty string rejected
    with pytest.raises(ValidationError):
        PersonOption(id='', name='Bob')
    with pytest.raises(ValidationError):
        PersonOption(id='p2', name='   ')
    with pytest.raises(ValidationError):
        CityOption(name='')

    # Valid DateRangeOption
    d_ok = DateRangeOption(min_month='2023-01', max_month='2023-12')
    assert d_ok.min_month == '2023-01'

    # Invalid regex pattern (not YYYY-MM)
    with pytest.raises(ValidationError):
        DateRangeOption(min_month='2023/01')
    with pytest.raises(ValidationError):
        DateRangeOption(min_month='2023-13')
    with pytest.raises(ValidationError):
        DateRangeOption(min_month='2023-00')

    # min_month > max_month
    with pytest.raises(ValidationError):
        DateRangeOption(min_month='2023-10', max_month='2023-05')


def test_photo_filter_scope_and_facet_counts_validation() -> None:
    from datetime import date

    import pytest
    from pydantic import ValidationError

    from src.models import FacetCounts, PhotoFilterScope

    # Valid PhotoFilterScope
    scope_ok = PhotoFilterScope(min_date=date(2023, 1, 1), max_date=date(2023, 12, 31))
    assert scope_ok.min_date == date(2023, 1, 1)

    # Inverted date range
    with pytest.raises(ValidationError):
        PhotoFilterScope(min_date=date(2023, 12, 31), max_date=date(2023, 1, 1))

    # Valid FacetCounts
    facets_ok = FacetCounts(countries={'Italy': 10}, cities={'Rome': 5})
    assert facets_ok.countries['Italy'] == 10

    # Negative facet count
    with pytest.raises(ValidationError):
        FacetCounts(countries={'Italy': -1})
    with pytest.raises(ValidationError):
        FacetCounts(people={'Alice': -3})


def test_preflight_and_setup_response_validation() -> None:
    from datetime import date

    import pytest
    from pydantic import ValidationError

    from src.models import GameSetupResponse, PreflightResponse

    # Valid PreflightResponse
    resp_ok = PreflightResponse(
        eligible_count=25,
        required=10,
        ok=True,
        active_filters=['Europe'],
        total_count=100,
        gps_count=50,
        date_count=80,
        min_date=date(2020, 1, 1),
        max_date=date(2023, 1, 1),
    )
    assert resp_ok.eligible_count == 25

    # Negative counts in PreflightResponse
    with pytest.raises(ValidationError):
        PreflightResponse(eligible_count=-1, required=10, ok=True, active_filters=[])
    with pytest.raises(ValidationError):
        PreflightResponse(eligible_count=10, required=-5, ok=True, active_filters=[])
    with pytest.raises(ValidationError):
        PreflightResponse(eligible_count=10, required=10, ok=True, active_filters=[], total_count=-10)

    # Inverted dates in PreflightResponse
    with pytest.raises(ValidationError):
        PreflightResponse(
            eligible_count=10,
            required=10,
            ok=True,
            active_filters=[],
            min_date=date(2024, 1, 1),
            max_date=date(2020, 1, 1),
        )

    # GameSetupResponse validation
    setup_resp = GameSetupResponse(match_id=' m123 ', total_turns=10, players=[' Alice ', ' Bob '])
    assert setup_resp.match_id == 'm123'
    assert setup_resp.total_turns == 10

    with pytest.raises(ValidationError):
        GameSetupResponse(match_id='', total_turns=10, players=['Alice'])
    with pytest.raises(ValidationError):
        GameSetupResponse(match_id='m1', total_turns=0, players=['Alice'])
    with pytest.raises(ValidationError):
        GameSetupResponse(match_id='m1', total_turns=10, players=[])


def test_gameplay_question_and_answer_validation() -> None:
    import pytest
    from pydantic import ValidationError

    from src.models import (
        AlbumShuffleAnswerItem,
        AnswerRequest,
        AnswerResponse,
        BatchPinItem,
        QuestionRequest,
        QuestionResponse,
        RoundLength,
    )

    # QuestionRequest
    q_req = QuestionRequest(match_id='  m1  ')
    assert q_req.match_id == 'm1'
    with pytest.raises(ValidationError):
        QuestionRequest(match_id='')

    # BatchPinItem
    pin_ok = BatchPinItem(pin_id='p1', latitude=45.0, longitude=9.0)
    assert pin_ok.latitude == 45.0
    with pytest.raises(ValidationError):
        BatchPinItem(pin_id='p1', latitude=95.0, longitude=0.0)
    with pytest.raises(ValidationError):
        BatchPinItem(pin_id='p1', latitude=0.0, longitude=-190.0)

    # QuestionResponse
    q_resp = QuestionResponse(
        question_id='q1',
        asset_id='a1',
        media_url='/api/media/a1',
        player_name='Alice',
        player_number=1,
        total_players=2,
        player_round_number=1,
        total_rounds_per_player=5,
        turn_number=1,
        total_turns=10,
        location_mode=True,
        date_mode=True,
        round_length=RoundLength.minute_1,
    )
    assert q_resp.question_id == 'q1'

    # Turn / round out of bounds in QuestionResponse
    with pytest.raises(ValidationError):
        QuestionResponse(
            question_id='q1',
            asset_id='a1',
            media_url='/api/media/a1',
            player_name='Alice',
            player_number=3,
            total_players=2,
            player_round_number=1,
            total_rounds_per_player=5,
            turn_number=1,
            total_turns=10,
            location_mode=True,
            date_mode=True,
            round_length=RoundLength.minute_1,
        )
    with pytest.raises(ValidationError):
        QuestionResponse(
            question_id='q1',
            asset_id='a1',
            media_url='/api/media/a1',
            player_name='Alice',
            player_number=1,
            total_players=2,
            player_round_number=6,
            total_rounds_per_player=5,
            turn_number=1,
            total_turns=10,
            location_mode=True,
            date_mode=True,
            round_length=RoundLength.minute_1,
        )

    # AlbumShuffleAnswerItem
    shuffle_item = AlbumShuffleAnswerItem(photo_id='ph1', assigned_timeline_index=2)
    assert shuffle_item.assigned_timeline_index == 2
    with pytest.raises(ValidationError):
        AlbumShuffleAnswerItem(photo_id='ph1', assigned_timeline_index=-1)

    # AnswerRequest
    ans_ok = AnswerRequest(
        match_id='m1',
        question_id='q1',
        guessed_latitude=45.0,
        guessed_longitude=10.0,
        guessed_year=2023,
        guessed_month=5,
        time_taken_seconds=4.5,
    )
    assert ans_ok.guessed_latitude == 45.0

    # Unpaired coordinates
    with pytest.raises(ValidationError):
        AnswerRequest(match_id='m1', question_id='q1', guessed_latitude=45.0, guessed_longitude=None)
    with pytest.raises(ValidationError):
        AnswerRequest(match_id='m1', question_id='q1', guessed_latitude=None, guessed_longitude=10.0)

    # Unpaired dates
    with pytest.raises(ValidationError):
        AnswerRequest(match_id='m1', question_id='q1', guessed_year=2023, guessed_month=None)
    with pytest.raises(ValidationError):
        AnswerRequest(match_id='m1', question_id='q1', guessed_year=None, guessed_month=5)

    # Out-of-range coordinates / dates
    with pytest.raises(ValidationError):
        AnswerRequest(match_id='m1', question_id='q1', guessed_latitude=-95.0, guessed_longitude=0.0)
    with pytest.raises(ValidationError):
        AnswerRequest(match_id='m1', question_id='q1', guessed_year=1800, guessed_month=1)
    with pytest.raises(ValidationError):
        AnswerRequest(match_id='m1', question_id='q1', guessed_year=2023, guessed_month=13)
    with pytest.raises(ValidationError):
        AnswerRequest(match_id='m1', question_id='q1', time_taken_seconds=-1.0)

    # AnswerResponse
    ans_resp = AnswerResponse(
        player_name='Alice',
        question_id='q1',
        round_number=1,
        turn_completed=2,
        total_turns=5,
        round_complete=False,
        waiting_for=['Bob'],
        match_finished=False,
    )
    assert ans_resp.turn_completed == 2
    with pytest.raises(ValidationError):
        AnswerResponse(
            player_name='Alice',
            question_id='q1',
            round_number=1,
            turn_completed=6,
            total_turns=5,
            round_complete=True,
            waiting_for=[],
            match_finished=True,
        )


def test_results_and_summary_validation() -> None:
    from datetime import date

    import pytest
    from pydantic import ValidationError

    from src.models import (
        BatchRevealItem,
        MatchSummaryPlayer,
        MatchSummaryResponse,
        PlayerRoundResult,
        RoundResultRequest,
        RoundResultResponse,
    )

    # PlayerRoundResult
    res_ok = PlayerRoundResult(
        player_name='Alice',
        round_score=80,
        total_score=150,
        distance_km=12.4,
        date_diff_days=3,
        date_diff_months=0,
        date_diff_years_part=0,
        date_diff_months_part=0,
        date_diff_days_part=3,
    )
    assert res_ok.round_score == 80

    with pytest.raises(ValidationError):
        PlayerRoundResult(player_name='Alice', round_score=-10, total_score=0)
    with pytest.raises(ValidationError):
        PlayerRoundResult(player_name='Alice', round_score=0, total_score=0, distance_km=-5.0)
    with pytest.raises(ValidationError):
        PlayerRoundResult(player_name='Alice', round_score=0, total_score=0, date_diff_months_part=12)

    # RoundResultRequest
    req_ok = RoundResultRequest(match_id='m1', round_number=1)
    assert req_ok.round_number == 1
    with pytest.raises(ValidationError):
        RoundResultRequest(match_id='m1', round_number=0)

    # BatchRevealItem
    reveal_item = BatchRevealItem(
        photo_id='ph1',
        true_pin_id='pin1',
        actual_latitude=45.0,
        actual_longitude=10.0,
        actual_date=date(2023, 5, 1),
        actual_year=2023,
        actual_month=5,
    )
    assert reveal_item.photo_id == 'ph1'
    with pytest.raises(ValidationError):
        BatchRevealItem(photo_id='ph1', true_pin_id='pin1', actual_latitude=95.0)

    # RoundResultResponse
    round_resp = RoundResultResponse(
        round_number=2,
        total_rounds=5,
        location_mode=True,
        date_mode=True,
        results=[res_ok],
        match_finished=False,
    )
    assert round_resp.round_number == 2

    with pytest.raises(ValidationError):
        RoundResultResponse(
            round_number=6,
            total_rounds=5,
            location_mode=True,
            date_mode=True,
            results=[res_ok],
            match_finished=True,
        )

    # MatchSummaryPlayer and MatchSummaryResponse
    player_summary = MatchSummaryPlayer(
        player_name='Alice',
        total_score=500,
        max_possible_score=1000,
        accuracy_pct=50.0,
        rank=1,
        is_winner=True,
    )
    assert player_summary.player_name == 'Alice'

    summary_resp = MatchSummaryResponse(
        match_id='m1',
        rounds_played=5,
        location_mode=True,
        date_mode=True,
        finished=True,
        winners=['Alice'],
        players=[player_summary],
    )
    assert summary_resp.rounds_played == 5

    with pytest.raises(ValidationError):
        MatchSummaryPlayer(
            player_name='Alice',
            total_score=500,
            max_possible_score=1000,
            accuracy_pct=-1.0,
            rank=1,
            is_winner=True,
        )


def test_supporting_dataclasses_validation() -> None:
    from datetime import date

    import pytest

    from src.config import AppSettings, ConfigError
    from src.immich.client import AssetAnswer
    from src.storage.metadata import AssetFilterCriteria

    # AppSettings port & decay validations
    with pytest.raises(ConfigError, match='APP_PORT'):
        AppSettings(
            immich_server_url='http://localhost:2283/api',
            immich_libraries={'lib1': 'key1'},
            app_port=70000,
        )

    with pytest.raises(ConfigError, match='LOCATION_SCORE_DECAY_KM'):
        AppSettings(
            immich_server_url='http://localhost:2283/api',
            immich_libraries={'lib1': 'key1'},
            location_score_decay_km=-10.0,
        )

    with pytest.raises(ConfigError, match='AUTO_DELTA_SYNC_INTERVAL_HOURS'):
        AppSettings(
            immich_server_url='http://localhost:2283/api',
            immich_libraries={'lib1': 'key1'},
            auto_delta_sync_interval_hours=-1,
        )

    # AssetFilterCriteria date range
    with pytest.raises(ValueError, match='min_date cannot be greater than max_date'):
        AssetFilterCriteria(min_date=date(2025, 1, 1), max_date=date(2024, 1, 1))

    # AssetAnswer coordinate validation
    with pytest.raises(ValueError, match='latitude must be between -90.0 and 90.0'):
        AssetAnswer(latitude=95.0, longitude=0.0)

    with pytest.raises(ValueError, match='longitude must be between -180.0 and 180.0'):
        AssetAnswer(latitude=0.0, longitude=185.0)


