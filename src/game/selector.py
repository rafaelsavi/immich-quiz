from __future__ import annotations

import random
from datetime import date

from src.immich.client import AssetAnswer, ImmichClient
from src.scoring import haversine_km
from src.storage.session import MatchState, RoundAsset


async def load_asset_pool(
    state: MatchState,
    immich: ImmichClient,
    min_capture_date: date | None,
    max_capture_date: date | None,
) -> None:
    """Populate the per-match candidate pool once instead of searching every round."""
    raw_assets = await immich.search_random_assets(state.setup.library_name, state.setup.album_id)
    pool: dict[str, AssetAnswer] = {}
    for asset in raw_assets:
        if not ImmichClient.is_eligible_asset(
            asset,
            state.setup.location_mode,
            state.setup.date_mode,
            min_capture_date,
            max_capture_date,
        ):
            continue
        asset_id = str(asset.get('id', '')).strip()
        if asset_id:
            pool[asset_id] = ImmichClient.extract_answer(asset)
    state.asset_pool = pool


def is_asset_valid_for_batch(
    candidate_ans: AssetAnswer,
    selected_assets: list[RoundAsset],
    location_mode: bool,
    date_mode: bool,
    min_dist_km: float = 0.1,
    min_time_sec: float = 60.0,
) -> bool:
    """
    Determine if a photo selection is valid.

    A photo selection is valid if:
    - All photos have valid coordinates when location_mode is active
    - All photos are located more than min_dist_km away from each other when location_mode is active
    - All photos are captured more than min_time_sec apart from each other when date_mode is active
    """
    if location_mode:
        if candidate_ans.latitude is None or candidate_ans.longitude is None:
            return False
        if abs(candidate_ans.latitude) < 1e-6 and abs(candidate_ans.longitude) < 1e-6:
            return False

    for sel in selected_assets:
        sel_ans = sel.answer
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


async def select_round_asset(
    state: MatchState,
    immich: ImmichClient,
    client_excluded: set[str],
    min_capture_date: date | None,
    max_capture_date: date | None,
) -> RoundAsset | None:
    """Draw an unplayed asset, refreshing the pool once if it is exhausted."""
    excluded = state.played_asset_ids | client_excluded

    if not state.asset_pool:
        await load_asset_pool(state, immich, min_capture_date, max_capture_date)
    candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if not candidates:
        await load_asset_pool(state, immich, min_capture_date, max_capture_date)
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

    # Prefer an asset that is >= 100m away and >= 60s apart from previously played match assets
    for aid in shuffled:
        ans = state.asset_pool[aid]
        if is_asset_valid_for_batch(ans, played_assets, state.setup.location_mode, state.setup.date_mode):
            return RoundAsset(asset_id=aid, answer=ans)

    # Fallback if pool is constrained: pick any unplayed candidate
    asset_id = random.choice(candidates)
    return RoundAsset(asset_id=asset_id, answer=state.asset_pool[asset_id])


async def select_batch_round_assets(
    state: MatchState,
    immich: ImmichClient,
    count: int,
    client_excluded: set[str],
    min_capture_date: date | None,
    max_capture_date: date | None,
) -> tuple[list[RoundAsset], list[dict[str, object]]] | None:
    excluded = state.played_asset_ids | client_excluded

    if not state.asset_pool:
        await load_asset_pool(state, immich, min_capture_date, max_capture_date)
    candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if len(candidates) < count:
        await load_asset_pool(state, immich, min_capture_date, max_capture_date)
        candidates = [asset_id for asset_id in state.asset_pool if asset_id not in excluded]

    if not candidates:
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

    # First pass: enforce location distance >= 0.1 km and capture date separation >= 60 seconds
    for aid in shuffled_candidates:
        ans = state.asset_pool[aid]
        if is_asset_valid_for_batch(
            ans, played_assets + selected_assets, state.setup.location_mode, state.setup.date_mode
        ):
            selected_ids.append(aid)
            selected_assets.append(RoundAsset(asset_id=aid, answer=ans))
            if len(selected_assets) == count:
                break

    # Fallback pass: if pool is constrained, fill remaining slots from available candidates
    if len(selected_assets) < count:
        for aid in shuffled_candidates:
            if aid not in selected_ids:
                ans = state.asset_pool[aid]
                if state.setup.location_mode:
                    if ans.latitude is None or ans.longitude is None:
                        continue
                    if abs(ans.latitude) < 1e-6 and abs(ans.longitude) < 1e-6:
                        continue
                selected_ids.append(aid)
                selected_assets.append(RoundAsset(asset_id=aid, answer=ans))
                if len(selected_assets) == count:
                    break

    if not selected_assets:
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
