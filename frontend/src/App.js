import React from "react";
import { Routes, Route, Link } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Home from "./pages/Home";
import MovieDetails from "./pages/MovieDetails";
import Recommendations from "./pages/Recommendations";
import { useAuth } from "./context/AuthContext";

function Navbar() {
  const { isAuthed, logout } = useAuth();

  return (
    <div style={{ padding: 12, borderBottom: "1px solid #ddd", display: "flex", gap: 12 }}>
      <Link to="/">Home</Link>
      <Link to="/recommendations">Recommendations</Link>
      <div style={{ marginLeft: "auto" }}>
        {isAuthed ? <button onClick={logout}>Logout</button> : <Link to="/login">Login</Link>}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <div>
      <Navbar />
      <div style={{ padding: 16 }}>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route path="/" element={<Home />} />
          <Route path="/movies/:movieId" element={<MovieDetails />} />

          <Route
            path="/recommendations"
            element={
              <ProtectedRoute>
                <Recommendations />
              </ProtectedRoute>
            }
          />
        </Routes>
      </div>
    </div>
  );
}
