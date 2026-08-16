import * as React from 'react'
import { createAuthClient, type AuthClient } from './auth-client'
import { createApiClient } from './api-client'
import { createWSClient } from './ws-client'
import {
  getAccessToken,
  setAccessToken,
  clearAccessToken,
  getSecondsUntilExpiry,
  parseJwtClaims,
} from './token-manager'
import type {
  User,
  AuthConfig,
  LoginResult,
  ApiClient,
  RegisterRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  EnableMFAResponse,
} from './types'

interface AuthContextValue {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string, rememberMe?: boolean) => Promise<LoginResult>
  register: (email: string, password: string, displayName: string) => Promise<LoginResult>
  logout: () => Promise<void>
  completeMFALogin: (mfaToken: string, code: string) => Promise<LoginResult>
  forgotPassword: (email: string) => Promise<{ success: boolean; error?: string }>
  resetPassword: (token: string, newPassword: string) => Promise<{ success: boolean; error?: string }>
  enableMFA: () => Promise<EnableMFAResponse>
  disableMFA: (code: string) => Promise<{ success: boolean; error?: string }>
  getToken: () => string | null
  refreshSession: () => Promise<string | null>
  updateSession: (accessToken: string, refreshToken?: string) => void
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

interface AuthProviderProps {
  children: React.ReactNode
  apiUrl: string
  onNavigate?: (path: string) => void
  loginRedirect?: string
  logoutRedirect?: string
  dashboardRedirect?: string
}

