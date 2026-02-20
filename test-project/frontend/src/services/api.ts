import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type { ApiError } from "../types/api";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
});

// --- Request interceptor: attach JWT ---
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("access_token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// --- Response interceptor: 401 redirect + error normalization ---
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string; message?: string; code?: string }>) => {
    if (error.response?.status === 401) {
      // Try token refresh before redirecting
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken && error.config && !error.config._isRetry) {
        error.config._isRetry = true;
        try {
          const { data } = await axios.post("/api/v1/auth/refresh", {
            refresh_token: refreshToken,
          });
          localStorage.setItem("access_token", data.access_token);
          if (data.refresh_token) {
            localStorage.setItem("refresh_token", data.refresh_token);
          }
          error.config.headers.Authorization = `Bearer ${data.access_token}`;
          return api.request(error.config);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
          return Promise.reject(error);
        }
      }
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    }

    // Normalize error
    const apiError: ApiError = {
      status: error.response?.status ?? 500,
      message:
        error.response?.data?.detail ??
        error.response?.data?.message ??
        error.message ??
        "An unexpected error occurred",
      code: error.response?.data?.code ?? "UNKNOWN_ERROR",
    };

    return Promise.reject(apiError);
  },
);

// Extend AxiosRequestConfig to support retry flag
declare module "axios" {
  interface InternalAxiosRequestConfig {
    _isRetry?: boolean;
  }
}

export default api;
