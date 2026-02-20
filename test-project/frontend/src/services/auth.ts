import api from "./api";
import type { User } from "../types/api";

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

interface LoginPayload {
  email: string;
  password: string;
}

interface RegisterPayload {
  email: string;
  password: string;
  name: string;
}

interface ProfileUpdatePayload {
  name?: string;
  avatarUrl?: string | null;
}

function storeTokens(tokens: AuthTokens): void {
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
}

function clearTokens(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export async function login(payload: LoginPayload): Promise<User> {
  const { data: tokens } = await api.post<AuthTokens>("/auth/login", payload);
  storeTokens(tokens);
  return getProfile();
}

export async function register(payload: RegisterPayload): Promise<User> {
  const { data: tokens } = await api.post<AuthTokens>("/auth/register", payload);
  storeTokens(tokens);
  return getProfile();
}

export async function logout(): Promise<void> {
  try {
    await api.post("/auth/logout");
  } finally {
    clearTokens();
  }
}

export async function refreshToken(): Promise<AuthTokens> {
  const currentRefreshToken = localStorage.getItem("refresh_token");
  if (!currentRefreshToken) {
    throw new Error("No refresh token available");
  }
  const { data } = await api.post<AuthTokens>("/auth/refresh", {
    refresh_token: currentRefreshToken,
  });
  storeTokens(data);
  return data;
}

export async function getProfile(): Promise<User> {
  const { data } = await api.get<User>("/auth/profile");
  return data;
}

export async function updateProfile(payload: ProfileUpdatePayload): Promise<User> {
  const { data } = await api.patch<User>("/auth/profile", payload);
  return data;
}
