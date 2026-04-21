# 🧠 Backend – Movie Recommendation System

## 📌 Overview

The backend is built using **FastAPI** and follows a layered architecture with background workers.

It is responsible for:

* Handling API requests
* Managing user interactions (likes, ratings, onboarding)
* Serving personalized recommendations
* Running background jobs (data enrichment, simulation)
* Managing ML artifacts (ALS, CBF, HNSW)
* Integrating with external APIs (TMDB)
* Interacting with PostgreSQL (Supabase)

---

## 🏗️ Architecture

```text
API Layer → Service Layer → ML / DB Layer → Storage Layer
                          ↓
                    Background Workers (Celery)
```

---

## 📁 Project Structure

```text
app/
  api/            # FastAPI endpoints
  core/           # authentication & security (JWT)
  db/             # database config and models
  ml/
    recommenders/ # ALS, CBF, hybrid logic
    scripts/      # training & artifact pipeline
    storage/      # Cloudflare R2 integration
    artifacts/    # loaded models
  schemas/        # request/response validation
  services/       # business logic layer
  workers/        # background jobs (Celery)
```

---

## 🔌 API Layer (`api/`)

Handles HTTP requests.

Key endpoints:

* `recommendations.py` → main recommendation endpoint
* `movies.py` → movie retrieval
* `likes.py` / `ratings.py` → interactions
* `onboarding.py` → cold start handling
* `users.py` → authentication

---

## ⚙️ Service Layer (`services/`)

This is the **core of the backend logic**.

Important services:

* `recommend_service.py` → main recommendation pipeline
* `movie_service.py` → movie retrieval
* `like_service.py` → like handling
* `rating_service.py` → rating handling
* `onboarding_service.py` → onboarding logic
* `event_service.py` → interaction tracking
* `metadata_service.py` → movie metadata
* `als_store.py` → ALS factor access
* `vector_index.py` → HNSW similarity search
* `r2_restore_service.py` → restore models from R2
* `startup.py` → application startup logic
* `smoke_checks.py` → health checks
* `tmdb_client.py` → external movie data integration

---

## 🧠 Machine Learning Layer (`ml/`)

### Recommenders (`ml/recommenders/`)

* `als_recommender.py` → collaborative filtering
* `cbf_recommender.py` → content-based filtering
* `hybrid_recommender.py` → hybrid logic

---

### Scripts (`ml/scripts/`)

Handles ML pipeline:

* `train_als.py` → train ALS model
* `build_hnsw_artifacts.py` → build vector index
* `eval_all_models.py` → evaluation (HitRate, NDCG)
* `run_pipeline.py` → full pipeline
* `publish_run_to_r2.py` → upload models
* `restore_run_from_r2.py` → restore models
* `rollback_production_run.py` → rollback
* `run_worker_once.py` → manual worker execution

---

### Storage (`ml/storage/`)

* `r2_client.py` → R2 connection
* `r2_artifacts.py` → artifact handling

---

## 📦 ML Artifacts (`ml/artifacts/`)

Stores active models:

* ALS factors
* TF-IDF + SVD
* HNSW index

Artifacts are:

* downloaded at startup
* refreshed every 5 minutes

---

## 🔄 Background Workers (`workers/`)

Handles asynchronous tasks:

* `tmdb_backfill_worker.py` → enrich movie data
* `tmdb_search_worker.py` → search enrichment
* `simulate_data.py` → generate synthetic interactions

👉 Prevents blocking API requests

---

## 🔄 Recommendation Flow

```text
User Request
   ↓
API Endpoint (/recommendations)
   ↓
Service Layer (recommend_service)
   ↓
Hybrid Recommender
   ↓
ALS + CBF Candidates
   ↓
Vector similarity (HNSW)
   ↓
Score normalization & combination
   ↓
Filter interacted items
   ↓
Return response
```

---

## 🗄️ Database Layer (`db/`)

* `database.py` → connection setup
* `models.py` → ORM models

Stores:

* users
* likes
* ratings
* interaction events

---

## 🔐 Authentication (`core/`)

* JWT authentication
* password hashing (argon2)
* token validation

---

## ☁️ Artifact Pipeline

1. Train models offline
2. Upload to Cloudflare R2
3. Promote run to production
4. Backend restores artifacts
5. Background refresh updates models

---

## 🚀 Running Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## 🔐 Environment Variables

* `DATABASE_URL`
* `SECRET_KEY`
* `ACCESS_TOKEN_EXPIRE_MINUTES`
* `R2_ACCESS_KEY`
* `R2_SECRET_KEY`

---

## 🧠 Notes

* Models are trained **offline**
* Recommendations are computed **at request time**
* Hybrid approach improves accuracy
* Background workers handle asynchronous tasks
