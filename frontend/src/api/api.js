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
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ✅ FIXED: FastAPI OAuth2 login expects x-www-form-urlencoded (NOT JSON)
export async function login(username, password) {
  const form = new URLSearchParams();
  form.append("username", username);
  form.append("password", password);

  const res = await axios.post(`${API_BASE}/users/login`, form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });

  return res.data; // should be { access_token, token_type }
}

// ---- your existing endpoints (examples; keep yours if different) ----
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
  const res = await api.get(`/movies/${movieId}/similar?limit=${limit}`);
  return res.data;
}

export async function getRecommendations(limit = 30) {
  const res = await api.get(`/recommendations?limit=${limit}`);
  return res.data;
}
