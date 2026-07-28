import axios, { AxiosError, type AxiosRequestConfig } from "axios";
import type { ApiErrorShape, ApiResponse, AuthTokens } from "@/types";
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080/api/v1";
// Access token lives in memory only (never localStorage) so it can't be read by an
// XSS payload at rest; the refresh token lives in an httpOnly cookie set by the
// gateway, which JS cannot read at all.
let accessToken: string | null = null;
export const tokenStore = {
  getAccess: () => accessToken,
  set: (tokens: Pick<AuthTokens, "accessToken">) => {
    accessToken = tokens.accessToken;
  },
  clear: () => {
    accessToken = null;
  },
};
export class ApiError extends Error {
  constructor(public readonly info: ApiErrorShape) {
    super(info.message);
    this.name = "ApiError";
  }
}
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  withCredentials: true,
  headers: { Accept: "application/json", "Content-Type": "application/json" },
});
apiClient.interceptors.request.use((config) => {
  const id = crypto.randomUUID();
  config.headers.set("x-request-id", id);
  config.headers.set(
    "x-correlation-id",
    typeof window !== "undefined" ? (sessionStorage.getItem("creditflow_correlation_id") ?? id) : id,
  );
  const token = tokenStore.getAccess();
  if (token) config.headers.set("Authorization", `Bearer ${token}`);
  return config;
});
let refreshing: Promise<string> | null = null;
async function refreshAccessToken() {
  const response = await axios.post<ApiResponse<{ tokens: AuthTokens }>>(
    `${API_BASE_URL}/auth/refresh`,
    {},
    { timeout: 15000, withCredentials: true },
  );
  if (!response.data.success) throw new Error(response.data.error.message);
  tokenStore.set(response.data.data.tokens);
  return response.data.data.tokens.accessToken;
}
apiClient.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined;
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      try {
        refreshing ??= refreshAccessToken().finally(() => {
          refreshing = null;
        });
        const token = await refreshing;
        original.headers = { ...original.headers, Authorization: `Bearer ${token}` };
        return apiClient.request(original);
      } catch {
        tokenStore.clear();
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.assign("/login?session=expired");
        }
      }
    }
    const body = error.response?.data as Partial<ApiResponse<never>> | undefined;
    const failure = body && "error" in body ? body.error : undefined;
    throw new ApiError({
      status: error.response?.status ?? 0,
      code: failure?.code ?? error.code ?? "NETWORK_ERROR",
      message: failure?.message ?? error.message,
      details: failure?.details,
      requestId: body?.meta?.requestId,
    });
  },
);
export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  let last: unknown;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const response = await apiClient.request<ApiResponse<T>>(config);
      const payload = response.data as ApiResponse<T> | T;
      if (typeof payload === "object" && payload !== null && "success" in payload) {
        if (!payload.success)
          throw new ApiError({
            status: 400,
            code: payload.error.code,
            message: payload.error.message,
            details: payload.error.details,
            requestId: payload.meta.requestId,
          });
        return payload.data;
      }
      return payload;
    } catch (error) {
      last = error;
      if (
        config.method?.toUpperCase() !== "GET" ||
        (error instanceof ApiError && error.info.status >= 400 && error.info.status < 500)
      )
        break;
      await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
    }
  }
  throw last;
}
