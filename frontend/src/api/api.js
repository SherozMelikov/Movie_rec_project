import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";

function getToken() {
  return localStorage.getItem("access_token");
}

// Axios instance
const api = axios.create({
  baseURL: API_BASE,
});

// Automatically attach token for protected endpoints
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// --- Auth ---
export async function login(username, password) {
  const res = await axios.post(
    `${API_BASE}/users/login`,
    { username, password },
    { headers: { "Content-Type": "application/json" } }
  );
  return res.data; // {access_token, token_type} (or sometimes string)
}

// --- Movies ---
export async function browseMovies({ limit = 20 } = {}) {
  const res = await api.get(`/movies/browse?limit=${limit}`);
  return res.data;
}

export async function searchMovies(q, limit = 20) {
  const res = await api.get(`/movies/search?q=${encodeURIComponent(q)}&limit=${limit}`);
  return res.data;
}

export async function getMovie(movieId) {
  const res = await api.get(`/movies/${movieId}`);
  return res.data;
}

export async function getSimilar(movieId, limit = 12) {
  const res = await api.get(`/movies/${movieId}/similar?k=${limit}`); // ✅ backend uses k (not limit)
  return res.data;
}

// --- Recommendations ---
export async function getRecommendations(limit = 30) {
  const res = await api.get(`/recommendations?limit=${limit}`);
  return res.data;
}

// --- Onboarding ---
export async function getMyOnboarding() {
  const res = await api.get("/onboarding/me");
  return res.data;
}

export async function saveOnboarding(payload) {
  const res = await api.post("/onboarding", payload);
  return res.data;
}

export async function getGenres() {
  const res = await api.get("/movies/genres");
  return res.data;
}

// --- Events (VIEW ONLY) ---
export async function trackView(movieId) {
  // matches backend: POST /events with JSON body (EventCreate)
  // {movie_id, event_type:"view", rating_value:null}
  try {
    const res = await api.post("/events", {
      movie_id: Number(movieId),
      event_type: "view",
      rating_value: null,
    });
    return res.data;
  } catch {
    // don't block UI if analytics fails
    return null;
  }
}

// --- Likes (toggle) ---
export async function isLiked(movieId) {
  const res = await api.get(`/likes/${movieId}`);
  return res.data; // {liked:true/false}
}

export async function likeMovie(movieId) {
  const res = await api.post(`/likes/${movieId}`);
  return res.data; // {liked:true}
}

export async function unlikeMovie(movieId) {
  await api.delete(`/likes/${movieId}`);
  return { liked: false };
}

// --- Ratings (upsert) ---
export async function getMyRating(movieId) {
  const res = await api.get(`/ratings/${movieId}`);
  return res.data; // {score:number|null}
}

export async function setRating(movieId, score) {
  const res = await api.put(`/ratings/${movieId}`, { score: Number(score) });
  return res.data; // {score:number}
}
export async function signup(username, email, password) {
  const res = await axios.post(
    `${API_BASE}/users/signup`,
    { username, email, password },
    { headers: { "Content-Type": "application/json" } }
  );
  return res.data; // returns created user object
}
