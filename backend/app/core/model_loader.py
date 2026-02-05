# backend/app/core/model_loader.py

from app.db.database import engine
import pandas as pd
from app.services.cbf_model import DynamicCBF
from app.services.cf_model import DynamicCF
from app.services.hybrid_model import DynamicHybridRecommender

class ModelLoader:
    def __init__(self):
        # Movies rarely change → safe to load once
        self.movies = pd.read_sql("SELECT movie_id, title, genres FROM movies", engine)
        self.cbf = DynamicCBF(self.movies)
        self.build_hybrid()  # optional, build at init

    def build_hybrid(self):
        ratings = pd.read_sql("SELECT user_id, movie_id, rating FROM ratings", engine)
        self.cf = DynamicCF(ratings)
        self.hybrid = DynamicHybridRecommender(self.cbf, self.cf)
        return self.hybrid

    def refresh_cf_model(self):
        """Rebuild CF with latest ratings so hybrid sees new user ratings"""
        ratings = pd.read_sql("SELECT user_id, movie_id, rating FROM ratings", engine)
        self.cf = DynamicCF(ratings)
        if hasattr(self, "hybrid"):
            self.hybrid.cf = self.cf