function AuthProvider({
  children,
  apiUrl,
  onNavigate,
  loginRedirect = '/login',
  logoutRedirect = '/login',
  dashboardRedirect = '/dashboard',
}: AuthProviderProps) {
  const [user, setUser] = React.useState<User | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)
  const refreshTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const refreshPromiseRef = React.useRef<Promise<string | null> | null>(null)
  const clientRef = React.useRef<AuthClient>(createAuthClient(apiUrl))

  // In-memory refresh token for ephemeral (no remember me) sessions.
  // This is tab-scoped: new tab / page refresh = gone = must login again.
  const ephemeralRefreshTokenRef = React.useRef<string | null>(null)

  const enrichUserWithClaims = React.useCallback((u: User, token: string): User => {
    const claims = parseJwtClaims(token)
    if (!claims) return u
    const modules = claims.custom?.modules
      ? claims.custom.modules.split(',').filter(Boolean)
      : u.modules
    return {
      ...u,
      tenant_id: claims.tid ?? u.tenant_id,
      roles: claims.roles ?? u.roles,
      permissions: claims.permissions ?? u.permissions,
      modules,
    }
  }, [])

  const navigate = React.useCallback(
    (path: string) => {
      if (onNavigate) {
        onNavigate(path)
      } else if (typeof window !== 'undefined') {
        window.location.href = path
      }
    },
    [onNavigate],
  )

  const scheduleRefresh = React.useCallback((token: string) => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current)
    }

    const secondsUntilExpiry = getSecondsUntilExpiry(token)
    if (secondsUntilExpiry === null || secondsUntilExpiry <= 60) return

    const refreshInMs = (secondsUntilExpiry - 60) * 1000
    refreshTimerRef.current = setTimeout(() => {
      refreshSession()
    }, refreshInMs)
  }, [])

  const refreshSession = React.useCallback(async (): Promise<string | null> => {
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current
    }

    refreshPromiseRef.current = (async () => {
      try {
        // If we have an ephemeral refresh token, send it in the body
        const ephemeralToken = ephemeralRefreshTokenRef.current
        const res = ephemeralToken
          ? await clientRef.current.refreshWithToken(ephemeralToken)
          : await clientRef.current.refresh()

        if (res.access_token) {
          setAccessToken(res.access_token)
          scheduleRefresh(res.access_token)

          // If BFF returned a new ephemeral refresh token, store it
          if (res.refresh_token && res.ephemeral) {
            ephemeralRefreshTokenRef.current = res.refresh_token
          }

          return res.access_token
        }
        return null
      } catch {
        clearAccessToken()
        ephemeralRefreshTokenRef.current = null
        setUser(null)
        return null
      } finally {
        refreshPromiseRef.current = null
      }
    })()

    return refreshPromiseRef.current
  }, [scheduleRefresh])

  // Initialize — try to restore session via BFF cookie refresh
  // (only works for "remember me" sessions; ephemeral ones are gone on reload)
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await clientRef.current.refresh()
        if (cancelled) return
        if (res.access_token) {
          setAccessToken(res.access_token)
          scheduleRefresh(res.access_token)
          const meRes = await clientRef.current.getMe(res.access_token)
          if (!cancelled) setUser(enrichUserWithClaims(meRes.user, res.access_token))
        }
      } catch {
        // No valid session
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    })()

    return () => {
      cancelled = true
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
    }
  }, [scheduleRefresh])

  const login = React.useCallback(
    async (email: string, password: string, rememberMe?: boolean): Promise<LoginResult> => {
      try {
        const res = await clientRef.current.login({ email, password }, rememberMe)

        if (res.requires_mfa) {
          return { success: false, requiresMFA: true, mfaToken: res.mfa_token }
        }

        if (res.access_token) {
          setAccessToken(res.access_token)
          scheduleRefresh(res.access_token)
          if (res.user) setUser(enrichUserWithClaims(res.user, res.access_token))

          // Ephemeral mode: BFF returned refresh_token in body (no cookie)
          if (res.refresh_token) {
            ephemeralRefreshTokenRef.current = res.refresh_token
          } else {
            ephemeralRefreshTokenRef.current = null
          }

          return { success: true }
        }

        return { success: false, error: 'No access token received' }
      } catch (err) {
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Login failed',
        }
      }
    },
    [scheduleRefresh],
  )

  const register = React.useCallback(
    async (email: string, password: string, displayName: string): Promise<LoginResult> => {
      try {
        const res = await clientRef.current.register({
          email,
          password,
          display_name: displayName,
        })

        if (res.access_token) {
          setAccessToken(res.access_token)
          scheduleRefresh(res.access_token)
          setUser(enrichUserWithClaims(res.user, res.access_token))
          return { success: true }
        }

        return { success: false, error: 'No access token received' }
      } catch (err) {
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Registration failed',
        }
      }
    },
    [scheduleRefresh],
  )

  const completeMFALogin = React.useCallback(
    async (mfaToken: string, code: string): Promise<LoginResult> => {
      try {
        const res = await clientRef.current.verifyMFA({ mfa_token: mfaToken, code })

        if (res.access_token) {
          setAccessToken(res.access_token)
          scheduleRefresh(res.access_token)
          setUser(enrichUserWithClaims(res.user, res.access_token))
          return { success: true }
        }

        return { success: false, error: 'No access token received' }
      } catch (err) {
        return {
          success: false,
          error: err instanceof Error ? err.message : 'MFA verification failed',
        }
      }
    },
    [scheduleRefresh],
  )

  const logout = React.useCallback(async () => {
    const token = getAccessToken()
    if (token) {
      try {
        await clientRef.current.logout(token)
      } catch {
        // best-effort
      }
    }
    clearAccessToken()
    ephemeralRefreshTokenRef.current = null
    setUser(null)
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
    navigate(logoutRedirect)
  }, [logoutRedirect, navigate])

  const forgotPassword = React.useCallback(
    async (email: string) => {
      try {
        await clientRef.current.forgotPassword({ email })
        return { success: true }
      } catch (err) {
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Request failed',
        }
      }
    },
    [],
  )

  const resetPassword = React.useCallback(
    async (token: string, newPassword: string) => {
      try {
        await clientRef.current.resetPassword({ token, new_password: newPassword })
        return { success: true }
      } catch (err) {
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Reset failed',
        }
      }
    },
    [],
  )

  const enableMFA = React.useCallback(async () => {
    const token = getAccessToken()
    if (!token) throw new Error('Not authenticated')
    return clientRef.current.enableMFA(token)
  }, [])

  const disableMFA = React.useCallback(
    async (code: string) => {
      const token = getAccessToken()
      if (!token) return { success: false, error: 'Not authenticated' }
      try {
        await clientRef.current.disableMFA(token, { code })
        setUser((prev) => (prev ? { ...prev, mfa_enabled: false } : null))
        return { success: true }
      } catch (err) {
        return {
          success: false,
          error: err instanceof Error ? err.message : 'Failed to disable MFA',
        }
      }
    },
    [],
  )

  const updateSession = React.useCallback(
    (accessToken: string, refreshToken?: string) => {
      setAccessToken(accessToken)
      scheduleRefresh(accessToken)
      if (refreshToken) {
        ephemeralRefreshTokenRef.current = refreshToken
      }
      // Re-enrich user with new token claims
      setUser((prev) => {
        if (!prev) return prev
        return enrichUserWithClaims(prev, accessToken)
      })
    },
    [scheduleRefresh, enrichUserWithClaims],
  )

  const value = React.useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      register,
      logout,
      completeMFALogin,
      forgotPassword,
      resetPassword,
      enableMFA,
      disableMFA,
      getToken: getAccessToken,
      refreshSession,
      updateSession,
    }),
    [user, isLoading, login, register, logout, completeMFALogin, forgotPassword, resetPassword, enableMFA, disableMFA, refreshSession, updateSession],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}

function useApiClient(): ApiClient {
  const { getToken, refreshSession } = useAuth()

  return React.useMemo(
    () =>
      createApiClient({
        getAccessToken: getToken,
        refreshToken: refreshSession,
      }),
    [getToken, refreshSession],
  )
}

function useWSClient() {
  const { getToken, refreshSession } = useAuth()

  return React.useMemo(
    () =>
      createWSClient({
        getAccessToken: getToken,
        refreshToken: refreshSession,
      }),
    [getToken, refreshSession],
  )
}

export { AuthProvider, useAuth, useApiClient, useWSClient, AuthContext }
export type { AuthContextValue, AuthProviderProps }
