"""Asset selection, diversity sampling, and map bounding box calculations.

This module provides the core asset selection engine for the quiz game, including:
- **Pool Ingestion & Caching**: Loading candidate assets per match from the fast indexed SQLite
  metadata store (`MetadataStore`) or falling back to the Immich Search API.
- **Smart Map Bounds**: Calculating match-wide geographic bounding boxes with anti-spoiler guards.
- **Photo Diversity Engine**: Preventing near-duplicate burst photos or tightly clustered locations
  through spatial (Haversine distance) and temporal (capture time delta) constraints.
- **Round Selection Algorithms**: Single-photo selection (`select_round_asset`) and batch selection
  (`select_batch_round_assets`) with multi-pass diversity prioritization and graceful fallback.
- **Pin Labeling**: Generating randomized pin identifiers ('A', 'B', 'C'...) for multi-photo and
  pin-matching game modes.
"""

from __future__ import annotations

import logging
import random
from datetime import date
from typing import Any

from src.immich.client import AssetAnswer, ImmichClient
from src.models import MapBounds
from src.scoring import calculate_date_decay, calculate_location_decay, haversine_km
from src.storage.metadata import AssetFilterCriteria, MetadataStore
from src.storage.session import MatchState, RoundAsset

logger = logging.getLogger('immich_quiz.match')

# Hardcoded Smart Map Zoom internal safeguards:
# Maximum geographic diagonal distance (in kilometers) before the match is considered global.
# If exceeded, the map view defaults to the global world view to prevent giving away spoilers.
SMART_MAP_ZOOM_MAX_SPAN_KM: float = 5000.0

# Internal Photo Diversity sampling parameters (soft prioritization thresholds):
# Minimum spatial separation (in kilometers) between selected photos when location mode is active.
DEFAULT_PHOTO_DIVERSITY_MIN_DISTANCE_KM: float = 0.1

# Minimum temporal separation (in seconds) between selected photos when date mode is active.
DEFAULT_PHOTO_DIVERSITY_MIN_TIME_SECONDS: float = 60.0


def calculate_match_bounds(
    pool: list[AssetAnswer] | dict[str, AssetAnswer],
    max_span_km: float = SMART_MAP_ZOOM_MAX_SPAN_KM,
) -> MapBounds | None:
    """Calculate the geographic bounding box for the match asset pool.

    Anti-spoiler & Privacy safeguards:
    - Computed match-wide across the whole pool (never per-photo).
    - If photos span globally (> max_span_km or > 60 deg lat / 90 deg lng), returns None
      so the client defaults cleanly to standard world view.
    - The client enforces `maxZoom` in Leaflet `fitBounds`, guaranteeing
      single-location and city albums never over-zoom to street level regardless of screen size.

    Args:
        pool: List or dictionary of `AssetAnswer` objects representing candidate photos in the match.
        max_span_km: Maximum diagonal distance threshold in kilometers. Defaults to 5000 km.

    Returns:
        A `MapBounds` object containing min/max latitude and longitude, or `None` if no valid
        coordinates exist or if the pool span exceeds global threshold limits.

    """
    answers = pool.values() if isinstance(pool, dict) else pool
    coords = [
        (ans.latitude, ans.longitude)
        for ans in answers
        if ans.latitude is not None
        and ans.longitude is not None
        and not (abs(ans.latitude) < 1e-6 and abs(ans.longitude) < 1e-6)
    ]
    if not coords:
        return None

    lats = [c[0] for c in coords]
    lngs = [c[1] for c in coords]

    min_lat = min(lats)
    max_lat = max(lats)
    min_lng = min(lngs)
    max_lng = max(lngs)

    lat_span = max_lat - min_lat
    lng_span = max_lng - min_lng

    # Global check: if span is excessively wide (> 60 deg lat or > 90 deg lng),
    # or distance between corners exceeds max_span_km, fallback to world view.
    if lat_span > 60.0 or lng_span > 90.0 or haversine_km(min_lat, min_lng, max_lat, max_lng) > max_span_km:
        return None

    return MapBounds(
        min_lat=round(min_lat, 6),
        max_lat=round(max_lat, 6),
        min_lng=round(min_lng, 6),
        max_lng=round(max_lng, 6),
    )


