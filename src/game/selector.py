import random
from datetime import date

from src.immich.client import AssetAnswer, ImmichClient, SearchQuery
from src.models import MapBounds
from src.scoring import haversine_km
from src.storage.metadata import AssetFilterCriteria, MetadataStore
from src.storage.session import MatchState, RoundAsset

# Hardcoded Smart Map Zoom internal safeguards
SMART_MAP_ZOOM_MAX_SPAN_KM: float = 5000.0

# Internal Photo Diversity sampling parameters (soft prioritization thresholds)
DEFAULT_PHOTO_DIVERSITY_MIN_DISTANCE_KM: float = 0.1
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


async def load_asset_pool(
    state: MatchState,
    immich: ImmichClient,
    min_capture_date: date | None,
    max_capture_date: date | None,
    include_shared_albums: bool = False,
    include_partner_assets: bool = False,
    metadata_store: MetadataStore | None = None,
) -> None:
    """Populate the per-match candidate pool once with active filter criteria."""
    effective_min_date = max(filter(None, [min_capture_date, state.setup.min_date]), default=None)
    effective_max_date = min(filter(None, [max_capture_date, state.setup.max_date]), default=None)

    # Use fast indexed SQLite metadata store when available
    if metadata_store is not None and metadata_store.has_synced_assets(state.setup.library_name):
        criteria = AssetFilterCriteria(
            library_name=state.setup.library_name,
            location_mode=state.setup.location_mode,
            date_mode=state.setup.date_mode,
            min_date=effective_min_date,
            max_date=effective_max_date,
            countries=tuple(state.setup.countries),
            cities=tuple(state.setup.cities),
            person_ids=tuple(state.setup.person_ids),
            people_mode=state.setup.people_mode,
            album_ids=tuple(state.setup.album_ids),
            include_shared_albums=include_shared_albums,
            include_partner_assets=include_partner_assets,
        )
        state.asset_pool = metadata_store.fetch_candidate_assets(criteria, limit=250)
        return

    # Fallback to Immich API on cold start or when metadata store has no indexed assets
    query = SearchQuery(
        album_ids=tuple(state.setup.album_ids),
        person_ids=tuple(state.setup.person_ids),
        people_mode=state.setup.people_mode,
        countries=tuple(state.setup.countries),
        cities=tuple(state.setup.cities),
        include_shared_albums=include_shared_albums,
        include_partner_assets=include_partner_assets,
        min_date=effective_min_date,
        max_date=effective_max_date,
    )

    raw_assets = await immich.search_random_assets(
        state.setup.library_name,
        query=query,
    )
    pool: dict[str, AssetAnswer] = {}
    for asset in raw_assets:
        if not ImmichClient.is_eligible_asset(
            asset,
            state.setup.location_mode,
            state.setup.date_mode,
            min_date=effective_min_date,
            max_date=effective_max_date,
            countries=tuple(state.setup.countries),
            cities=tuple(state.setup.cities),
        ):
            continue
        asset_id = str(asset.get('id', '')).strip()
        if asset_id:
            pool[asset_id] = ImmichClient.extract_answer(asset)
    state.asset_pool = pool


