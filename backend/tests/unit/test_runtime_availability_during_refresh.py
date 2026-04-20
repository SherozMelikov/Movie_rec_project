import threading
import time
import numpy as np

from app.services.als_store import ALSStore
from app.services.vector_index import VectorIndex


def test_runtime_remains_available_during_refresh(monkeypatch):
    als = ALSStore()
    vec = VectorIndex()

    # Fake loaded state using realistic numpy arrays
    als.user_factors = np.array([[0.1, 0.2]], dtype=np.float32)
    als.item_factors = np.array([[0.2, 0.3]], dtype=np.float32)
    als.user_id_to_idx = {1: 0}
    als.movie_id_to_idx = {101: 0}

    vec.movie_ids = np.array([101], dtype=np.int32)
    vec.vectors = np.array([[0.1, 0.2]], dtype=np.float32)
    vec.id_to_pos = {101: 0}
    vec.index = object()  # fake loaded marker only

    # Simulate refresh (reload)
    def fake_reload():
        time.sleep(0.1)
        with als._lock:
            als.user_factors = np.array([[0.5, 0.6]], dtype=np.float32)
            als.item_factors = np.array([[0.6, 0.7]], dtype=np.float32)
        with vec._lock:
            vec.vectors = np.array([[0.5, 0.6]], dtype=np.float32)

    refresh_thread = threading.Thread(target=fake_reload)
    refresh_thread.start()

    errors = []

    def simulate_requests():
        try:
            assert als.can_score_user(1) is True
            scores = als.score_candidates(1, [101])
            assert isinstance(scores, list)

            v = vec.get_vector(101)
            assert v is not None
        except Exception as e:
            errors.append(e)

    request_threads = [threading.Thread(target=simulate_requests) for _ in range(10)]

    for t in request_threads:
        t.start()

    for t in request_threads:
        t.join()

    refresh_thread.join()

    assert not errors