import React, { createContext, useContext, useMemo, useState } from "react";
import { login as apiLogin } from "../api/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("access_token"));
  const isAuthed = !!token;

  async function login(username, password) {
    const data = await apiLogin(username, password);
    const accessToken = data.access_token;

    localStorage.setItem("access_token", accessToken);
    setToken(accessToken);
  }

  function logout() {
    localStorage.removeItem("access_token");
    setToken(null);
  }

  const value = useMemo(() => ({ token, isAuthed, login, logout }), [token, isAuthed]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
