# This file is optional and  performing the role of  API connector  that :
# -talks  directly  to  TMDB servers 
# -sends HTTP  requests 
# -returns raw json Data

# app/services/tmdb_client.py
import os
import requests

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = os.getenv("TMDB_BASE_URL", "https://api.themoviedb.org/3")

class TmdbClient:
    def search_movie(self, title: str, year: int | None = None):
        params = {"api_key": TMDB_API_KEY, "query": title}
        if year:
            params["year"] = year
        r = requests.get(f"{TMDB_BASE_URL}/search/movie", params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("results", [])

    def movie_details(self, tmdb_id: int):
        params = {"api_key": TMDB_API_KEY}
        r = requests.get(f"{TMDB_BASE_URL}/movie/{tmdb_id}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()

tmdb_client = TmdbClient()
