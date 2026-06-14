import { api } from "./api.js";

const LOGIN_URL = "/api/auth/login/";
const REGISTER_URL = "/api/auth/register/";

function setUserEmail(email) {
  const target = document.getElementById("user-email");
  const loginLink = document.getElementById("login-link");
  const registerLink = document.getElementById("register-link");
  const logoutButton = document.getElementById("logout-button");
  if (!target) return;
  if (email) {
    target.textContent = email;
    loginLink?.classList.add("d-none");
    registerLink?.classList.add("d-none");
    logoutButton?.classList.remove("d-none");
  } else {
    target.textContent = "";
    loginLink?.classList.remove("d-none");
    registerLink?.classList.remove("d-none");
    logoutButton?.classList.add("d-none");
  }
}

async function refreshUserMenu() {
  if (!api.hasAccessToken()) {
    setUserEmail(null);
    return;
  }
  try {
    const me = await api.me();
    setUserEmail(me.email);
  } catch (_error) {
    setUserEmail(null);
  }
}

async function login(email, password) {
  const response = await fetch(LOGIN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new Error("Invalid email or password.");
  }
  const body = await response.json();
  api.clearTokens();
  localStorage.setItem("access", body.access);
  localStorage.setItem("refresh", body.refresh);
  await refreshUserMenu();
}

async function register(email, password) {
  const response = await fetch(REGISTER_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, password_confirm: password }),
  });
  if (!response.ok) {
    let detail = "Registration failed.";
    try {
      const errorBody = await response.json();
      if (errorBody.password_confirm) {
        detail = "Passwords do not match.";
      } else if (errorBody.password) {
        detail = "Password validation failed.";
      } else if (errorBody.email) {
        detail = "Email is already registered.";
      }
    } catch (_parseError) {
      // ignore: response had no JSON body
    }
    throw new Error(detail);
  }
}

function logout() {
  api.clearTokens();
  setUserEmail(null);
  window.location.href = "/";
}

function requireAuth(_redirectPath = "/map/") {
  if (!api.hasAccessToken()) {
    window.location.href = "/login/";
    return false;
  }
  return true;
}

document.getElementById("logout-button")?.addEventListener("click", logout);
refreshUserMenu();

export const auth = { login, register, logout, requireAuth, refreshUserMenu };
