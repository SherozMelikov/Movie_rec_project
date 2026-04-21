# 🎨 Frontend – Movie Recommendation System

## 📌 Overview

The frontend is built using **React** and provides the user interface for the movie recommendation system.

It is responsible for:

* user registration and login
* onboarding for cold-start personalization
* browsing movies
* viewing movie details
* displaying personalized recommendation sections
* sending likes and ratings to the backend
* managing protected routes and authentication state

---

## 🏗️ Architecture

The frontend follows a component-based structure:

```text
Pages → Components → API Layer → Backend
```

---

## 📁 Project Structure

```text
src/
  api/         # API communication layer
  components/  # reusable UI components
  context/     # global auth state
  hooks/       # custom hooks
  pages/       # route-level pages
  styles/      # styling
  App.js       # main routing setup
  config.js    # frontend configuration
  index.js     # application entry point
```

---

## 📄 Main Pages

* `GetStarted.jsx` → landing / introduction page
* `Home.jsx` → main movie browsing page
* `Login.jsx` → user login
* `Register.jsx` → user registration
* `OnboardingWizard.jsx` → collect initial preferences
* `MovieDetails.jsx` → detailed view of a movie
* `Recommendations.jsx` → personalized recommendation sections

---

## 🧩 Components

Reusable UI components include:

* `Navbar.jsx` → navigation bar
* `MovieCard.jsx` → single movie display
* `MovieGrid.jsx` → grid layout for movies
* `MovieRow.jsx` → horizontal recommendation rows
* `Loader.jsx` → loading state
* `ProtectedRoute.jsx` → route protection for authenticated pages

---

## 🔌 API Integration

The frontend communicates with the FastAPI backend through `src/api/api.js`.

It handles:

* authentication requests
* movie retrieval
* recommendations
* likes
* ratings
* onboarding submissions

---

## 🔐 Authentication

Authentication state is managed using:

* `AuthContext.js` → global auth context
* `useAuth.js` → custom hook for auth access
* `ProtectedRoute.jsx` → prevents access to protected pages for unauthenticated users

---

## 🚀 Running Frontend Locally

```bash
cd frontend
npm install
npm start
```

For production build:

```bash
npm run build
```

---

## 🔐 Environment Variables

Required variables:

* `VITE_API_BASE_URL` or frontend API base URL configuration used by the project

---

## 🧠 Notes

* The frontend is designed to work with the FastAPI backend
* Personalized recommendations are rendered from backend API responses
* Onboarding helps reduce the cold-start problem for new users
