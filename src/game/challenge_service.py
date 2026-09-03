"""Challenge mode orchestration service delegating scoring to GameMode engines."""

from __future__ import annotations

import math
import random
from datetime import date
from typing import Any

from fastapi import HTTPException

from src.app_logging import LOGGER_MATCH, get_logger
from src.config import AppSettings
from src.game.selector import calculate_match_bounds, generate_batch_pins, is_asset_valid_for_batch
from src.immich.client import AssetAnswer
from src.models import (
    BatchPhotoItem,
    BatchPinItem,
    BatchRevealItem,
    ChallengeAnswerRequest,
    ChallengeAnswerResponse,
    ChallengeCreateRequest,
    ChallengeQuestionResponse,
    GameMode,
    MapBounds,
    RoundLength,
)
from src.scoring import (
    SCORE_MAX_POINTS,
    batch_exponential_date_score,
    batch_exponential_location_score,
    calculate_date_decay,
    calculate_location_decay,
    haversine_km,
)
from src.storage.challenge import ChallengeStore
from src.storage.leaderboard import LeaderboardStore
from src.storage.metadata import AssetFilterCriteria, MetadataStore
from src.storage.session import RoundAsset

logger = get_logger(LOGGER_MATCH)


def select_diverse_challenge_assets(
    candidates: dict[str, AssetAnswer],
    count: int,
    location_mode: bool,
    date_mode: bool,
) -> list[RoundAsset]:
    """Select count diverse assets from candidate pool with fallback."""
    shuffled_ids = list(candidates.keys())
    random.shuffle(shuffled_ids)

    selected: list[RoundAsset] = []
    # Primary pass: greedily pick diverse assets
    for aid in shuffled_ids:
        ans = candidates[aid]
        if is_asset_valid_for_batch(
            ans,
            selected,
            location_mode=location_mode,
            date_mode=date_mode,
        ):
            selected.append(RoundAsset(asset_id=aid, answer=ans))
            if len(selected) == count:
                break

    # Fallback pass: fill remaining slots with distinct unplayed candidates
    if len(selected) < count:
        selected_ids = {ra.asset_id for ra in selected}
        for aid in shuffled_ids:
            if aid not in selected_ids:
                selected.append(RoundAsset(asset_id=aid, answer=candidates[aid]))
                if len(selected) == count:
                    break

    return selected


def get_challenge_total_rounds(
    challenge_or_config: dict[str, Any],
    asset_ids: list[str] | None = None,
) -> int:
    """Calculate the total number of rounds for a challenge based on game mode and asset pool."""
    if 'config' in challenge_or_config and isinstance(challenge_or_config['config'], dict):
        config = challenge_or_config['config']
        assets = asset_ids if asset_ids is not None else challenge_or_config.get('asset_ids', [])
    else:
        config = challenge_or_config
        assets = asset_ids or []

    game_mode = config.get('game_mode', 'pinpoint')
    if str(game_mode).lower() in ('album_shuffle', 'gamemode.album_shuffle'):
        return len(config.get('round_batches', []))
    return len(assets)


