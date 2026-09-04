"""In-memory match session management, turn tracking, and score accumulation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.immich.client import AssetAnswer
from src.models import GameSetupRequest, PinpointAnswerItem, PinpointDeviation
from src.scoring import DATE_MAX_DECAY_DAYS, LOCATION_MAX_DECAY_KM


class QuestionAlreadyAnsweredError(RuntimeError):
    """Raised when a question receives a second answer submission."""


@dataclass
class RoundAsset:
    """The photo drawn for a round, shared by every player in that round."""

    asset_id: str
    answer: AssetAnswer


@dataclass
class RoundData:
    """Server-selected round assets and prompt data drawn once per match round."""

    assets: list[RoundAsset]
    pins: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class QuestionState:
    """Turn-specific question instance, candidate asset(s), and submitted player response."""

    question_id: str
    player_name: str
    round_index: int
    round_data: RoundData
    answered: bool = False
    location_points: int = 0
    date_points: int = 0
    timed_out: bool = False
    time_taken_seconds: float | None = None
    submitted_at: str | None = None

    # Mode-specific player answers and evaluations
    pinpoint_guess: PinpointAnswerItem | None = None
    pinpoint_deviation: PinpointDeviation | None = None
    album_shuffle_guesses: list[dict[str, Any]] | None = None


@dataclass
class MatchState:
    """Comprehensive in-memory state tracking for an active or finished match session."""

    match_id: str
    setup: GameSetupRequest
    turn_index: int = 0
    finished: bool = False
    questions: dict[str, QuestionState] = field(default_factory=dict)
    scores: dict[str, dict[str, int]] = field(default_factory=dict)
    played_asset_ids: set[str] = field(default_factory=set)
    active_question_id: str | None = None
    asset_pool: dict[str, AssetAnswer] = field(default_factory=dict)
    location_decay_km: float = LOCATION_MAX_DECAY_KM
    date_decay_days: float = DATE_MAX_DECAY_DAYS
    rounds: dict[int, RoundData] = field(default_factory=dict)
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
        """Update last_activity_at timestamp to now."""
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
        """Check whether every player in the round has completed their turn."""
        answered = self.round_questions(round_index)
        return len(answered) == len(self.setup.players) and all(q.answered for q in answered)

    def players_pending_in_round(self, round_index: int) -> list[str]:
        """Return list of players who have not yet answered in the specified round."""
        answered = {q.player_name for q in self.round_questions(round_index) if q.answered}
        return [player for player in self.setup.players if player not in answered]


class SessionStore:
    """In-memory session registry managing active matches and question states."""

    def __init__(self) -> None:
        self._matches: dict[str, MatchState] = {}

    def create_match(self, setup: GameSetupRequest) -> MatchState:
        """Create and register a new match session."""
        match_id = str(uuid4())
        state = MatchState(match_id=match_id, setup=setup)
        self._matches[match_id] = state
        return state

    def get_match(self, match_id: str) -> MatchState:
        """Retrieve active match state or raise KeyError."""
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
        round_data: RoundData,
    ) -> QuestionState:
        """Create and record a new question turn state for the active player."""
        state = self.get_match(match_id)
        question = QuestionState(
            question_id=str(uuid4()),
            player_name=state.current_player_name(),
            round_index=state.current_round_index,
            round_data=round_data,
        )
        state.questions[question.question_id] = question
        state.active_question_id = question.question_id
        for ba in round_data.assets:
            state.played_asset_ids.add(ba.asset_id)
        state.touch()
        return question

    def is_asset_registered(self, asset_id: str) -> bool:
        """Return True when the asset was served as a question in some live match."""
        return any(asset_id in match.played_asset_ids for match in self._matches.values())

    def _finalize_question_score(
        self,
        state: MatchState,
        question: QuestionState,
        location_points: int,
        date_points: int,
        timed_out: bool,
        time_taken_seconds: float | None,
    ) -> MatchState:
        question.answered = True
        question.location_points = location_points
        question.date_points = date_points
        question.timed_out = timed_out
        question.time_taken_seconds = time_taken_seconds
        question.submitted_at = datetime.now(timezone.utc).isoformat()

        if state.active_question_id == question.question_id:
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

    def apply_pinpoint_score(
        self,
        match_id: str,
        question_id: str,
        location_points: int,
        date_points: int,
        guess: PinpointAnswerItem,
        deviation: PinpointDeviation,
        timed_out: bool = False,
        time_taken_seconds: float | None = None,
    ) -> MatchState:
        """Apply points and pinpoint guess/deviation metrics to an active question."""
        state = self.get_match(match_id)
        question = state.questions.get(question_id)
        if question is None:
            raise KeyError(f'Unknown question_id: {question_id}')
        if question.answered:
            raise QuestionAlreadyAnsweredError(f'Question already answered: {question_id}')

        question.pinpoint_guess = guess
        question.pinpoint_deviation = deviation
        return self._finalize_question_score(
            state, question, location_points, date_points, timed_out, time_taken_seconds
        )

    def apply_album_shuffle_score(
        self,
        match_id: str,
        question_id: str,
        location_points: int,
        date_points: int,
        album_shuffle_guesses: list[dict[str, Any]],
        timed_out: bool = False,
        time_taken_seconds: float | None = None,
    ) -> MatchState:
        """Apply points and album shuffle assignments to an active question."""
        state = self.get_match(match_id)
        question = state.questions.get(question_id)
        if question is None:
            raise KeyError(f'Unknown question_id: {question_id}')
        if question.answered:
            raise QuestionAlreadyAnsweredError(f'Question already answered: {question_id}')

        question.album_shuffle_guesses = album_shuffle_guesses
        return self._finalize_question_score(
            state, question, location_points, date_points, timed_out, time_taken_seconds
        )

    def cleanup_expired_matches(self, ttl_seconds: int = 7200) -> int:
        """Prune inactive matches older than ttl_seconds (default 2 hours)."""
        now = time.time()
        expired = [
            match_id for match_id, state in self._matches.items() if (now - state.last_activity_at) > ttl_seconds
        ]
        for match_id in expired:
            del self._matches[match_id]
        return len(expired)
