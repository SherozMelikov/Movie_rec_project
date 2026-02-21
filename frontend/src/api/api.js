import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";

function getToken() {
  return localStorage.getItem("access_token");
}

// ✅ One axios instance for everything
export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});


// Automatically attach token for protected endpoints
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});


// ✅ Professional: normalize errors from FastAPI/our custom schema
export function normalizeApiError(err) {
  const status = err?.response?.status;
  const data = err?.response?.data;

  // Network / CORS / server down
  if (!err?.response) {
    return {
      status: 0,
      code: "NETWORK_ERROR",
      formError: "Can’t reach the server. Check your connection and try again.",
      fieldErrors: {},
    };
  }

  const detail = data?.detail;

  // FastAPI validation (422) => detail is array
  if (status === 422 && Array.isArray(detail)) {
    const fieldErrors = {};
    detail.forEach((x) => {
      const field = x?.loc?.[x.loc.length - 1];
      if (field && !fieldErrors[field]) fieldErrors[field] = x.msg;
    });
    return {
      status,
      code: "VALIDATION_ERROR",
      formError: "Please fix the highlighted fields.",
      fieldErrors,
    };
  }

  // Our custom error payload => detail is object {detail, code, field_errors}
  if (detail && typeof detail === "object") {
    return {
      status,
      code: detail.code || "ERROR",
      formError: detail.detail || "Something went wrong.",
      fieldErrors: detail.field_errors || {},
    };
  }

  // Plain string detail
  if (typeof detail === "string") {
    return {
      status,
      code: "ERROR",
      formError: detail,
      fieldErrors: {},
    };
  }

  // Fallback
  return {
    status,
    code: "ERROR",
    formError: "Something went wrong. Please try again.",
    fieldErrors: {},
  };
}

// --- Auth ---
export async function login(username, password) {
  const res = await api.post("/users/login", { username, password });
  return res.data; // {access_token, token_type}
}


export async function signup(username, email, password) {
  const res = await api.post("/users/signup", { username, email, password });
  return res.data; // created user
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
  const res = await api.get(`/movies/${movieId}/similar?k=${limit}`);
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
  return res.data;
}

export async function likeMovie(movieId) {
  const res = await api.post(`/likes/${movieId}`);
  return res.data;
}

export async function unlikeMovie(movieId) {
  await api.delete(`/likes/${movieId}`);
  return { liked: false };
}

// --- Ratings (upsert) ---
export async function getMyRating(movieId) {
  const res = await api.get(`/ratings/${movieId}`);
  return res.data;
}

export async function setRating(movieId, score) {
  const res = await api.put(`/ratings/${movieId}`, { score: Number(score) });
  return res.data;
}


export async function getRecommendationSections(limitPerSection = 12) {
  const res = await api.get(`/recommendations/sections?limit_per_section=${limitPerSection}`);
  return res.data;
}

