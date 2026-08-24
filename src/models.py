"""Domain models, request/response schemas, and validation logic for Immich Quiz."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.i18n import SupportedLanguage, t
from src.scoring import SCORE_MAX_POINTS

# ---------------------------------------------------------------------------
# Enums and Shared Primitives
# ---------------------------------------------------------------------------


class RoundLength(str, Enum):
    """Countdown timer duration allowed per round or turn."""

    seconds_30 = '30s'
    minute_1 = '1m'
    minute_2 = '2m'
    minute_5 = '5m'
    unlimited = 'unlimited'


class GameMode(str, Enum):
    """Supported gameplay mechanics ('pinpoint' single photo guess, 'album_shuffle' batch ordering)."""

    pinpoint = 'pinpoint'
    album_shuffle = 'album_shuffle'


class PeopleMode(str, Enum):
    """Multi-person filtering match criteria ('ANY' matches any selected person, 'ALL' requires all selected people)."""

    ANY = 'ANY'
    ALL = 'ALL'


class PlayMode(str, Enum):
    """Match session mode ('local' couch multiplayer, 'challenge' async match seed, 'room' live room)."""

    local = 'local'
    challenge = 'challenge'
    room = 'room'


class SyncStatus(str, Enum):
    """High-level execution status of the background synchronization engine."""

    idle = 'idle'
    syncing = 'syncing'
    error = 'error'
    never_synced = 'never_synced'


class SyncMode(str, Enum):
    """Scope of metadata synchronization ('full' complete re-indexing, 'delta' incremental update)."""

    full = 'full'
    delta = 'delta'


class SyncStage(str, Enum):
    """Granular execution stage within a synchronization job."""

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
    """Real-time synchronization status and metrics for indexed libraries."""

    libraries: list[str] = Field(default_factory=list)
    is_syncing: bool = False
    last_sync_at: str | None = None
    last_full_sync_at: str | None = None
    last_immich_updated_at: str | None = None
    sync_status: SyncStatus = SyncStatus.idle
    sync_mode: SyncMode = SyncMode.full
    sync_stage: SyncStage = SyncStage.idle
    sync_error: str | None = None
    total_assets: int = Field(default=0, ge=0)
    synced_assets: int = Field(default=0, ge=0)
    last_sync_duration_seconds: float | None = Field(default=None, ge=0.0)
    warnings: dict[str, str] = Field(default_factory=dict)


class MapBounds(BaseModel):
    """Geographic bounding box spanning minimum and maximum latitude/longitude coordinates."""

    min_lat: float = Field(ge=-90.0, le=90.0)
    max_lat: float = Field(ge=-90.0, le=90.0)
    min_lng: float = Field(ge=-180.0, le=180.0)
    max_lng: float = Field(ge=-180.0, le=180.0)

    @model_validator(mode='after')
    def validate_bounds(self) -> MapBounds:
        if self.min_lat > self.max_lat:
            raise ValueError('min_lat cannot be greater than max_lat')
        if self.min_lng > self.max_lng:
            raise ValueError('min_lng cannot be greater than max_lng')
        return self


def _validate_and_normalize_players(players: list[str], *, allow_empty: bool = False) -> list[str]:
    """Validate player list constraints (non-empty, unique names) and strip whitespace."""
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
    """Person filter option with unique identifier and display name."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class CityOption(BaseModel):
    """City filter option with name and optional country."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    country: str | None = None


class DateRangeOption(BaseModel):
    """Available date bounds formatted as 'YYYY-MM' strings."""

    model_config = ConfigDict(str_strip_whitespace=True)

    min_month: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')  # Format: "YYYY-MM"
    max_month: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')  # Format: "YYYY-MM"

    @model_validator(mode='after')
    def validate_range(self) -> DateRangeOption:
        if self.min_month and self.max_month and self.min_month > self.max_month:
            raise ValueError('min_month cannot be after max_month')
        return self


class LibraryFiltersResponse(BaseModel):
    """Available filter dimensions (dates, countries, cities, people) discovered for libraries."""

    date_range: DateRangeOption
    countries: list[str] = Field(default_factory=list)
    cities: list[CityOption] = Field(default_factory=list)
    people: list[PersonOption] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Composable Filter & Rule Models
# ---------------------------------------------------------------------------


class PhotoFilterScope(BaseModel):
    """Pure dataset filter dimensions (IDs and criteria only, no presentation fields)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    libraries: list[str] = Field(default_factory=list)
    album_ids: list[str] = Field(default_factory=list)
    person_ids: list[str] = Field(default_factory=list)
    people_mode: PeopleMode = PeopleMode.ANY
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    min_date: date | None = None
    max_date: date | None = None
    include_shared: bool = False

    @model_validator(mode='after')
    def validate_dates(self) -> PhotoFilterScope:
        if self.min_date and self.max_date and self.min_date > self.max_date:
            raise ValueError('min_date cannot be greater than max_date')
        return self


