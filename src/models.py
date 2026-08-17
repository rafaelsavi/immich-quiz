from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.i18n import SupportedLanguage, t
from src.scoring import SCORE_MAX_POINTS

# ---------------------------------------------------------------------------
# Enums and Shared Primitives
# ---------------------------------------------------------------------------


class RoundLength(str, Enum):
    seconds_30 = '30s'
    minute_1 = '1m'
    minute_2 = '2m'
    minute_5 = '5m'
    unlimited = 'unlimited'


class GameMode(str, Enum):
    pinpoint = 'pinpoint'
    album_shuffle = 'album_shuffle'


class PeopleMode(str, Enum):
    ANY = 'ANY'
    ALL = 'ALL'


class PlayMode(str, Enum):
    local = 'local'
    challenge = 'challenge'
    room = 'room'


class SyncStatus(str, Enum):
    idle = 'idle'
    syncing = 'syncing'
    error = 'error'
    never_synced = 'never_synced'


class SyncMode(str, Enum):
    full = 'full'
    delta = 'delta'


class SyncStage(str, Enum):
    idle = 'idle'
    initializing = 'initializing'
    fetching_people = 'fetching_people'
    fetching_albums = 'fetching_albums'
    updating_albums = 'updating_albums'
    fetching_tags = 'fetching_tags'
    scanning_assets = 'scanning_assets'
    indexing_assets = 'indexing_assets'
    checking_updates = 'checking_updates'
    updating_assets = 'updating_assets'
    pruning = 'pruning'
    finalizing = 'finalizing'


class SyncStateResponse(BaseModel):
    library_name: str
    last_sync_at: str | None = None
    last_full_sync_at: str | None = None
    last_immich_updated_at: str | None = None
    sync_status: SyncStatus = SyncStatus.idle
    sync_mode: SyncMode = SyncMode.full
    sync_stage: SyncStage = SyncStage.idle
    sync_error: str | None = None
    total_assets: int = 0
    synced_assets: int = 0
    last_sync_duration_seconds: float | None = None
    warning: str | None = None


class MapBounds(BaseModel):
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


def _validate_and_normalize_players(players: list[str], *, allow_empty: bool = False) -> list[str]:
    if not allow_empty and not players:
        raise ValueError('Player list cannot be empty')

    normalized_players: list[str] = []
    seen: set[str] = set()
    for player in players:
        cleaned = player.strip()
        if not cleaned:
            raise ValueError('Player names must be non-empty')
        key = cleaned.lower()
        if key in seen:
            raise ValueError('Player names must be unique')
        seen.add(key)
        normalized_players.append(cleaned)
    return normalized_players


# ---------------------------------------------------------------------------
# Library Discovery & Filter Options
# ---------------------------------------------------------------------------


class PersonOption(BaseModel):
    id: str
    name: str


class CityOption(BaseModel):
    name: str
    country: str | None = None


class DateRangeOption(BaseModel):
    min_month: str | None = None  # Format: "YYYY-MM"
    max_month: str | None = None  # Format: "YYYY-MM"


class LibraryFiltersResponse(BaseModel):
    date_range: DateRangeOption
    countries: list[str]
    cities: list[CityOption]
    people: list[PersonOption]


# ---------------------------------------------------------------------------
# Game Setup & Preflight Request / Response Models
# ---------------------------------------------------------------------------