def load_asset_pool(
    state: MatchState,
    metadata_store: MetadataStore,
    settings: Any | None = None,
) -> None:
    """Populate the per-match candidate pool once with active filter criteria.

    Queries the fast indexed local SQLite metadata store. Clamps match setup dates against
    global configuration date boundaries. Mutates `state.asset_pool` in place and computes
    adaptive scoring decay parameters for the match session.

    Args:
        state: Active match state containing setup filters and pool storage.
        metadata_store: Local SQLite metadata store for fast indexed querying.
        settings: Optional application settings for global whitelist/blacklist enforcement.

    """
    criteria = AssetFilterCriteria.from_setup(state.setup, settings)
    state.asset_pool = metadata_store.fetch_candidate_assets(criteria, limit=250)
    state.location_decay_km = calculate_location_decay(state.asset_pool)
    state.date_decay_days = calculate_date_decay(state.asset_pool)
    logger.info(
        'Match %s candidate pool loaded: %d assets -> location_decay=%.1f km, date_decay=%.1f days',
        state.match_id,
        len(state.asset_pool),
        state.location_decay_km,
        state.date_decay_days,
    )


def is_asset_valid_for_batch(
    candidate_ans: AssetAnswer,
    selected_answers: list[AssetAnswer] | list[RoundAsset] | list[AssetAnswer | RoundAsset],
    location_mode: bool,
    date_mode: bool,
    min_dist_km: float = DEFAULT_PHOTO_DIVERSITY_MIN_DISTANCE_KM,
    min_time_sec: float = DEFAULT_PHOTO_DIVERSITY_MIN_TIME_SECONDS,
) -> bool:
    """Determine if a candidate photo satisfies diversity separation against selected match photos.

    Enforces:
    - Non-zero valid coordinates when `location_mode` is active.
    - Haversine distance separation >= `min_dist_km` from all selected photos when `location_mode` is active.
    - Time separation >= `min_time_sec` from all selected photos when `date_mode` is active.

    Args:
        candidate_ans: The candidate photo's metadata and ground truth answers.
        selected_answers: List of previously selected or played photos to test against.
        location_mode: Whether geographic distance separation should be checked.
        date_mode: Whether capture time separation should be checked.
        min_dist_km: Minimum distance threshold in kilometers. Defaults to 0.1 km (100m).
        min_time_sec: Minimum temporal threshold in seconds. Defaults to 60.0 seconds.

    Returns:
        `True` if the candidate meets all active diversity constraints, `False` otherwise.

    """
    if location_mode:
        if candidate_ans.latitude is None or candidate_ans.longitude is None:
            return False
        if abs(candidate_ans.latitude) < 1e-6 and abs(candidate_ans.longitude) < 1e-6:
            return False

    for sel in selected_answers:
        sel_ans = sel.answer if isinstance(sel, RoundAsset) else sel
        if location_mode and (
            candidate_ans.latitude is not None
            and candidate_ans.longitude is not None
            and sel_ans.latitude is not None
            and sel_ans.longitude is not None
        ):
            dist = haversine_km(
                candidate_ans.latitude,
                candidate_ans.longitude,
                sel_ans.latitude,
                sel_ans.longitude,
            )
            if dist < min_dist_km:
                return False

        if date_mode and candidate_ans.capture_datetime is not None and sel_ans.capture_datetime is not None:
            diff_sec = abs((candidate_ans.capture_datetime - sel_ans.capture_datetime).total_seconds())
            if diff_sec < min_time_sec:
                return False

    return True


def filter_diverse_asset_answers(
    eligible_answers: list[AssetAnswer],
    location_mode: bool,
    date_mode: bool,
    min_dist_km: float = DEFAULT_PHOTO_DIVERSITY_MIN_DISTANCE_KM,
    min_time_sec: float = DEFAULT_PHOTO_DIVERSITY_MIN_TIME_SECONDS,
) -> list[AssetAnswer]:
    """Greedily build a diverse subset of asset answers satisfying minimum distance and time constraints.

    Iterates through candidates in order and appends any candidate that satisfies diversity constraints
    relative to all previously accepted candidates.

    Args:
        eligible_answers: Candidate list of `AssetAnswer` instances.
        location_mode: Whether geographic distance separation should be evaluated.
        date_mode: Whether capture time separation should be evaluated.
        min_dist_km: Minimum distance separation in kilometers. Defaults to 0.1 km.
        min_time_sec: Minimum time separation in seconds. Defaults to 60.0 seconds.

    Returns:
        A list of `AssetAnswer` instances that are mutually diverse.

    """
    diverse: list[AssetAnswer] = []
    for ans in eligible_answers:
        if is_asset_valid_for_batch(
            ans,
            diverse,
            location_mode,
            date_mode,
            min_dist_km=min_dist_km,
            min_time_sec=min_time_sec,
        ):
            diverse.append(ans)
    return diverse


