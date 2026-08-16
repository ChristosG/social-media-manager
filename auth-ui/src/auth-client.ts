import type {
  RegisterRequest,
  LoginRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  VerifyMFARequest,
  DisableMFARequest,
  AuthTokenResponse,
  LoginResponse,
  RefreshResponse,
  MessageResponse,
  OAuthURLResponse,
  OAuthCallbackResponse,
  EnableMFAResponse,
  User,
  ApiError,
} from './types'

class AuthClientError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'AuthClientError'
    this.status = status
  }
}

// Hard ceiling on any auth request. Without it, a hung /refresh (e.g. the auth service mid-restart, or a
// stalled proxy hop) never settles, so the provider's init `await refresh()` never resolves and the app is
// pinned on the loading splash until a manual reload. A timeout turns that hang into a fast rejection, which
// the caller treats as "no session" → redirect to /login.
const REQUEST_TIMEOUT_MS = 8000

async function request<T>(
  baseUrl: string,
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${baseUrl}${path}`
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    credentials: 'include',
    signal: options.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  })

  const data = await res.json()

  if (!res.ok) {
    const err = data as ApiError
    throw new AuthClientError(
      err.message || err.error || 'Request failed',
      res.status,
    )
  }

  return data as T
}

export function createAuthClient(baseUrl: string) {
  return {
    register(data: RegisterRequest) {
      return request<AuthTokenResponse>(baseUrl, '/register', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    },

    login(data: LoginRequest, rememberMe?: boolean) {
      return request<LoginResponse>(baseUrl, '/login', {
        method: 'POST',
        body: JSON.stringify(data),
        headers: rememberMe != null ? { 'X-Remember-Me': rememberMe ? '1' : '0' } : {},
      })
    },

    refresh() {
      return request<RefreshResponse>(baseUrl, '/refresh', {
        method: 'POST',
      })
    },

    refreshWithToken(refreshToken: string) {
      return request<RefreshResponse>(baseUrl, '/refresh', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
    },

    forgotPassword(data: ForgotPasswordRequest) {
      return request<MessageResponse>(baseUrl, '/forgot-password', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    },

    resetPassword(data: ResetPasswordRequest) {
      return request<MessageResponse>(baseUrl, '/reset-password', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    },

    verifyMFA(data: VerifyMFARequest) {
      return request<AuthTokenResponse>(baseUrl, '/mfa/verify', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    },

    getMe(accessToken: string) {
      return request<{ user: User }>(baseUrl, '/me', {
        method: 'GET',
        headers: { Authorization: `Bearer ${accessToken}` },
      })
    },

    logout(accessToken: string) {
      return request<MessageResponse>(baseUrl, '/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
      })
    },

    enableMFA(accessToken: string) {
      return request<EnableMFAResponse>(baseUrl, '/mfa/enable', {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
      })
    },

    disableMFA(accessToken: string, data: DisableMFARequest) {
      return request<MessageResponse>(baseUrl, '/mfa/disable', {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify(data),
      })
    },

    getOAuthURL(provider: string, redirectUrl: string) {
      const params = new URLSearchParams({ redirect_url: redirectUrl })
      return request<OAuthURLResponse>(
        baseUrl,
        `/oauth/${provider}?${params}`,
        { method: 'GET' },
      )
    },

    oauthCallback(provider: string, code: string, state: string) {
      const params = new URLSearchParams({ code, state })
      return request<OAuthCallbackResponse>(
        baseUrl,
        `/oauth/${provider}/callback?${params}`,
        { method: 'GET' },
      )
    },
  }
}

export type AuthClient = ReturnType<typeof createAuthClient>
export { AuthClientError }