def format_filter_summary(
    *,
    album_name: str | None = None,
    album_ids: list[str] | None = None,
    countries: list[str] | None = None,
    cities: list[str] | None = None,
    person_ids: list[str] | None = None,
    person_names: list[str] | None = None,
    people_mode: PeopleMode | str | None = None,
    min_date: date | None = None,
    max_date: date | None = None,
    include_shared: bool = False,
    language: SupportedLanguage = SupportedLanguage.EN,
) -> tuple[int, str]:
    """Return (is_custom_filtered, summary_str) based on active filter parameters."""
    lang = SupportedLanguage.from_str(language)
    parts: list[str] = []

    if album_ids or (album_name and album_name != '-'):
        if album_name and album_name != '-':
            parts.append(album_name)
        else:
            parts.append(t('filters.albums_count', lang, len(album_ids or [])))
    if countries:
        if len(countries) <= 2:
            parts.append(', '.join(countries))
        else:
            parts.append(t('filters.countries_count', lang, len(countries)))
    if cities:
        if len(cities) <= 2:
            parts.append(', '.join(cities))
        else:
            parts.append(t('filters.cities_count', lang, len(cities)))
    if person_names:
        if len(person_names) <= 2:
            parts.append(', '.join(person_names))
        else:
            parts.append(t('filters.people_count', lang, len(person_names)))
    elif person_ids:
        parts.append(t('filters.people_count', lang, len(person_ids)))
    if min_date or max_date:
        if min_date and max_date:
            parts.append(t('filters.date_range', lang, min_date.strftime('%Y/%m'), max_date.strftime('%Y/%m')))
        elif min_date:
            parts.append(t('filters.date_from', lang, min_date.strftime('%Y/%m')))
        elif max_date:
            parts.append(t('filters.date_until', lang, max_date.strftime('%Y/%m')))
    if include_shared:
        parts.append(t('filters.shared', lang))

    if not parts:
        return 0, t('filters.full_library', lang)
    return 1, ' • '.join(parts)


def format_filter_tooltip(
    *,
    album_name: str | None = None,
    album_ids: list[str] | None = None,
    countries: list[str] | None = None,
    cities: list[str] | None = None,
    person_ids: list[str] | None = None,
    person_names: list[str] | None = None,
    people_mode: PeopleMode | str | None = None,
    min_date: date | None = None,
    max_date: date | None = None,
    include_shared: bool = False,
    language: SupportedLanguage = SupportedLanguage.EN,
) -> str | None:
    """Return a detailed multiline tooltip string listing all active filter values."""
    lang = SupportedLanguage.from_str(language)
    lines: list[str] = []

    if album_ids or (album_name and album_name != '-'):
        val = album_name if (album_name and album_name != '-') else t('filters.albums_count', lang, len(album_ids or []))
        lines.append(f'{t("tooltip.album", lang)}: {val}')
    if countries:
        lines.append(f'{t("tooltip.countries", lang)}: {", ".join(countries)}')
    if cities:
        lines.append(f'{t("tooltip.cities", lang)}: {", ".join(cities)}')
    if person_names or person_ids:
        people_list = person_names if person_names else person_ids
        names_str = ', '.join(people_list) if people_list else ''
        count = len(people_list or [])
        if count > 1:
            is_all = people_mode == PeopleMode.ALL or str(people_mode).upper() == 'ALL'
            prefix = t('tooltip.people_all', lang) if is_all else t('tooltip.people_any', lang)
            lines.append(f'{prefix}: {names_str}')
        elif count == 1:
            lines.append(f'{t("tooltip.person_single", lang)}: {names_str}')
    if min_date or max_date:
        if min_date and max_date:
            lines.append(t('tooltip.dates_range', lang, min_date.strftime('%Y/%m'), max_date.strftime('%Y/%m')))
        elif min_date:
            lines.append(t('tooltip.dates_from', lang, min_date.strftime('%Y/%m')))
        elif max_date:
            lines.append(t('tooltip.dates_until', lang, max_date.strftime('%Y/%m')))
    if include_shared:
        lines.append(t('tooltip.shared', lang))

    if not lines:
        return None
    return '\n'.join(lines)


