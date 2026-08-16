# Demo App

Reference implementation for `@platform/auth-ui`. Shows how to integrate the auth package into a Next.js app with minimal code.

This app runs against the platform gateway (auth service + gateway on `localhost:8080`).

## Running it

```bash
# Make sure the backend is running
cd /mnt/nvme2TB/microservices_agents/platform
docker compose up -d

# Build the auth-ui package (if not already built)
cd /mnt/nvme2TB/microservices_agents/auth-ui
bun install
bun run build

# Start the demo app
cd /mnt/nvme2TB/microservices_agents/demo-app
bun install
bun run dev
```

Open `http://localhost:3000`. You'll be redirected to the login page.

## What to test

| Flow | How |
|------|-----|
| Register | Go to `/register`, create an account. Redirects to dashboard. |
| Login | Go to `/login`, sign in. Redirects to dashboard. |
| Login without remember me | Uncheck "Remember me", login. Open a new tab to `localhost:3000` — you should NOT be auto-logged in. |
| Login with remember me | Check "Remember me", login. Open a new tab — you should be auto-logged in. |
| Logout | Click "Sign out" on dashboard. Redirects to login. |
| Protected route | Visit `/dashboard` while logged out — redirects to login. |
| Guest guard | Visit `/login` while logged in — redirects to dashboard. |
| Forgot password | Click "Forgot password?" on login page. Submit email. Backend logs the reset token (email sending is stubbed). |
| MFA setup | On dashboard, click "Enable two-factor authentication". Scan QR code with Google Authenticator/Authy. Click "Done". |
| MFA login | After enabling MFA, log out and log back in. After entering email/password, you'll be prompted for the 6-digit code. |
| Dark mode | Click the theme toggle button (top-right of dashboard). Cycles through light/dark/system. |
| API client | Dashboard shows an "API Client Test" card that calls `GET /api/auth/me` using `useApiClient()`. JWT is automatically attached. |
| Session persistence | Login with "remember me", refresh the page. Session should be restored without re-entering credentials. |
| Token security | Open browser devtools → Application → Cookies. The `platform_refresh_token` cookie should be `httpOnly`. No tokens should appear in localStorage. |

## Project structure

```
src/app/
├── layout.tsx                          # Imports styles, wraps with Providers
├── providers.tsx                       # AuthProvider + ThemeProvider + router
├── page.tsx                            # Redirect: /login or /dashboard
├── login/page.tsx                      # LoginPage component
├── register/page.tsx                   # RegisterPage component
├── forgot-password/page.tsx            # ForgotPasswordPage component
├── reset-password/page.tsx             # ResetPasswordPage component (reads ?token= from URL)
├── dashboard/page.tsx                  # Protected page: profile, MFA setup, API test, theme toggle
├── auth/callback/[provider]/page.tsx   # OAuth callback handler
└── api/auth/[...path]/route.ts         # BFF proxy (one-liner)
```

## How the integration works

The entire auth integration is **5 files** of actual app code:

### 1. BFF route handler — `api/auth/[...path]/route.ts`

```ts
import { createBFFRouteHandler } from '@platform/auth-ui/server'

export const { GET, POST, PUT, DELETE } = createBFFRouteHandler({
  gatewayUrl: process.env.GATEWAY_URL || 'http://localhost:8080',
})
```

This is the security layer. All auth requests from the browser go through here. The handler:
- Proxies requests to the gateway
- Intercepts login/register responses to extract the refresh token
- Sets the refresh token as an httpOnly cookie (when "remember me" is on)
- On refresh requests, reads the cookie and forwards it to the gateway
- On logout, clears the cookie

### 2. Providers — `providers.tsx`

```tsx
'use client'
import { useRouter } from 'next/navigation'
import { AuthProvider, ThemeProvider } from '@platform/auth-ui'

export function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  return (
    <ThemeProvider>
      <AuthProvider apiUrl="/api/auth" onNavigate={(path) => router.push(path)}>
        {children}
      </AuthProvider>
    </ThemeProvider>
  )
}
```

`apiUrl="/api/auth"` points to the BFF route, not directly to the gateway. The `onNavigate` callback connects auth-ui's navigation to Next.js's router.

### 3. Layout — `layout.tsx`

```tsx
import '@platform/auth-ui/styles.css'
import { Providers } from './providers'

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body><Providers>{children}</Providers></body>
    </html>
  )
}
```

One CSS import. One provider wrapper. That's it.

### 4. Auth pages — `login/page.tsx`, `register/page.tsx`, etc.

Each page is a single component import:

```tsx
'use client'
import { useRouter } from 'next/navigation'
import { LoginPage } from '@platform/auth-ui'

export default function Login() {
  const router = useRouter()
  return (
    <LoginPage
      onNavigate={(path) => router.push(path)}
      onSuccess={() => router.push('/dashboard')}
      showOAuth
    />
  )
}
```

### 5. Protected pages — `dashboard/page.tsx`

```tsx
import { AuthGuard, useAuth, useApiClient } from '@platform/auth-ui'

export default function Dashboard() {
  return (
    <AuthGuard onUnauthenticated={() => router.push('/login')}>
      <DashboardContent />
    </AuthGuard>
  )
}

function DashboardContent() {
  const { user, logout } = useAuth()
  const api = useApiClient()

  // api.get() automatically attaches the JWT
  const data = await api.get('/api/v1/products')
}
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_URL` | `http://localhost:8080` | Platform gateway URL |

## Token flow

```
Browser                    This App (BFF)              Gateway (:8080)
  │                            │                          │
  │  Login form submit         │                          │
  │  POST /api/auth/login  ──► │                          │
  │                            │  POST /api/v1/auth/login │
  │                            │  ──────────────────────► │
  │                            │                          │
  │                            │  ◄── access_token +      │
  │                            │      refresh_token       │
  │                            │                          │
  │  ◄── access_token (JSON)   │                          │
  │  + httpOnly cookie         │                          │
  │    (refresh_token)         │                          │
  │                            │                          │
  │  GET /api/auth/me          │                          │
  │  Authorization: Bearer ──► │  GET /api/v1/auth/me     │
  │                            │  ──────────────────────► │
  │                            │  ◄── user profile        │
  │  ◄── user profile          │                          │
```

The browser never sees the refresh token (stored as httpOnly cookie). The access token lives in React state (memory only).