def generate_batch_pins(
    assets: list[RoundAsset],
    location_mode: bool,
) -> list[dict[str, object]]:
    """Generate randomized lettered map markers ('A', 'B', ...) for batch assets.

    When `location_mode` is enabled, filters out assets without valid coordinates (or placed at (0, 0)),
    shuffles the true coordinate locations to prevent order-correlation hints, and assigns sequential
    letters ('A', 'B', ... 'Z', 'A1', ...).

    Args:
        assets: List of `RoundAsset` instances chosen for the batch.
        location_mode: Whether location mode is enabled for the match.

    Returns:
        List of dictionaries containing `pin_id`, `true_asset_id`, `latitude`, and `longitude`.
        Returns an empty list if `location_mode` is disabled.

    """
    if not location_mode:
        return []

    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    raw_pins = []
    for ra in assets:
        if ra.answer.latitude is None or ra.answer.longitude is None:
            continue
        if abs(ra.answer.latitude) < 1e-6 and abs(ra.answer.longitude) < 1e-6:
            continue
        raw_pins.append(
            {
                'true_asset_id': ra.asset_id,
                'latitude': ra.answer.latitude,
                'longitude': ra.answer.longitude,
            }
        )

    random.shuffle(raw_pins)
    pins_data: list[dict[str, object]] = []
    for idx, p in enumerate(raw_pins):
        letter = letters[idx % len(letters)]
        if idx >= len(letters):
            letter = f'{letter}{idx // len(letters)}'
        pins_data.append(
            {
                'pin_id': letter,
                'true_asset_id': p['true_asset_id'],
                'latitude': p['latitude'],
                'longitude': p['longitude'],
            }
        )

    return pins_data


async def _select_diverse_assets(
    state: MatchState,
    immich: ImmichClient,
    count: int,
    client_excluded: set[str],
    min_capture_date: date | None = None,
    max_capture_date: date | None = None,
    min_dist_km: float = DEFAULT_PHOTO_DIVERSITY_MIN_DISTANCE_KM,
    min_time_sec: float = DEFAULT_PHOTO_DIVERSITY_MIN_TIME_SECONDS,
    metadata_store: MetadataStore | None = None,
    settings: Any | None = None,
) -> list[RoundAsset] | None:
    """Core candidate selection routine: draws up to `count` unplayed, diverse assets with fallback.

    Selection Workflow:
    1. Filters out previously played match asset IDs and client-excluded IDs.
    2. If candidates < `count`, attempts to reload the match pool (via metadata store or Immich).
    3. **Primary pass**: Shuffles candidate IDs and greedily picks up to `count` assets that satisfy
       both distance and time diversity constraints relative to previously played match assets
       and any assets already selected in the current round/batch.
    4. **Fallback pass**: If diversity constraints cannot fill all `count` slots (e.g. tightly clustered
       album photos or small pools), fills remaining slots with distinct unplayed candidates.

    Args:
        state: Active match state.
        immich: Immich API client for pool fetching fallback.
        count: Number of assets required for the round or batch.
        client_excluded: Set of asset IDs excluded by the client.
        min_capture_date: Minimum capture date boundary.
        max_capture_date: Maximum capture date boundary.
        min_dist_km: Minimum distance threshold in kilometers. Defaults to 0.1 km.
        min_time_sec: Minimum temporal threshold in seconds. Defaults to 60.0 seconds.
        metadata_store: Optional local SQLite metadata store.
        settings: Optional application settings for global whitelist/blacklist enforcement.

    Returns:
        List of `RoundAsset` instances of length `count`, or `None` if fewer than `count`
        unplayed candidates are available.

    """
    excluded = state.played_asset_ids | client_excluded

    if not state.asset_pool and metadata_store is not None:
        load_asset_pool(
            state,
            metadata_store,
            settings=settings,
        )
    candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if len(candidates) < count and metadata_store is not None:
        load_asset_pool(
            state,
            metadata_store,
            settings=settings,
        )
        candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if len(candidates) < count:
        return None

    shuffled_candidates = list(candidates)
    random.shuffle(shuffled_candidates)

    selected_ids: list[str] = []
    selected_assets: list[RoundAsset] = []
    played_assets = [
        RoundAsset(asset_id=aid, answer=state.asset_pool[aid])
        for aid in state.played_asset_ids
        if aid in state.asset_pool
    ]

    # Primary pass: Greedily pick diverse assets (location distance >= min_dist_km, time separation >= min_time_sec)
    for aid in shuffled_candidates:
        ans = state.asset_pool[aid]
        if is_asset_valid_for_batch(
            ans,
            played_assets + selected_assets,
            state.setup.location_mode,
            state.setup.date_mode,
            min_dist_km=min_dist_km,
            min_time_sec=min_time_sec,
        ):
            selected_ids.append(aid)
            selected_assets.append(RoundAsset(asset_id=aid, answer=ans))
            if len(selected_assets) == count:
                break

    # Fallback pass: If diversity requirements couldn't fill all `count` slots,
    # fill with remaining distinct unplayed candidates
    if len(selected_assets) < count:
        for aid in shuffled_candidates:
            if aid not in selected_ids:
                selected_ids.append(aid)
                selected_assets.append(RoundAsset(asset_id=aid, answer=state.asset_pool[aid]))
                if len(selected_assets) == count:
                    break

    if len(selected_assets) < count:
        return None

    return selected_assets


