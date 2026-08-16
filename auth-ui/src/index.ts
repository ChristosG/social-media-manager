// Context & Hooks
export { AuthProvider, useAuth, useApiClient, useWSClient } from './auth-context'
export type { AuthContextValue, AuthProviderProps } from './auth-context'

// Theme
export { ThemeProvider, ThemeToggle, useTheme } from './theme-provider'

// API Client
export { createApiClient } from './api-client'
export { ApiRequestError } from './api-client'

// WebSocket Client
export { createWSClient } from './ws-client'
export type { WSClientConfig, AuthenticatedWebSocket } from './ws-client'

// Token Manager
export { getAccessToken, setAccessToken, clearAccessToken, parseJwtClaims } from './token-manager'
export type { JwtClaims } from './token-manager'

// Pages
export { LoginPage } from './pages/login-page'
export { RegisterPage } from './pages/register-page'
export { ForgotPasswordPage } from './pages/forgot-password-page'
export { ResetPasswordPage } from './pages/reset-password-page'

// Forms
export { LoginForm } from './forms/login-form'
export { RegisterForm } from './forms/register-form'
export { ForgotPasswordForm } from './forms/forgot-password-form'
export { ResetPasswordForm } from './forms/reset-password-form'
export { OAuthButtons } from './forms/oauth-buttons'
export { MFAVerifyForm } from './forms/mfa-verify'
export { MFASetup } from './forms/mfa-setup'

// Guards
export { AuthGuard } from './guards/auth-guard'
export { GuestGuard } from './guards/guest-guard'

// OAuth
export { OAuthCallbackHandler } from './oauth/oauth-callback-handler'

// UI Components
export { Button } from './components/ui/button'
export { Input } from './components/ui/input'
export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent } from './components/ui/card'
export { Label } from './components/ui/label'
export { Separator } from './components/ui/separator'
export { Switch } from './components/ui/switch'
export { PasswordInput } from './components/ui/password-input'

// Types
export type {
  User,
  AuthState,
  AuthConfig,
  LoginResult,
  ApiClient,
  ApiClientConfig,
  RegisterRequest,
  LoginRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  VerifyMFARequest,
  AuthTokenResponse,
  LoginResponse,
  RefreshResponse,
  MessageResponse,
  EnableMFAResponse,
  OAuthURLResponse,
  OAuthCallbackResponse,
  BFFConfig,
} from './types'