class FilterDisplayMeta(BaseModel):
    """Presentation labels and resolved display metadata for filters."""

    model_config = ConfigDict(str_strip_whitespace=True)

    album_names: list[str] = Field(default_factory=list)
    person_names: list[str] = Field(default_factory=list)


class GameFilterConfig(PhotoFilterScope, FilterDisplayMeta):
    """Combined dataset scope with resolved presentation metadata and formatter helpers."""

    def format_filter_summary(
        self,
        language: SupportedLanguage = SupportedLanguage.EN,
    ) -> tuple[int, str]:
        """Return (is_custom_filtered, summary_str) based on active filter parameters."""
        active_filters_count = sum(
            [
                bool(self.album_names),
                bool(self.countries),
                bool(self.cities),
                bool(self.person_names),
                bool(self.min_date or self.max_date),
                bool(self.include_shared),
            ]
        )
        max_items = 1 if active_filters_count > 1 else 2

        parts: list[str] = []

        if self.libraries:
            if len(self.libraries) <= max_items:
                parts.append(', '.join(self.libraries))
            else:
                parts.append(t('filters.libraries_count', language, len(self.libraries)))
        if self.album_names:
            if len(self.album_names) <= max_items:
                parts.append(', '.join(self.album_names))
            else:
                parts.append(t('filters.albums_count', language, len(self.album_names)))
        if self.countries:
            if len(self.countries) <= max_items:
                parts.append(', '.join(self.countries))
            else:
                parts.append(t('filters.countries_count', language, len(self.countries)))
        if self.cities:
            if len(self.cities) <= max_items:
                parts.append(', '.join(self.cities))
            else:
                parts.append(t('filters.cities_count', language, len(self.cities)))
        if self.person_names:
            if len(self.person_names) <= max_items:
                parts.append(', '.join(self.person_names))
            else:
                parts.append(t('filters.people_count', language, len(self.person_names)))
        if self.min_date or self.max_date:
            if self.min_date and self.max_date:
                parts.append(
                    t('filters.date_range', language, self.min_date.strftime('%Y/%m'), self.max_date.strftime('%Y/%m'))
                )
            elif self.min_date:
                parts.append(t('filters.date_from', language, self.min_date.strftime('%Y/%m')))
            elif self.max_date:
                parts.append(t('filters.date_until', language, self.max_date.strftime('%Y/%m')))
        if self.include_shared:
            parts.append(t('filters.shared', language))

        if not parts:
            return 0, t('filters.full_library', language)
        return 1, ' • '.join(parts)

    def format_filter_tooltip(
        self,
        language: SupportedLanguage = SupportedLanguage.EN,
    ) -> str | None:
        """Return a detailed multiline tooltip string listing all active filter values."""
        lines: list[str] = []

        if self.libraries:
            label = t('tooltip.libraries', language) if len(self.libraries) > 1 else t('tooltip.library', language)
            lines.append(f'{label}: {", ".join(self.libraries)}')
        if self.album_names:
            label = t('tooltip.albums', language) if len(self.album_names) > 1 else t('tooltip.album', language)
            lines.append(f'{label}: {", ".join(self.album_names)}')
        if self.countries:
            lines.append(f'{t("tooltip.countries", language)}: {", ".join(self.countries)}')
        if self.cities:
            lines.append(f'{t("tooltip.cities", language)}: {", ".join(self.cities)}')
        if self.person_names:
            names_str = ', '.join(self.person_names)
            count = len(self.person_names)
            if count > 1:
                is_all = self.people_mode == PeopleMode.ALL or str(self.people_mode).upper() == 'ALL'
                prefix = t('tooltip.people_all', language) if is_all else t('tooltip.people_any', language)
                lines.append(f'{prefix}: {names_str}')
            elif count == 1:
                lines.append(f'{t("tooltip.person_single", language)}: {names_str}')
        if self.min_date or self.max_date:
            if self.min_date and self.max_date:
                lines.append(
                    t('tooltip.dates_range', language, self.min_date.strftime('%Y/%m'), self.max_date.strftime('%Y/%m'))
                )
            elif self.min_date:
                lines.append(t('tooltip.dates_from', language, self.min_date.strftime('%Y/%m')))
            elif self.max_date:
                lines.append(t('tooltip.dates_until', language, self.max_date.strftime('%Y/%m')))
        if self.include_shared:
            lines.append(t('tooltip.shared', language))

        if not lines:
            return None
        return '\n'.join(lines)


