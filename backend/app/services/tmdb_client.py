# app/services/tmdb_client.py
import os
import time
import requests

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = os.getenv("TMDB_BASE_URL", "https://api.themoviedb.org/3")

TIMEOUT_SECONDS = int(os.getenv("TMDB_TIMEOUT_SECONDS", "10"))
SLEEP_ON_429_SECONDS = int(os.getenv("TMDB_429_SLEEP_SECONDS", "60"))

if not TMDB_API_KEY:
    # Don't raise at import time if you sometimes run without TMDb.
    # Worker will fail fast, API can still run cached-only.
    TMDB_API_KEY = None


class TmdbClient:
    def _get(self, path: str, params: dict) -> tuple[int, dict | None]:
        """Return (status_code, json_or_none). Handles 429 with one retry."""
        if not TMDB_API_KEY:
            return 0, None

        url = f"{TMDB_BASE_URL}{path}"
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
            if r.status_code == 429:
                time.sleep(SLEEP_ON_429_SECONDS)
                r = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)

            if r.status_code != 200:
                return r.status_code, None
            return 200, r.json()
        except Exception:
            return 0, None

    def search_movie(self, title: str, year: int | None = None) -> tuple[int, list[dict]]:
        params = {"api_key": TMDB_API_KEY, "query": title, "language": "en-US"}
        if year:
            params["year"] = year
        code, data = self._get("/search/movie", params=params)
        if not data:
            return code, []
        return code, data.get("results", []) or []

    def movie_details(self, tmdb_id: int) -> tuple[int, dict | None]:
        params = {"api_key": TMDB_API_KEY, "language": "en-US"}
        return self._get(f"/movie/{tmdb_id}", params=params)


tmdb_client = TmdbClient()
