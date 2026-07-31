from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from src.models import LeaderboardEntry
from src.scoring import max_possible_score

CSV_HEADER = [
    'match_id',
    'played_at',
    'player_name',
    'rounds',
    'round_length',
    'location_mode',
    'date_mode',
    'library',
    'album',
    'max_possible_score',
    'total_score',
]


class LeaderboardStore:
    def __init__(self, csv_path: Path, *, score_max_points: int = 100) -> None:
        self._csv_path = csv_path
        self._score_max_points = score_max_points
        self._ensure_file()

    def append_match(
        self,
        match_id: str,
        library_name: str,
        album_name: str,
        rounds_played: int,
        round_length: str,
        location_mode: bool,
        date_mode: bool,
        player_scores: dict[str, dict[str, int]],
    ) -> None:
        played_at = datetime.now(timezone.utc).isoformat()

        with self._csv_path.open('a', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
            for player, scores in player_scores.items():
                total = scores.get('total', 0)
                max_score = max_possible_score(
                    rounds_played,
                    location_mode,
                    date_mode,
                    per_goal_max_points=self._score_max_points,
                )

                row = {
                    'match_id': match_id,
                    'played_at': played_at,
                    'player_name': player,
                    'rounds': rounds_played,
                    'round_length': round_length,
                    'location_mode': location_mode,
                    'date_mode': date_mode,
                    'library': library_name,
                    'album': album_name,
                    'max_possible_score': max_score,
                    'total_score': total,
                }
                writer.writerow(row)

    def list_entries(
        self,
        *,
        rounds: int | None = None,
        round_length: str | None = None,
        location_mode: bool | None = None,
        date_mode: bool | None = None,
        library: str | None = None,
        album: str | None = None,
    ) -> list[LeaderboardEntry]:
        entries: list[LeaderboardEntry] = []
        with self._csv_path.open('r', newline='', encoding='utf-8') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue

                # Parse flat config columns — booleans are stored as 'True'/'False'
                row_rounds = int(row['rounds'])
                row_round_length = row['round_length']
                row_location_mode = row['location_mode'].lower() == 'true'
                row_date_mode = row['date_mode'].lower() == 'true'
                row_library = row['library']
                row_album = row['album']

                # Apply filters — skip rows that don't match
                if rounds is not None and row_rounds != rounds:
                    continue
                if round_length is not None and row_round_length != round_length:
                    continue
                if location_mode is not None and row_location_mode != location_mode:
                    continue
                if date_mode is not None and row_date_mode != date_mode:
                    continue
                if library is not None and row_library != library:
                    continue
                if album is not None and row_album != album:
                    continue

                config = {
                    'rounds': row_rounds,
                    'round_length': row_round_length,
                    'location_mode': row_location_mode,
                    'date_mode': row_date_mode,
                    'library': row_library,
                    'album': row_album,
                }

                entries.append(
                    LeaderboardEntry(
                        match_id=row['match_id'],
                        played_at=datetime.fromisoformat(row['played_at']),
                        player_name=row['player_name'],
                        max_possible_score=int(row['max_possible_score']),
                        total_score=int(row['total_score']),
                        config=config,
                    )
                )
        entries.sort(key=lambda x: x.played_at, reverse=True)
        return entries

    def _ensure_file(self) -> None:
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        if self._csv_path.exists():
            return
        with self._csv_path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow(CSV_HEADER)
