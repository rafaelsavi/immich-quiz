from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import uuid4

from src.immich.client import AssetAnswer
from src.models import GameSetupRequest


class QuestionAlreadyAnsweredError(RuntimeError):
    """Raised when a question receives a second answer submission."""


@dataclass
class RoundAsset:
    """The photo drawn for a round, shared by every player in that round."""

    asset_id: str
    answer: AssetAnswer


@dataclass
class QuestionState:
    question_id: str
    asset_id: str
    player_name: str
    round_index: int
    actual_latitude: float | None
    actual_longitude: float | None
    actual_date: date | None
    actual_city: str | None = None
    actual_country: str | None = None
    answered: bool = False
    guessed_latitude: float | None = None
    guessed_longitude: float | None = None
    guessed_year: int | None = None
    guessed_month: int | None = None
    location_points: int = 0
    date_points: int = 0
    distance_km: float | None = None
    date_diff_days: int | None = None
    date_diff_months: int | None = None
    timed_out: bool = False
    batch_assets: list[RoundAsset] | None = None
    batch_pins: list[dict[str, Any]] | None = None
    album_shuffle_guesses: list[dict[str, Any]] | None = None


@dataclass
class MatchState:
    match_id: str
    setup: GameSetupRequest
    turn_index: int = 0
    finished: bool = False
    questions: dict[str, QuestionState] = field(default_factory=dict)
    scores: dict[str, dict[str, int]] = field(default_factory=dict)
    played_asset_ids: set[str] = field(default_factory=set)
    active_question_id: str | None = None
    asset_pool: dict[str, AssetAnswer] = field(default_factory=dict)
    round_assets: dict[int, RoundAsset] = field(default_factory=dict)
    batch_round_assets: dict[int, list[RoundAsset]] = field(default_factory=dict)
    batch_round_pins: dict[int, list[dict[str, object]]] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.scores:
            self.scores = {player: {'location': 0, 'date': 0, 'total': 0} for player in self.setup.players}
        now = time.time()
        if not self.created_at:
            self.created_at = now
        self.last_activity_at = now

    def touch(self) -> None:
        self.last_activity_at = time.time()

    @property
    def total_turns(self) -> int:
        return self.setup.round_count * len(self.setup.players)

    @property
    def current_round_index(self) -> int:
        return self.turn_index // len(self.setup.players)

    def current_player_name(self) -> str:
        player_index = self.turn_index % len(self.setup.players)
        return self.setup.players[player_index]

    def current_player_round(self) -> int:
        return self.current_round_index + 1

    def round_questions(self, round_index: int) -> list[QuestionState]:
        """Questions issued for a round, ordered by the match player order."""
        by_player = {
            question.player_name: question
            for question in self.questions.values()
            if question.round_index == round_index
        }
        return [by_player[player] for player in self.setup.players if player in by_player]

    def is_round_complete(self, round_index: int) -> bool:
        answered = self.round_questions(round_index)
        return len(answered) == len(self.setup.players) and all(q.answered for q in answered)

    def players_pending_in_round(self, round_index: int) -> list[str]:
        answered = {q.player_name for q in self.round_questions(round_index) if q.answered}
        return [player for player in self.setup.players if player not in answered]


class SessionStore:
    def __init__(self) -> None:
        self._matches: dict[str, MatchState] = {}

    def create_match(self, setup: GameSetupRequest) -> MatchState:
        match_id = str(uuid4())
        state = MatchState(match_id=match_id, setup=setup)
        self._matches[match_id] = state
        return state

    def get_match(self, match_id: str) -> MatchState:
        state = self._matches.get(match_id)
        if state is None:
            raise KeyError(f'Unknown match_id: {match_id}')
        state.touch()
        return state

    def active_question(self, match_id: str) -> QuestionState | None:
        """Return the issued-but-unanswered question for the current turn, if any.

        Reusing it stops a new asset being drawn each time the client
        re-requests a question for the same turn.
        """
        state = self.get_match(match_id)
        if state.active_question_id is None:
            return None
        question = state.questions.get(state.active_question_id)
        if question is None or question.answered:
            return None
        return question

    def register_question(
        self,
        match_id: str,
        asset_id: str,
        actual_latitude: float | None,
        actual_longitude: float | None,
        actual_date: date | None,
        actual_city: str | None = None,
        actual_country: str | None = None,
        batch_assets: list[RoundAsset] | None = None,
        batch_pins: list[dict[str, object]] | None = None,
    ) -> QuestionState:
        state = self.get_match(match_id)
        question = QuestionState(
            question_id=str(uuid4()),
            asset_id=asset_id,
            player_name=state.current_player_name(),
            round_index=state.current_round_index,
            actual_latitude=actual_latitude,
            actual_longitude=actual_longitude,
            actual_date=actual_date,
            actual_city=actual_city,
            actual_country=actual_country,
            batch_assets=batch_assets,
            batch_pins=batch_pins,
        )
        state.questions[question.question_id] = question
        state.active_question_id = question.question_id
        if batch_assets:
            for ba in batch_assets:
                state.played_asset_ids.add(ba.asset_id)
        else:
            state.played_asset_ids.add(asset_id)
        state.touch()
        return question

    def is_asset_registered(self, asset_id: str) -> bool:
        """Return True when the asset was served as a question in some live match."""
        return any(asset_id in match.played_asset_ids for match in self._matches.values())

    def apply_score(
        self,
        match_id: str,
        question_id: str,
        location_points: int,
        date_points: int,
        guessed_latitude: float | None = None,
        guessed_longitude: float | None = None,
        guessed_year: int | None = None,
        guessed_month: int | None = None,
        distance_km: float | None = None,
        diff_days: int | None = None,
        diff_months: int | None = None,
        timed_out: bool = False,
        album_shuffle_guesses: list[dict[str, Any]] | None = None,
    ) -> MatchState:
        state = self.get_match(match_id)
        question = state.questions.get(question_id)
        if question is None:
            raise KeyError(f'Unknown question_id: {question_id}')
        if question.answered:
            raise QuestionAlreadyAnsweredError(f'Question already answered: {question_id}')

        question.answered = True
        question.guessed_latitude = guessed_latitude
        question.guessed_longitude = guessed_longitude
        question.guessed_year = guessed_year
        question.guessed_month = guessed_month
        question.location_points = location_points
        question.date_points = date_points
        question.distance_km = distance_km
        question.date_diff_days = diff_days
        question.date_diff_months = diff_months
        question.timed_out = timed_out
        question.album_shuffle_guesses = album_shuffle_guesses

        if state.active_question_id == question_id:
            state.active_question_id = None

        bucket = state.scores[question.player_name]
        bucket['location'] += location_points
        bucket['date'] += date_points
        bucket['total'] += location_points + date_points

        state.turn_index += 1
        if state.turn_index >= state.total_turns:
            state.finished = True
        state.touch()
        return state

    def cleanup_expired_matches(self, ttl_seconds: int = 7200) -> int:
        """Prune inactive matches older than ttl_seconds (default 2 hours)."""
        now = time.time()
        expired = [
            match_id for match_id, state in self._matches.items() if (now - state.last_activity_at) > ttl_seconds
        ]
        for match_id in expired:
            del self._matches[match_id]
        return len(expired)
