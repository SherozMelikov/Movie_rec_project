import React from "react";
import { Routes, Route, Link, useLocation, Navigate } from "react-router-dom";

import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";

import GetStarted from "./pages/GetStarted";
import Login from "./pages/Login";
import Register from "./pages/Register";

import Home from "./pages/Home";
import MovieDetails from "./pages/MovieDetails";
import Recommendations from "./pages/Recommendations";

import OnboardingGenres from "./pages/OnboardingGenres";
import OnboardingMovies from "./pages/OnboardingMovies";
import "./styles/navbar.css"; 
function Navbar() {
  const { isAuthed, logout } = useAuth();

  return (
    <div className="nav">
      <div className="nav-inner">
        <Link to="/home" className="brand">
          <span className="brand-badge">M</span>
          <span>MovieRec</span>
        </Link>

        <div className="nav-links">
          <Link className="nav-link" to="/home">Home</Link>
          <Link className="nav-link" to="/recommendations">Recommendations</Link>
        </div>

        <div className="nav-right">
          {isAuthed ? (
            <button className="nav-btn" onClick={logout}>Logout</button>
          ) : (
            <>
              <Link className="nav-link" to="/login">Sign in</Link>
              <Link className="nav-btn nav-btnPrimary" to="/register">Get started</Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const location = useLocation();

  // No main navbar on these screens
  const hideNavbarRoutes = ["/", "/login", "/register", "/onboarding/genres", "/onboarding/movies"];
  const hideNavbar = hideNavbarRoutes.includes(location.pathname);

  return (
    <div>
      {!hideNavbar && <Navbar />}

      <div style={{ padding: hideNavbar ? 0 : 16 }}>
        <Routes>
          {/* Landing */}
          <Route path="/" element={<GetStarted />} />

          {/* Auth */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protect app pages */}
          <Route
            path="/home"
            element={
              <ProtectedRoute>
                <Home />
              </ProtectedRoute>
            }
          />

          <Route
            path="/movies/:movieId"
            element={
              <ProtectedRoute>
                <MovieDetails />
              </ProtectedRoute>
            }
          />

          {/* Onboarding */}
          <Route
            path="/onboarding/genres"
            element={
              <ProtectedRoute>
                <OnboardingGenres />
              </ProtectedRoute>
            }
          />
          <Route
            path="/onboarding/movies"
            element={
              <ProtectedRoute>
                <OnboardingMovies />
              </ProtectedRoute>
            }
          />

          {/* Recommendations */}
          <Route
            path="/recommendations"
            element={
              <ProtectedRoute>
                <Recommendations />
              </ProtectedRoute>
            }
          />

          {/* Redirect old home */}
          <Route path="/oldhome" element={<Navigate to="/home" replace />} />
        </Routes>
      </div>
    </div>
  );
}