class BaseGameConfig(BaseModel):
    """Shared filter and mode configuration for preflight checks and game setup."""

    model_config = ConfigDict(str_strip_whitespace=True)

    library_name: str = Field(min_length=1)
    round_count: int = Field(default=10)
    location_mode: bool = True
    date_mode: bool = True
    game_mode: GameMode = GameMode.pinpoint
    album_ids: list[str] = Field(default_factory=list)
    person_ids: list[str] = Field(default_factory=list)
    person_names: list[str] = Field(default_factory=list)
    people_mode: PeopleMode = PeopleMode.ANY
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    min_date: date | None = None
    max_date: date | None = None
    include_shared: bool = False

    @model_validator(mode='after')
    def validate_modes_and_dates(self) -> BaseGameConfig:
        if self.round_count not in {5, 10, 20}:
            raise ValueError('round_count must be one of: 5, 10, 20')
        if not (self.location_mode or self.date_mode):
            raise ValueError('At least one mode must be enabled')
        if self.min_date and self.max_date and self.min_date > self.max_date:
            raise ValueError('min_date cannot be greater than max_date')
        return self

    def format_filter_summary(
        self,
        album_name: str | None = None,
        person_names: list[str] | None = None,
        language: SupportedLanguage = SupportedLanguage.EN,
    ) -> tuple[int, str]:
        """Return (is_custom_filtered, summary_str) for this configuration."""
        resolved_album_name = album_name or getattr(self, 'album_name', None)
        resolved_person_names = person_names or getattr(self, 'person_names', None)
        return format_filter_summary(
            album_name=resolved_album_name,
            album_ids=self.album_ids,
            countries=self.countries,
            cities=self.cities,
            person_ids=self.person_ids,
            person_names=resolved_person_names,
            people_mode=self.people_mode,
            min_date=self.min_date,
            max_date=self.max_date,
            include_shared=self.include_shared,
            language=language,
        )

    def format_filter_tooltip(
        self,
        album_name: str | None = None,
        person_names: list[str] | None = None,
        language: SupportedLanguage = SupportedLanguage.EN,
    ) -> str | None:
        """Return a detailed multiline tooltip string listing all active filter values."""
        resolved_album_name = album_name or getattr(self, 'album_name', None)
        resolved_person_names = person_names or getattr(self, 'person_names', None)
        return format_filter_tooltip(
            album_name=resolved_album_name,
            album_ids=self.album_ids,
            countries=self.countries,
            cities=self.cities,
            person_ids=self.person_ids,
            person_names=resolved_person_names,
            people_mode=self.people_mode,
            min_date=self.min_date,
            max_date=self.max_date,
            include_shared=self.include_shared,
            language=language,
        )


class PreflightRequest(BaseGameConfig):
    """Payload for live preflight eligibility checks during setup."""

    players: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def normalize_players(self) -> PreflightRequest:
        self.players = _validate_and_normalize_players(self.players, allow_empty=True)
        return self


class FacetCounts(BaseModel):
    countries: dict[str, int] = Field(default_factory=dict)
    cities: dict[str, int] = Field(default_factory=dict)
    people: dict[str, int] = Field(default_factory=dict)
    albums: dict[str, int] = Field(default_factory=dict)


class PreflightResponse(BaseModel):
    eligible_count: int
    required: int
    ok: bool
    # Human-readable list of active filters that narrow eligibility
    active_filters: list[str]
    min_date: date | None = None
    max_date: date | None = None
    total_count: int | None = None
    gps_count: int | None = None
    date_count: int | None = None
    location_mode: bool = True
    date_mode: bool = True
    facet_counts: FacetCounts | None = None
    is_synced: bool = True
    sync_status: SyncStatus = SyncStatus.idle


class GameSetupRequest(BaseGameConfig):
    """Payload for initiating a match."""

    players: list[str] = Field(min_length=1)
    round_length: RoundLength = RoundLength.minute_1
    album_name: str | None = None  # Populated server-side after resolving album_ids

    @model_validator(mode='after')
    def normalize_players(self) -> GameSetupRequest:
        self.players = _validate_and_normalize_players(self.players, allow_empty=False)
        return self


class GameSetupResponse(BaseModel):
    match_id: str
    total_turns: int
    players: list[str]
    map_bounds: MapBounds | None = None


# ---------------------------------------------------------------------------
# Gameplay / Question & Turn Models
# ---------------------------------------------------------------------------


class QuestionRequest(BaseModel):
    match_id: str
    played_asset_ids: list[str] = Field(default_factory=list)


class BatchPhotoItem(BaseModel):
    photo_id: str
    media_url: str


class BatchPinItem(BaseModel):
    pin_id: str
    latitude: float
    longitude: float


class QuestionResponse(BaseModel):
    question_id: str
    asset_id: str
    media_url: str
    library_name: str
    album_name: str | None = None
    player_name: str
    player_number: int
    total_players: int
    player_round_number: int
    total_rounds_per_player: int
    turn_number: int
    total_turns: int
    location_mode: bool
    date_mode: bool
    game_mode: GameMode = GameMode.pinpoint
    round_length: RoundLength
    batch_photos: list[BatchPhotoItem] | None = None
    batch_pins: list[BatchPinItem] | None = None


