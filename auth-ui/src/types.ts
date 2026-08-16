export interface User {
  id: string
  email: string
  display_name: string
  mfa_enabled: boolean
  email_verified: boolean
  created_at: string
  updated_at: string
  tenant_id?: string
  roles?: string[]
  permissions?: string[]
  modules?: string[]
}

export interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
}

export interface AuthConfig {
  apiUrl: string
  onNavigate?: (path: string) => void
  loginRedirect?: string
  logoutRedirect?: string
  dashboardRedirect?: string
}

// API Request types
export interface RegisterRequest {
  email: string
  password: string
  display_name: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RefreshTokenRequest {
  refresh_token: string
}

export interface LogoutRequest {
  refresh_token: string
}

export interface VerifyMFARequest {
  mfa_token: string
  code: string
}

export interface DisableMFARequest {
  code: string
}

export interface ForgotPasswordRequest {
  email: string
}

export interface ResetPasswordRequest {
  token: string
  new_password: string
}

// API Response types
export interface AuthTokenResponse {
  access_token: string
  refresh_token?: string
  user: User
}

export interface LoginResponse {
  access_token?: string
  refresh_token?: string
  user?: User
  requires_mfa: boolean
  mfa_token?: string
}

export interface RefreshResponse {
  access_token: string
  refresh_token?: string
  ephemeral?: boolean
}

export interface MessageResponse {
  message: string
}

export interface OAuthURLResponse {
  url: string
}

export interface OAuthCallbackResponse {
  access_token: string
  refresh_token?: string
  user: User
  is_new_user: boolean
}

export interface EnableMFAResponse {
  secret: string
  qr_code_url: string
  recovery_codes: string[]
}

export interface ApiError {
  error: string
  message?: string
  status?: number
}

// API Client types
export interface ApiClientConfig {
  getAccessToken: () => string | null
  refreshToken: () => Promise<string | null>
  baseUrl?: string
}

export interface ApiClient {
  get: <T = unknown>(path: string, options?: RequestInit) => Promise<T>
  post: <T = unknown>(path: string, body?: unknown, options?: RequestInit) => Promise<T>
  put: <T = unknown>(path: string, body?: unknown, options?: RequestInit) => Promise<T>
  patch: <T = unknown>(path: string, body?: unknown, options?: RequestInit) => Promise<T>
  delete: <T = unknown>(path: string, options?: RequestInit) => Promise<T>
}

// Login result for the auth context
export interface LoginResult {
  success: boolean
  requiresMFA?: boolean
  mfaToken?: string
  error?: string
}

// BFF handler config
export interface BFFConfig {
  gatewayUrl: string
  cookieName?: string
  cookieMaxAge?: number
  secureCookies?: boolean
}