class GameRulesConfig(BaseModel):
    """Game rules and mechanics (round counts, timers, game modes)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    round_count: int = Field(default=10, ge=1)
    round_length: RoundLength = RoundLength.minute_1
    location_mode: bool = True
    date_mode: bool = True
    game_mode: GameMode = GameMode.pinpoint


class BaseGameConfig(GameFilterConfig, GameRulesConfig):
    """Shared filter and mode configuration for preflight checks and game setup."""

    @model_validator(mode='after')
    def validate_game_config(self) -> BaseGameConfig:
        if self.min_date and self.max_date and self.min_date > self.max_date:
            raise ValueError('min_date cannot be greater than max_date')
        if self.round_count not in {5, 10, 20}:
            raise ValueError('round_count must be one of: 5, 10, 20')
        if not (self.location_mode or self.date_mode):
            raise ValueError('At least one mode must be enabled')
        return self


class MatchConfig(GameFilterConfig, GameRulesConfig):
    """Read-only deserialization of a stored match configuration without setup validators."""

    pass


class PreflightRequest(BaseGameConfig):
    """Payload for live preflight eligibility checks during setup."""

    players: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def normalize_players(self) -> PreflightRequest:
        self.players = _validate_and_normalize_players(self.players, allow_empty=True)
        return self


class FacetCounts(BaseModel):
    """Count of eligible assets broken down across countries, cities, people, and albums."""

    countries: dict[str, int] = Field(default_factory=dict)
    cities: dict[str, int] = Field(default_factory=dict)
    people: dict[str, int] = Field(default_factory=dict)
    albums: dict[str, int] = Field(default_factory=dict)

    @field_validator('countries', 'cities', 'people', 'albums', mode='after')
    @classmethod
    def validate_non_negative_counts(cls, v: dict[str, int]) -> dict[str, int]:
        for key, count in v.items():
            if count < 0:
                raise ValueError(f'Count for {key} cannot be negative: {count}')
        return v


class PreflightResponse(BaseModel):
    """Eligibility check result containing matching counts, warnings, and facet breakdowns."""

    eligible_count: int = Field(ge=0)
    required: int = Field(ge=0)
    ok: bool
    # Human-readable list of active filters that narrow eligibility
    active_filters: list[str] = Field(default_factory=list)
    min_date: date | None = None
    max_date: date | None = None
    total_count: int | None = Field(default=None, ge=0)
    gps_count: int | None = Field(default=None, ge=0)
    date_count: int | None = Field(default=None, ge=0)
    location_mode: bool = True
    date_mode: bool = True
    facet_counts: FacetCounts | None = None
    is_synced: bool = True
    sync_status: SyncStatus = SyncStatus.idle

    @model_validator(mode='after')
    def validate_preflight_dates(self) -> PreflightResponse:
        if self.min_date and self.max_date and self.min_date > self.max_date:
            raise ValueError('min_date cannot be greater than max_date')
        return self


class GameSetupRequest(BaseGameConfig):
    """Payload for initiating a match."""

    players: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def normalize_players(self) -> GameSetupRequest:
        self.players = _validate_and_normalize_players(self.players, allow_empty=False)
        return self


class GameSetupResponse(BaseModel):
    """Initial match configuration and metadata returned upon creating a match."""

    model_config = ConfigDict(str_strip_whitespace=True)

    match_id: str = Field(min_length=1)
    total_turns: int = Field(ge=1)
    players: list[str] = Field(min_length=1)
    map_bounds: MapBounds | None = None


# ---------------------------------------------------------------------------
# Leaderboard Query Model
# ---------------------------------------------------------------------------


class LeaderboardQuery(BaseModel):
    """Typed query parameters for searching and isolating leaderboard entries."""

    model_config = ConfigDict(str_strip_whitespace=True)

    # Game mechanics (optional to allow condensed aggregation across modes/rounds)
    rounds: int | None = Field(default=None, ge=1)
    round_length: RoundLength | None = None
    location_mode: bool | None = None
    date_mode: bool | None = None
    game_mode: GameMode | None = None

    # Dataset filters with strict list typing
    libraries: list[str] = Field(default_factory=list)
    album_ids: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    person_ids: list[str] = Field(default_factory=list)
    people_mode: PeopleMode = PeopleMode.ANY
    min_date: date | None = None
    max_date: date | None = None
    include_shared: bool = False

    # Search, pagination, and matching mode
    player_name: str | None = None
    play_mode: PlayMode | None = None
    challenge_id: str | None = None
    played_after: date | None = None
    played_before: date | None = None
    is_custom_filtered: bool | None = None
    exact_filter_match: bool = True
    limit: int | None = Field(default=None, ge=1)

    @model_validator(mode='before')
    @classmethod
    def normalize_query_inputs(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field in ('libraries', 'album_ids', 'countries', 'cities', 'person_ids'):
                val = data.get(field)
                if isinstance(val, str):
                    data[field] = [x.strip() for x in val.split(',') if x.strip()]
                elif isinstance(val, (list, tuple, set)):
                    cleaned: list[str] = []
                    for item in val:
                        if isinstance(item, str) and ',' in item:
                            cleaned.extend(x.strip() for x in item.split(',') if x.strip())
                        elif str(item).strip():
                            cleaned.append(str(item).strip())
                    data[field] = cleaned
        return data

    @model_validator(mode='after')
    def validate_query_dates(self) -> LeaderboardQuery:
        if self.min_date and self.max_date and self.min_date > self.max_date:
            raise ValueError('min_date cannot be greater than max_date')
        if self.played_after and self.played_before and self.played_after > self.played_before:
            raise ValueError('played_after cannot be greater than played_before')
        return self

    @classmethod
    def from_config(
        cls,
        config: BaseGameConfig,
        *,
        exact_filter_match: bool = True,
        player_name: str | None = None,
        limit: int | None = None,
    ) -> LeaderboardQuery:
        """Construct exact match query directly from a game config instance."""
        return cls(
            rounds=config.round_count,
            round_length=config.round_length,
            location_mode=config.location_mode,
            date_mode=config.date_mode,
            game_mode=config.game_mode,
            libraries=list(config.libraries),
            album_ids=list(config.album_ids),
            countries=list(config.countries),
            cities=list(config.cities),
            person_ids=list(config.person_ids),
            people_mode=config.people_mode,
            min_date=config.min_date,
            max_date=config.max_date,
            include_shared=config.include_shared,
            player_name=player_name,
            exact_filter_match=exact_filter_match,
            limit=limit,
        )


# ---------------------------------------------------------------------------
# Gameplay / Question & Turn Models
# ---------------------------------------------------------------------------


class QuestionRequest(BaseModel):
    """Payload requesting the next question or turn for an active match."""

    model_config = ConfigDict(str_strip_whitespace=True)

    match_id: str = Field(min_length=1)
    played_asset_ids: list[str] = Field(default_factory=list)


class BatchPhotoItem(BaseModel):
    """Photo asset item within an album shuffle batch round."""

    model_config = ConfigDict(str_strip_whitespace=True)

    photo_id: str = Field(min_length=1)
    media_url: str = Field(min_length=1)


class BatchPinItem(BaseModel):
    """Map pin item containing randomized coordinate options in an album shuffle batch round."""

    model_config = ConfigDict(str_strip_whitespace=True)

    pin_id: str = Field(min_length=1)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class QuestionResponse(BaseModel):
    """Turn and question payload delivered to the active player."""

    model_config = ConfigDict(str_strip_whitespace=True)

    question_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    media_url: str = Field(min_length=1)
    player_name: str = Field(min_length=1)
    player_number: int = Field(ge=1)
    total_players: int = Field(ge=1)
    player_round_number: int = Field(ge=1)
    total_rounds_per_player: int = Field(ge=1)
    turn_number: int = Field(ge=1)
    total_turns: int = Field(ge=1)
    location_mode: bool
    date_mode: bool
    game_mode: GameMode = GameMode.pinpoint
    round_length: RoundLength
    batch_photos: list[BatchPhotoItem] | None = None
    batch_pins: list[BatchPinItem] | None = None

    @model_validator(mode='after')
    def validate_turn_and_round_numbers(self) -> QuestionResponse:
        if self.player_number > self.total_players:
            raise ValueError('player_number cannot exceed total_players')
        if self.player_round_number > self.total_rounds_per_player:
            raise ValueError('player_round_number cannot exceed total_rounds_per_player')
        if self.turn_number > self.total_turns:
            raise ValueError('turn_number cannot exceed total_turns')
        return self


# ---------------------------------------------------------------------------
# Answers & Round Acknowledgements
# ---------------------------------------------------------------------------


class AlbumShuffleAnswerItem(BaseModel):
    """Individual photo mapping assignment submitted during an album shuffle round."""

    model_config = ConfigDict(str_strip_whitespace=True)

    photo_id: str = Field(min_length=1)
    assigned_pin_id: str | None = None
    assigned_timeline_index: int | None = Field(default=None, ge=0)


class AnswerRequest(BaseModel):
    """Player guess submission payload containing location, date, or batch shuffle assignments."""

    model_config = ConfigDict(str_strip_whitespace=True)

    match_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    guessed_latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    guessed_longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    guessed_year: int | None = Field(default=None, ge=1826, le=2200)
    guessed_month: int | None = Field(default=None, ge=1, le=12)
    album_shuffle_answers: list[AlbumShuffleAnswerItem] | None = None
    timed_out: bool = False
    time_taken_seconds: float | None = Field(default=None, ge=0.0)

    @model_validator(mode='after')
    def validate_answer_pairs(self) -> AnswerRequest:
        if self.album_shuffle_answers is None:
            if (self.guessed_year is None) != (self.guessed_month is None):
                raise ValueError('guessed_year and guessed_month must be provided together')
            if (self.guessed_latitude is None) != (self.guessed_longitude is None):
                raise ValueError('guessed_latitude and guessed_longitude must be provided together')
        return self


class AnswerResponse(BaseModel):
    """Turn acknowledgement confirming submission and reporting match progress without revealing answers."""

    model_config = ConfigDict(str_strip_whitespace=True)

    player_name: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    round_number: int = Field(ge=1)
    turn_completed: int = Field(ge=1)
    total_turns: int = Field(ge=1)
    round_complete: bool
    waiting_for: list[str]
    match_finished: bool

    @model_validator(mode='after')
    def validate_turn_bounds(self) -> AnswerResponse:
        if self.turn_completed > self.total_turns:
            raise ValueError('turn_completed cannot exceed total_turns')
        return self


# ---------------------------------------------------------------------------
# Results & Match Summaries
# ---------------------------------------------------------------------------


class PlayerRoundResult(BaseModel):
    """Individual player result, score breakdown, and deviation metrics for a completed round."""

    model_config = ConfigDict(str_strip_whitespace=True)

    player_name: str = Field(min_length=1)
    guessed_latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    guessed_longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    guessed_year: int | None = Field(default=None, ge=1826, le=2200)
    guessed_month: int | None = Field(default=None, ge=1, le=12)
    location_score: int | None = Field(default=None, ge=0)
    date_score: int | None = Field(default=None, ge=0)
    round_score: int = Field(ge=0)
    total_score: int = Field(ge=0)
    distance_km: float | None = Field(default=None, ge=0.0)
    date_diff_days: int | None = Field(default=None, ge=0)
    date_diff_months: int | None = Field(default=None, ge=0)
    date_diff_years_part: int | None = Field(default=None, ge=0)
    date_diff_months_part: int | None = Field(default=None, ge=0, le=11)
    date_diff_days_part: int | None = Field(default=None, ge=0, le=31)
    timed_out: bool = False
    album_shuffle_guesses: list[AlbumShuffleAnswerItem] | None = None


class RoundResultRequest(BaseModel):
    """Request payload to retrieve answers and scores for a completed round."""

    model_config = ConfigDict(str_strip_whitespace=True)

    match_id: str = Field(min_length=1)
    round_number: int = Field(ge=1)


class BatchRevealItem(BaseModel):
    """Ground truth location and date details for a photo in an album shuffle batch reveal."""

    model_config = ConfigDict(str_strip_whitespace=True)

    photo_id: str = Field(min_length=1)
    true_pin_id: str | None = None
    actual_latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    actual_longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    actual_date: date | None = None
    actual_year: int | None = Field(default=None, ge=1826, le=2200)
    actual_month: int | None = Field(default=None, ge=1, le=12)
    actual_city: str | None = None
    actual_country: str | None = None


class RoundResultResponse(BaseModel):
    """Full round result reveal containing true answers, player scores, and deviations."""

    round_number: int = Field(ge=1)
    total_rounds: int = Field(ge=1)
    location_mode: bool
    date_mode: bool
    game_mode: GameMode = GameMode.pinpoint
    actual_latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    actual_longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    actual_date: date | None = None
    actual_year: int | None = Field(default=None, ge=1826, le=2200)
    actual_month: int | None = Field(default=None, ge=1, le=12)
    actual_city: str | None = None
    actual_country: str | None = None
    batch_reveal: list[BatchRevealItem] | None = None
    results: list[PlayerRoundResult]
    match_finished: bool
    score_max_points: int = Field(default=SCORE_MAX_POINTS, ge=1)

    @model_validator(mode='after')
    def validate_round_bounds(self) -> RoundResultResponse:
        if self.round_number > self.total_rounds:
            raise ValueError('round_number cannot exceed total_rounds')
        return self


class MatchSummaryPlayer(BaseModel):
    """Aggregated match performance, total score, accuracy, and rank for a single player."""

    model_config = ConfigDict(str_strip_whitespace=True)

    player_name: str = Field(min_length=1)
    location_score: int | None = Field(default=None, ge=0)
    date_score: int | None = Field(default=None, ge=0)
    total_score: int = Field(ge=0)
    max_possible_score: int = Field(ge=0)
    accuracy_pct: float = Field(ge=0.0, le=100.0)
    rank: int = Field(ge=1)
    is_winner: bool


class MatchSummaryResponse(BaseModel):
    """Final match summary containing winner, player rankings, scores, and active filter summaries."""

    model_config = ConfigDict(str_strip_whitespace=True)

    match_id: str = Field(min_length=1)
    rounds_played: int = Field(ge=1)
    location_mode: bool
    date_mode: bool
    game_mode: GameMode = GameMode.pinpoint
    libraries: list[str] = Field(default_factory=list)
    album_names: list[str] = Field(default_factory=list)
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
    """Persistent leaderboard record representing a player's final performance in a completed match."""

    model_config = ConfigDict(str_strip_whitespace=True)

    match_id: str = Field(min_length=1)
    played_at: datetime
    player_name: str = Field(min_length=1)
    total_score: int = Field(ge=0)
    max_possible_score: int = Field(ge=0)
    accuracy_pct: float = Field(ge=0.0, le=100.0)
    rank: int = Field(ge=1)
    is_winner: bool
    game_mode: GameMode
    rounds: int = Field(ge=1)
    play_mode: PlayMode
    is_custom_filtered: bool
    config: MatchConfig

    location_score: int | None = Field(default=None, ge=0)
    date_score: int | None = Field(default=None, ge=0)
    total_time_seconds: float | None = Field(default=None, ge=0.0)
    duration_seconds: float | None = Field(default=None, ge=0.0)
    filter_summary: str | None = None
    challenge_id: str | None = None
    challenge_title: str | None = None
    room_id: str | None = None
    room_name: str | None = None
    awards: list[str] = Field(default_factory=list)