# ---------------------------------------------------------------------------
# Answers & Round Acknowledgements
# ---------------------------------------------------------------------------


class AlbumShuffleAnswerItem(BaseModel):
    photo_id: str
    assigned_pin_id: str | None = None
    assigned_timeline_index: int | None = None


class AnswerRequest(BaseModel):
    match_id: str
    question_id: str
    guessed_latitude: float | None = None
    guessed_longitude: float | None = None
    guessed_year: int | None = Field(default=None, ge=1826, le=2200)
    guessed_month: int | None = Field(default=None, ge=1, le=12)
    album_shuffle_answers: list[AlbumShuffleAnswerItem] | None = None
    timed_out: bool = False
    time_taken_seconds: float | None = None

    @model_validator(mode='after')
    def validate_month_pair(self) -> AnswerRequest:
        if self.album_shuffle_answers is None and (self.guessed_year is None) != (self.guessed_month is None):
            raise ValueError('guessed_year and guessed_month must be provided together')
        return self


class AnswerResponse(BaseModel):
    """Acknowledgement only: answers stay hidden until the whole round is in."""

    player_name: str
    question_id: str
    round_number: int
    turn_completed: int
    total_turns: int
    round_complete: bool
    waiting_for: list[str]
    match_finished: bool


# ---------------------------------------------------------------------------
# Results & Match Summaries
# ---------------------------------------------------------------------------


class PlayerRoundResult(BaseModel):
    player_name: str
    guessed_latitude: float | None = None
    guessed_longitude: float | None = None
    guessed_year: int | None = None
    guessed_month: int | None = None
    location_score: int | None = None
    date_score: int | None = None
    round_score: int
    total_score: int
    distance_km: float | None = None
    date_diff_days: int | None = None
    date_diff_months: int | None = None
    date_diff_years_part: int | None = None
    date_diff_months_part: int | None = None
    date_diff_days_part: int | None = None
    timed_out: bool = False
    album_shuffle_guesses: list[AlbumShuffleAnswerItem] | None = None


class RoundResultRequest(BaseModel):
    match_id: str
    round_number: int


class BatchRevealItem(BaseModel):
    photo_id: str
    true_pin_id: str
    actual_latitude: float | None = None
    actual_longitude: float | None = None
    actual_date: date | None = None
    actual_year: int | None = None
    actual_month: int | None = None
    actual_city: str | None = None
    actual_country: str | None = None


class RoundResultResponse(BaseModel):
    round_number: int
    total_rounds: int
    location_mode: bool
    date_mode: bool
    game_mode: GameMode = GameMode.pinpoint
    library_name: str
    actual_latitude: float | None = None
    actual_longitude: float | None = None
    actual_date: date | None = None
    actual_year: int | None = None
    actual_month: int | None = None
    actual_city: str | None = None
    actual_country: str | None = None
    batch_reveal: list[BatchRevealItem] | None = None
    results: list[PlayerRoundResult]
    match_finished: bool
    score_max_points: int = SCORE_MAX_POINTS


class MatchSummaryPlayer(BaseModel):
    player_name: str
    location_score: int | None = None
    date_score: int | None = None
    total_score: int
    max_possible_score: int
    accuracy_pct: float
    rank: int
    is_winner: bool


class MatchSummaryResponse(BaseModel):
    match_id: str
    rounds_played: int
    location_mode: bool
    date_mode: bool
    game_mode: GameMode = GameMode.pinpoint
    library_name: str
    album_name: str | None = None
    finished: bool
    winners: list[str]
    players: list[MatchSummaryPlayer]
    filter_summary: str | None = None
    filter_tooltip: str | None = None
    is_custom_filtered: bool = False


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


class LeaderboardEntry(BaseModel):
    match_id: str
    played_at: datetime
    player_name: str
    max_possible_score: int
    total_score: int
    location_score: int | None = None
    date_score: int | None = None
    accuracy_pct: float = 0.0
    rank: int = 1
    is_winner: bool = False
    awards: list[str] = Field(default_factory=list)
    filter_summary: str | None = None
    is_custom_filtered: bool = False
    play_mode: PlayMode = PlayMode.local
    challenge_id: str | None = None
    challenge_title: str | None = None
    room_id: str | None = None
    room_name: str | None = None
    config: dict = Field(default_factory=dict)
