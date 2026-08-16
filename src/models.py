from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class SyncStatus(str, Enum):
    idle = 'idle'
    syncing = 'syncing'
    error = 'error'
    never_synced = 'never_synced'


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
    score_max_points: int = 100


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
    config: dict = Field(default_factory=dict)