def is_asset_valid_for_batch(
    candidate_ans: AssetAnswer,
    selected_answers: list[AssetAnswer] | list[RoundAsset] | list[AssetAnswer | RoundAsset],
    location_mode: bool,
    date_mode: bool,
    min_dist_km: float = DEFAULT_PHOTO_DIVERSITY_MIN_DISTANCE_KM,
    min_time_sec: float = DEFAULT_PHOTO_DIVERSITY_MIN_TIME_SECONDS,
) -> bool:
    """
    Determine if a candidate photo satisfies diversity separation against selected match photos.

    Enforces:
    - Non-zero valid coordinates when location_mode is active.
    - Distance separation >= min_dist_km from all selected photos when location_mode is active.
    - Time separation >= min_time_sec from all selected photos when date_mode is active.
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
    """Greedily build a diverse subset of asset answers satisfying minimum distance and time constraints."""
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


async def select_round_asset(
    state: MatchState,
    immich: ImmichClient,
    client_excluded: set[str],
    min_capture_date: date | None,
    max_capture_date: date | None,
    include_shared_albums: bool = False,
    include_partner_assets: bool = False,
    min_dist_km: float = DEFAULT_PHOTO_DIVERSITY_MIN_DISTANCE_KM,
    min_time_sec: float = DEFAULT_PHOTO_DIVERSITY_MIN_TIME_SECONDS,
    metadata_store: MetadataStore | None = None,
) -> RoundAsset | None:
    """Draw an unplayed asset, prioritizing diverse assets but falling back to any unplayed candidate."""
    excluded = state.played_asset_ids | client_excluded

    if not state.asset_pool:
        await load_asset_pool(
            state,
            immich,
            min_capture_date,
            max_capture_date,
            include_shared_albums=include_shared_albums,
            include_partner_assets=include_partner_assets,
            metadata_store=metadata_store,
        )
    candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if not candidates:
        await load_asset_pool(
            state,
            immich,
            min_capture_date,
            max_capture_date,
            include_shared_albums=include_shared_albums,
            include_partner_assets=include_partner_assets,
            metadata_store=metadata_store,
        )
        candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if not candidates:
        return None

    shuffled = list(candidates)
    random.shuffle(shuffled)

    played_assets = [
        RoundAsset(asset_id=aid, answer=state.asset_pool[aid])
        for aid in state.played_asset_ids
        if aid in state.asset_pool
    ]

    # Primary pass: Select an asset that satisfies distance and time diversity against previously played match assets
    for aid in shuffled:
        ans = state.asset_pool[aid]
        if is_asset_valid_for_batch(
            ans,
            played_assets,
            state.setup.location_mode,
            state.setup.date_mode,
            min_dist_km=min_dist_km,
            min_time_sec=min_time_sec,
        ):
            return RoundAsset(asset_id=aid, answer=ans)

    # Fallback pass: When pool is clustered or limited, downsample to any available unplayed candidate
    fallback_id = shuffled[0]
    return RoundAsset(asset_id=fallback_id, answer=state.asset_pool[fallback_id])


async def select_batch_round_assets(
    state: MatchState,
    immich: ImmichClient,
    count: int,
    client_excluded: set[str],
    min_capture_date: date | None,
    max_capture_date: date | None,
    include_shared_albums: bool = False,
    include_partner_assets: bool = False,
    min_dist_km: float = DEFAULT_PHOTO_DIVERSITY_MIN_DISTANCE_KM,
    min_time_sec: float = DEFAULT_PHOTO_DIVERSITY_MIN_TIME_SECONDS,
    metadata_store: MetadataStore | None = None,
) -> tuple[list[RoundAsset], list[dict[str, object]]] | None:
    excluded = state.played_asset_ids | client_excluded

    if not state.asset_pool:
        await load_asset_pool(
            state,
            immich,
            min_capture_date,
            max_capture_date,
            include_shared_albums=include_shared_albums,
            include_partner_assets=include_partner_assets,
            metadata_store=metadata_store,
        )
    candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if len(candidates) < count:
        await load_asset_pool(
            state,
            immich,
            min_capture_date,
            max_capture_date,
            include_shared_albums=include_shared_albums,
            include_partner_assets=include_partner_assets,
            metadata_store=metadata_store,
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

    # Fallback pass: If diversity requirements couldn't fill all `count` slots, fill with remaining distinct unplayed candidates
    if len(selected_assets) < count:
        for aid in shuffled_candidates:
            if aid not in selected_ids:
                selected_ids.append(aid)
                selected_assets.append(RoundAsset(asset_id=aid, answer=state.asset_pool[aid]))
                if len(selected_assets) == count:
                    break

    if len(selected_assets) < count:
        return None

    assets = selected_assets

    pins_data: list[dict[str, object]] = []
    if state.setup.location_mode:
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

    return assets, pins_data