async def select_round_asset(
    state: MatchState,
    immich: ImmichClient,
    client_excluded: set[str],
    min_capture_date: date | None = None,
    max_capture_date: date | None = None,
    min_dist_km: float = DEFAULT_PHOTO_DIVERSITY_MIN_DISTANCE_KM,
    min_time_sec: float = DEFAULT_PHOTO_DIVERSITY_MIN_TIME_SECONDS,
    metadata_store: MetadataStore | None = None,
    settings: Any | None = None,
) -> RoundAsset | None:
    """Draw an unplayed asset, prioritizing diverse assets but falling back to any unplayed candidate.

    Delegates to `_select_diverse_assets` with `count=1`.

    Args:
        state: Active match state.
        immich: Immich client for pool reloading if required.
        client_excluded: Set of asset IDs reported as played or excluded by the client.
        min_capture_date: Minimum capture date boundary.
        max_capture_date: Maximum capture date boundary.
        min_dist_km: Minimum distance separation in km. Defaults to 0.1 km.
        min_time_sec: Minimum time separation in seconds. Defaults to 60.0 seconds.
        metadata_store: Optional local SQLite metadata store.
        settings: Optional application settings.

    Returns:
        A `RoundAsset` containing the selected asset ID and answer metadata, or `None` if no
        unplayed assets are available.

    """
    assets = await _select_diverse_assets(
        state,
        immich,
        count=1,
        client_excluded=client_excluded,
        min_capture_date=min_capture_date,
        max_capture_date=max_capture_date,
        min_dist_km=min_dist_km,
        min_time_sec=min_time_sec,
        metadata_store=metadata_store,
        settings=settings,
    )
    return assets[0] if assets else None


async def select_batch_round_assets(
    state: MatchState,
    immich: ImmichClient,
    count: int,
    client_excluded: set[str],
    min_capture_date: date | None = None,
    max_capture_date: date | None = None,
    min_dist_km: float = DEFAULT_PHOTO_DIVERSITY_MIN_DISTANCE_KM,
    min_time_sec: float = DEFAULT_PHOTO_DIVERSITY_MIN_TIME_SECONDS,
    metadata_store: MetadataStore | None = None,
    settings: Any | None = None,
) -> tuple[list[RoundAsset], list[dict[str, object]]] | None:
    """Select a batch of diverse round assets and generate randomized map pins.

    Designed for multi-photo batch game modes (e.g. Album Shuffle).
    Ensures selected assets are diverse both relative to previously played rounds and among each other
    within the batch.

    Args:
        state: Active match state.
        immich: Immich API client for pool fetching fallback.
        count: Number of assets required for the batch.
        client_excluded: Set of asset IDs excluded by the client.
        min_capture_date: Minimum capture date boundary.
        max_capture_date: Maximum capture date boundary.
        min_dist_km: Minimum distance threshold in kilometers. Defaults to 0.1 km.
        min_time_sec: Minimum temporal threshold in seconds. Defaults to 60.0 seconds.
        metadata_store: Optional local SQLite metadata store.
        settings: Optional application settings.

    Returns:
        A tuple of `(selected_assets, pins_data)` where `selected_assets` is a list of `RoundAsset`
        instances and `pins_data` is a list of dictionary representations of map pins.
        Returns `None` if fewer than `count` candidates are available.

    """
    assets = await _select_diverse_assets(
        state,
        immich,
        count=count,
        client_excluded=client_excluded,
        min_capture_date=min_capture_date,
        max_capture_date=max_capture_date,
        min_dist_km=min_dist_km,
        min_time_sec=min_time_sec,
        metadata_store=metadata_store,
        settings=settings,
    )
    if not assets:
        return None

    pins_data = generate_batch_pins(assets, location_mode=state.setup.location_mode)
    return assets, pins_data