class ChallengeService:
    """Orchestrates challenge creation, question delivery, and scoring.

    Delegates scoring to the same exponential decay functions used by local mode,
    using pre-computed decay constants frozen in config_json at creation time.
    """

    def __init__(
        self,
        challenge_store: ChallengeStore,
        metadata_store: MetadataStore,
        leaderboard_store: LeaderboardStore,
        settings: AppSettings,
    ) -> None:
        self.challenge_store = challenge_store
        self.metadata_store = metadata_store
        self.leaderboard_store = leaderboard_store
        self.settings = settings

    def create_challenge(
        self,
        setup: ChallengeCreateRequest,
        base_url: str,
    ) -> dict[str, Any]:
        """Create a deterministic challenge seed with frozen scoring parameters."""
        # Resolve human-readable album and person names if not already populated
        if setup.albums and not setup.album_names:
            album_names_map = self.metadata_store.get_album_names(setup.albums)
            setup.album_names = [album_names_map.get(aid, aid) for aid in setup.albums]
        if setup.people and not setup.person_names:
            person_names_map = self.metadata_store.get_person_names(setup.people)
            setup.person_names = [person_names_map.get(pid, pid) for pid in setup.people]

        criteria = AssetFilterCriteria.from_setup(setup, self.settings)
        game_mode = setup.game_mode

        # Determine required asset count
        batch_size = 3 if game_mode == GameMode.album_shuffle else 1
        required = setup.round_count * batch_size

        candidates = self.metadata_store.fetch_candidate_assets(criteria, limit=max(250, required * 5))
        if len(candidates) < required:
            raise HTTPException(
                status_code=400,
                detail=f'Insufficient eligible photos. Found {len(candidates)}, need {required}.',
            )

        # Select diverse assets using diversity engine
        selected = select_diverse_challenge_assets(
            candidates,
            required,
            location_mode=setup.location_mode,
            date_mode=setup.date_mode,
        )
        asset_ids = [ra.asset_id for ra in selected]

        # Pre-compute scoring decay constants from the selected pool
        location_decay_km = calculate_location_decay(selected) if setup.location_mode else None
        date_decay_days = calculate_date_decay(selected) if setup.date_mode else None
        map_bounds = calculate_match_bounds([ra.answer for ra in selected]) if setup.location_mode else None

        # Build config_json with frozen scoring parameters
        config = setup.model_dump(mode='json')
        config['location_decay_km'] = location_decay_km
        config['date_decay_days'] = date_decay_days
        config['map_bounds'] = map_bounds.model_dump() if map_bounds else None

        # Generate filter summary for display and auto-title
        _, filter_summary = setup.format_filter_summary(language=self.settings.language)
        filter_tooltip = setup.format_filter_tooltip(language=self.settings.language)
        config['filter_summary'] = filter_summary
        config['filter_tooltip'] = filter_tooltip

        # Album Shuffle: pre-assign batch groupings and randomized pins
        if game_mode == GameMode.album_shuffle:
            round_batches = [list(range(i * batch_size, (i + 1) * batch_size)) for i in range(setup.round_count)]
            config['batch_size'] = batch_size
            config['round_batches'] = round_batches
            # Pre-generate pins for each round batch
            batch_pins: dict[str, list[dict[str, object]]] = {}
            for round_idx, indices in enumerate(round_batches):
                batch_assets = [selected[i] for i in indices]
                pins = generate_batch_pins(batch_assets, location_mode=setup.location_mode)
                batch_pins[str(round_idx)] = pins
            config['batch_pins'] = batch_pins

        # Auto-generate title if not provided
        title = setup.title
        if not title:
            title = f"{setup.creator_name}'s {filter_summary} Challenge"

        record = self.challenge_store.create_challenge(
            creator_name=setup.creator_name,
            libraries=list(setup.libraries) if setup.libraries else None,
            config=config,
            asset_ids=asset_ids,
            title=title,
            expires_in_hours=setup.expires_in_hours,
        )

        play_url = f'{base_url.rstrip("/")}/play/{record["capability_token"]}'

        return {
            **record,
            'play_url': play_url,
            'title': title,
            'game_mode': game_mode.value,
            'rounds': setup.round_count,
        }

    def get_question(
        self,
        challenge: dict[str, Any],
        round_index: int,
    ) -> ChallengeQuestionResponse:
        """Build question payload for round N without exposing answer data."""
        config = challenge['config']
        asset_ids = challenge['asset_ids']
        game_mode = GameMode(config.get('game_mode', 'pinpoint'))

        if game_mode == GameMode.album_shuffle:
            round_batches = config.get('round_batches', [])
            if round_index < 0 or round_index >= len(round_batches):
                raise HTTPException(status_code=400, detail='Invalid round index for album shuffle.')
            batch_indices = round_batches[round_index]
            batch_asset_ids = [asset_ids[i] for i in batch_indices]

            batch_photos = [
                BatchPhotoItem(
                    photo_id=aid,
                    media_url=f'/api/media/{aid}',
                )
                for aid in batch_asset_ids
            ]

            raw_pins = config.get('batch_pins', {}).get(str(round_index), [])
            batch_pins = (
                [
                    BatchPinItem(
                        pin_id=str(p['pin_id']),
                        latitude=float(p['latitude']),
                        longitude=float(p['longitude']),
                    )
                    for p in raw_pins
                    if p.get('latitude') is not None and p.get('longitude') is not None
                ]
                if config.get('location_mode', True)
                else None
            )

            return ChallengeQuestionResponse(
                round_index=round_index,
                total_rounds=len(round_batches),
                asset_id=batch_asset_ids[0],
                media_url=f'/api/media/{batch_asset_ids[0]}',
                game_mode=game_mode,
                location_mode=bool(config.get('location_mode', True)),
                date_mode=bool(config.get('date_mode', True)),
                round_length=RoundLength(config.get('round_length', '1m')),
                map_bounds=MapBounds(**config['map_bounds']) if config.get('map_bounds') else None,
                batch_photos=batch_photos,
                batch_pins=batch_pins,
            )

        # Pinpoint: single photo
        if round_index < 0 or round_index >= len(asset_ids):
            raise HTTPException(status_code=400, detail='Invalid round index for pinpoint.')

        target_asset_id = asset_ids[round_index]
        return ChallengeQuestionResponse(
            round_index=round_index,
            total_rounds=len(asset_ids),
            asset_id=target_asset_id,
            media_url=f'/api/media/{target_asset_id}',
            game_mode=game_mode,
            location_mode=bool(config.get('location_mode', True)),
            date_mode=bool(config.get('date_mode', True)),
            round_length=RoundLength(config.get('round_length', '1m')),
            map_bounds=MapBounds(**config['map_bounds']) if config.get('map_bounds') else None,
        )

    def score_and_persist_answer(
        self,
        challenge: dict[str, Any],
        session: dict[str, Any],
        body: ChallengeAnswerRequest,
    ) -> ChallengeAnswerResponse:
        """Score a round answer using frozen decay constants and persist to match_round_guesses.

        Returns the personal round reveal with actual answer data (server enforces
        Fog of War — this player only sees their own result).
        """
        config = challenge['config']
        asset_ids = challenge['asset_ids']
        game_mode = GameMode(config.get('game_mode', 'pinpoint'))
        location_mode = bool(config.get('location_mode', True))
        date_mode = bool(config.get('date_mode', True))

        # Frozen decay constants from creation time
        location_decay_km = config.get('location_decay_km')
        date_decay_days = config.get('date_decay_days')

        # Server-side timer grace window validation
        round_length = RoundLength(config.get('round_length', '1m'))
        max_seconds = round_length.seconds
        if max_seconds and body.time_taken_seconds > max_seconds + 5.0 and not body.timed_out:
            logger.warning(
                'Challenge %s: Player %r round %d exceeded timer (%.1fs > %ds + 5s grace)',
                challenge['challenge_id'],
                session['player_name'],
                body.round_index,
                body.time_taken_seconds,
                max_seconds,
            )
            body.timed_out = True

        if game_mode == GameMode.album_shuffle:
            return self._score_album_shuffle(
                challenge,
                session,
                body,
                config,
                asset_ids,
                location_mode,
                date_mode,
                location_decay_km,
                date_decay_days,
            )

        return self._score_pinpoint(
            challenge,
            session,
            body,
            config,
            asset_ids,
            location_mode,
            date_mode,
            location_decay_km,
            date_decay_days,
        )

    def _score_pinpoint(
        self,
        challenge: dict[str, Any],
        session: dict[str, Any],
        body: ChallengeAnswerRequest,
        config: dict[str, Any],
        asset_ids: list[str],
        location_mode: bool,
        date_mode: bool,
        location_decay_km: float | None,
        date_decay_days: float | None,
    ) -> ChallengeAnswerResponse:
        """Score a Pinpoint round using the same exponential decay as local mode."""
        if body.round_index < 0 or body.round_index >= len(asset_ids):
            raise HTTPException(status_code=400, detail='Invalid round index for pinpoint.')

        target_asset_id = asset_ids[body.round_index]
        asset = self.metadata_store.get_asset_answer(target_asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail='Photo asset not found.')

        # Location scoring: 100 * e^(-distance_km / decay_km)
        distance_km: float | None = None
        location_points: int = 0
        if (
            location_mode
            and location_decay_km
            and location_decay_km > 0
            and body.guessed_latitude is not None
            and body.guessed_longitude is not None
            and asset.latitude is not None
            and asset.longitude is not None
        ):
            distance_km = haversine_km(
                asset.latitude,
                asset.longitude,
                body.guessed_latitude,
                body.guessed_longitude,
            )
            location_points = round(SCORE_MAX_POINTS * math.exp(-distance_km / location_decay_km))

        # Date scoring: 100 * e^(-date_diff_days / decay_days)
        date_diff: int | None = None
        date_diff_months: int | None = None
        date_points: int = 0
        if (
            date_mode
            and date_decay_days
            and date_decay_days > 0
            and body.guessed_year is not None
            and body.guessed_month is not None
            and asset.capture_date is not None
        ):
            guess_date = date(body.guessed_year, body.guessed_month, 1)
            actual_mid = date(asset.capture_date.year, asset.capture_date.month, 15)
            date_diff = abs((guess_date - actual_mid).days)
            date_diff_months = abs(
                (body.guessed_year - asset.capture_date.year) * 12 + (body.guessed_month - asset.capture_date.month)
            )
            date_points = round(SCORE_MAX_POINTS * math.exp(-date_diff / date_decay_days))

        round_score = location_points + date_points
        total_rounds = get_challenge_total_rounds(challenge)
        is_final = body.round_index >= total_rounds - 1

        # Persist round guess using existing leaderboard schema
        guess_date_str = (
            f'{body.guessed_year:04d}-{body.guessed_month:02d}-01'
            if body.guessed_year is not None and body.guessed_month is not None
            else None
        )
        self.leaderboard_store.record_challenge_round_guess(
            match_id=session['match_id'],
            challenge_id=challenge['challenge_id'],
            player_name=session['player_name'],
            round_index=body.round_index,
            photo_index=0,
            game_mode='pinpoint',
            asset_id=target_asset_id,
            guess_latitude=body.guessed_latitude,
            guess_longitude=body.guessed_longitude,
            actual_latitude=asset.latitude,
            actual_longitude=asset.longitude,
            actual_city=asset.city,
            actual_country=asset.country,
            distance_km=distance_km,
            location_points=location_points if location_mode else None,
            guess_date=guess_date_str,
            actual_date=asset.capture_date.isoformat() if asset.capture_date else None,
            date_diff_days=date_diff,
            date_points=date_points if date_mode else None,
            round_score=round_score,
            time_taken_seconds=body.time_taken_seconds,
        )

        # Advance session state
        self.challenge_store.advance_session(
            session['session_token'],
            round_index=body.round_index,
            location_points=location_points,
            date_points=date_points,
            round_score=round_score,
            time_taken_seconds=body.time_taken_seconds,
            is_final=is_final,
        )

        # Finalize match entry if last round
        if is_final:
            updated_session = self.challenge_store.get_player_session(session['session_token'])
            if updated_session:
                self._finalize_player_match(challenge, updated_session, total_rounds)

        updated = self.challenge_store.get_player_session(session['session_token'])

        return ChallengeAnswerResponse(
            round_index=body.round_index,
            round_score=round_score,
            location_score=location_points if location_mode else None,
            date_score=date_points if date_mode else None,
            distance_km=distance_km,
            date_diff_days=date_diff,
            date_diff_months=date_diff_months,
            actual_latitude=asset.latitude,
            actual_longitude=asset.longitude,
            actual_date=asset.capture_date,
            actual_year=asset.capture_date.year if asset.capture_date else None,
            actual_month=asset.capture_date.month if asset.capture_date else None,
            actual_city=asset.city,
            actual_country=asset.country,
            game_mode=GameMode.pinpoint,
            is_game_over=is_final,
            total_score=updated['total_score'] if updated else round_score,
            total_time_seconds=updated['total_time_seconds'] if updated else body.time_taken_seconds,
            player_color=session.get('player_color'),
        )

    def _score_album_shuffle(
        self,
        challenge: dict[str, Any],
        session: dict[str, Any],
        body: ChallengeAnswerRequest,
        config: dict[str, Any],
        asset_ids: list[str],
        location_mode: bool,
        date_mode: bool,
        location_decay_km: float | None,
        date_decay_days: float | None,
    ) -> ChallengeAnswerResponse:
        """Score an Album Shuffle round using batch partial credit and frozen decay parameters."""
        total_rounds = get_challenge_total_rounds(challenge)
        if body.round_index < 0 or body.round_index >= total_rounds:
            raise HTTPException(status_code=400, detail='Invalid round index.')

        round_batches = config.get('round_batches', [])

        batch_indices = round_batches[body.round_index]
        batch_asset_ids = [asset_ids[i] for i in batch_indices]
        batch_assets: list[RoundAsset] = []
        for aid in batch_asset_ids:
            ans = self.metadata_store.get_asset_answer(aid)
            if not ans:
                raise HTTPException(status_code=404, detail=f'Photo asset {aid} not found.')
            batch_assets.append(RoundAsset(asset_id=aid, answer=ans))

        raw_pins = config.get('batch_pins', {}).get(str(body.round_index), [])
        answers = body.album_shuffle_answers or []
        assigned_pins = {ans.photo_id: ans.assigned_pin_id for ans in answers}
        assigned_timeline = {ans.photo_id: ans.assigned_timeline_index for ans in answers}

        true_pin_map = {str(bp['true_asset_id']): str(bp['pin_id']) for bp in raw_pins}
        pin_coords = {
            str(bp['pin_id']): (
                float(bp['latitude']) if bp.get('latitude') is not None else None,
                float(bp['longitude']) if bp.get('longitude') is not None else None,
            )
            for bp in raw_pins
        }
        photo_coords = {ba.asset_id: (ba.answer.latitude, ba.answer.longitude) for ba in batch_assets}
        photo_dates = {ba.asset_id: ba.answer.capture_date for ba in batch_assets}

        # Location scoring via batch exponential decay
        if location_mode and location_decay_km is not None and location_decay_km > 0:
            location_points, _, _ = batch_exponential_location_score(
                assigned_pins=assigned_pins,
                true_pin_map=true_pin_map,
                pin_coords=pin_coords,
                photo_coords=photo_coords,
                decay_km=location_decay_km,
            )
        else:
            location_points = 0

        # Date scoring via batch exponential decay
        if date_mode and date_decay_days is not None and date_decay_days > 0:
            date_points, _, _ = batch_exponential_date_score(
                assigned_timeline=assigned_timeline,
                photo_dates=photo_dates,
                decay_days=date_decay_days,
            )
        else:
            date_points = 0

        round_score = location_points + date_points
        is_final = body.round_index >= total_rounds - 1

        # Calculate per-photo breakdowns and persist to match_round_guesses
        sorted_by_date = sorted(batch_assets, key=lambda a: a.answer.capture_date or date.min, reverse=False)
        true_rank_map = {a.asset_id: idx for idx, a in enumerate(sorted_by_date)}
        slot_target_dates = [a.answer.capture_date or date.min for a in sorted_by_date]
        total_photos = len(batch_assets)
        per_photo_pts = (SCORE_MAX_POINTS / total_photos) if total_photos > 0 else 0.0
        pin_by_id = {str(bp['pin_id']): bp for bp in raw_pins}

        for idx, ba in enumerate(batch_assets):
            assigned_pin_id = assigned_pins.get(ba.asset_id)
            assigned_timeline_index = assigned_timeline.get(ba.asset_id)
            assigned_pin = pin_by_id.get(assigned_pin_id) if assigned_pin_id else None

            guess_lat = (
                float(assigned_pin['latitude']) if assigned_pin and assigned_pin.get('latitude') is not None else None
            )
            guess_lng = (
                float(assigned_pin['longitude']) if assigned_pin and assigned_pin.get('longitude') is not None else None
            )

            dist_km: float | None = None
            if (
                guess_lat is not None
                and guess_lng is not None
                and ba.answer.latitude is not None
                and ba.answer.longitude is not None
            ):
                if assigned_pin_id and assigned_pin_id == true_pin_map.get(ba.asset_id):
                    dist_km = 0.0
                else:
                    dist_km = haversine_km(ba.answer.latitude, ba.answer.longitude, guess_lat, guess_lng)

            if location_mode:
                is_correct_loc: int | None = (
                    1 if (ba.asset_id in true_pin_map and assigned_pin_id == true_pin_map[ba.asset_id]) else 0
                )
                if dist_km is not None and location_decay_km is not None and location_decay_km > 0:
                    loc_photo_pts: int | None = round(per_photo_pts * math.exp(-dist_km / location_decay_km))
                else:
                    loc_photo_pts = 0
            else:
                is_correct_loc = None
                loc_photo_pts = None

            diff_days: int | None = None
            if date_mode:
                p_date = ba.answer.capture_date or date.min
                if assigned_timeline_index is not None and 0 <= assigned_timeline_index < total_photos:
                    target_date = slot_target_dates[assigned_timeline_index]
                    d_days = abs((p_date - target_date).days)
                    diff_days = d_days
                    is_correct_date: int | None = (
                        1 if (assigned_timeline_index == true_rank_map.get(ba.asset_id) or p_date == target_date) else 0
                    )
                    dt_photo_pts: int | None = (
                        round(per_photo_pts * math.exp(-d_days / date_decay_days))
                        if (date_decay_days is not None and date_decay_days > 0)
                        else 0
                    )
                else:
                    is_correct_date = 0
                    dt_photo_pts = 0
            else:
                is_correct_date = None
                dt_photo_pts = None

            photo_score = (loc_photo_pts or 0) + (dt_photo_pts or 0)

            self.leaderboard_store.record_challenge_round_guess(
                match_id=session['match_id'],
                challenge_id=challenge['challenge_id'],
                player_name=session['player_name'],
                round_index=body.round_index,
                photo_index=idx,
                game_mode='album_shuffle',
                asset_id=ba.asset_id,
                guess_latitude=guess_lat,
                guess_longitude=guess_lng,
                actual_latitude=ba.answer.latitude,
                actual_longitude=ba.answer.longitude,
                actual_city=ba.answer.city,
                actual_country=ba.answer.country,
                distance_km=dist_km,
                location_points=loc_photo_pts,
                guess_date=None,
                actual_date=ba.answer.capture_date.isoformat() if ba.answer.capture_date else None,
                date_diff_days=diff_days,
                date_points=dt_photo_pts,
                round_score=photo_score,
                is_correct_location=is_correct_loc,
                is_correct_date_order=is_correct_date,
                time_taken_seconds=body.time_taken_seconds,
                assigned_pin_id=str(assigned_pin_id) if assigned_pin_id else None,
                assigned_timeline_index=assigned_timeline_index,
            )

        # Advance session state
        self.challenge_store.advance_session(
            session['session_token'],
            round_index=body.round_index,
            location_points=location_points,
            date_points=date_points,
            round_score=round_score,
            time_taken_seconds=body.time_taken_seconds,
            is_final=is_final,
        )

        # Finalize match entry if last round
        if is_final:
            updated_session = self.challenge_store.get_player_session(session['session_token'])
            if updated_session:
                self._finalize_player_match(challenge, updated_session, total_rounds)

        updated = self.challenge_store.get_player_session(session['session_token'])

        batch_reveal = [
            BatchRevealItem(
                photo_id=ba.asset_id,
                true_pin_id=true_pin_map.get(ba.asset_id),
                actual_latitude=ba.answer.latitude,
                actual_longitude=ba.answer.longitude,
                actual_date=ba.answer.capture_date,
                actual_year=ba.answer.capture_date.year if ba.answer.capture_date else None,
                actual_month=ba.answer.capture_date.month if ba.answer.capture_date else None,
                actual_city=ba.answer.city,
                actual_country=ba.answer.country,
            )
            for ba in batch_assets
        ]

        return ChallengeAnswerResponse(
            round_index=body.round_index,
            round_score=round_score,
            location_score=location_points if location_mode else None,
            date_score=date_points if date_mode else None,
            game_mode=GameMode.album_shuffle,
            batch_reveal=batch_reveal,
            is_game_over=is_final,
            total_score=updated['total_score'] if updated else round_score,
            total_time_seconds=updated['total_time_seconds'] if updated else body.time_taken_seconds,
            player_color=session.get('player_color'),
        )

    def _finalize_player_match(
        self,
        challenge: dict[str, Any],
        session: dict[str, Any],
        total_rounds: int,
    ) -> None:
        """Create match and match_entry records when a player finishes all rounds."""
        config = challenge['config']
        self.leaderboard_store.finalize_challenge_player_match(
            match_id=session['match_id'],
            challenge_id=challenge['challenge_id'],
            config=config,
            player_name=session['player_name'],
            location_score=session.get('location_score', 0),
            date_score=session.get('date_score', 0),
            total_score=session['total_score'],
            total_rounds=total_rounds,
            total_time_seconds=session['total_time_seconds'],
            libraries=challenge.get('libraries'),
        )
        logger.info(
            '🏁 Challenge %s: Player %r finished (score=%d, time=%.1fs)',
            challenge['challenge_id'],
            session['player_name'],
            session['total_score'],
            session['total_time_seconds'],
        )
