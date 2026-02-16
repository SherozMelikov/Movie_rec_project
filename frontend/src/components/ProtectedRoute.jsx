import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { isAuthed } = useAuth();
  const location = useLocation();

  if (!isAuthed) {
    // Send user to Landing page (Netflix style)
    // keep where they were trying to go
    return <Navigate to="/" replace state={{ from: location }} />;
  }

  return children;
}
