# @platform/auth-ui

Drop-in authentication UI for Next.js apps. Install, wrap your app, and get login/register/MFA pages with secure token management out of the box.

Built for the platform gateway (`/api/v1/auth/*` endpoints). Works with any Next.js 15+ app.

## What's included

- **Pre-built pages** — Login, Register, Forgot Password, Reset Password
- **MFA support** — TOTP setup with QR code, 6-digit verification flow
- **OAuth buttons** — Google & GitHub (bring your own provider credentials)
- **Token security** — Access token in memory, refresh token in httpOnly cookie (or memory-only for ephemeral sessions)
- **Auto-refresh** — Timer-based refresh 60s before expiry, plus 401 interceptor fallback
- **Remember me** — Checked = persistent cookie (7 days), unchecked = tab-scoped session (no cookie, no cross-tab leakage)
- **Authenticated API client** — Fetch wrapper that auto-injects JWTs for any endpoint
- **Dark/light theme** — System detection, toggle component, OKLCH colors, customizable via CSS variables
- **Route guards** — `AuthGuard` and `GuestGuard` components for protected/public routes
- **Fluid typography** — Text scales smoothly between mobile and desktop via `clamp()`

## Quick start

### 1. Install

```bash
bun add @platform/auth-ui
```

Or with npm/pnpm — the package is compatible with any package manager.

For local development with a file reference:

```json
{
  "dependencies": {
    "@platform/auth-ui": "file:../auth-ui"
  }
}
```

If using a local `file:` reference, add to `next.config.ts`:

```ts
const nextConfig: NextConfig = {
  transpilePackages: ['@platform/auth-ui'],
}
```

### 2. Add the BFF route handler

Create `app/api/auth/[...path]/route.ts`:

```ts
import { createBFFRouteHandler } from '@platform/auth-ui/server'

export const { GET, POST, PUT, DELETE } = createBFFRouteHandler({
  gatewayUrl: process.env.GATEWAY_URL || 'http://localhost:8080',
})
```

This proxies all auth requests through your Next.js server. It handles:
- Setting/reading httpOnly cookies for refresh tokens
- Stripping refresh tokens from responses sent to the browser
- Ephemeral sessions (no cookie) when "remember me" is unchecked

### 3. Import styles and wrap with providers

`app/layout.tsx`:

```tsx
import '@platform/auth-ui/styles.css'
import { Providers } from './providers'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
```

`app/providers.tsx`:

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

### 4. Add pages

```tsx
// app/login/page.tsx
'use client'
import { useRouter } from 'next/navigation'
import { LoginPage } from '@platform/auth-ui'

export default function Login() {
  const router = useRouter()
  return (
    <LoginPage
      onNavigate={(path) => router.push(path)}
      onSuccess={() => router.push('/dashboard')}
      showOAuth  // shows Google/GitHub buttons
    />
  )
}
```

```tsx
// app/register/page.tsx
'use client'
import { useRouter } from 'next/navigation'
import { RegisterPage } from '@platform/auth-ui'

export default function Register() {
  const router = useRouter()
  return (
    <RegisterPage
      onNavigate={(path) => router.push(path)}
      onSuccess={() => router.push('/dashboard')}
      showOAuth
    />
  )
}
```

```tsx
// app/forgot-password/page.tsx
'use client'
import { useRouter } from 'next/navigation'
import { ForgotPasswordPage } from '@platform/auth-ui'

export default function ForgotPassword() {
  const router = useRouter()
  return <ForgotPasswordPage onNavigate={(path) => router.push(path)} />
}
```

### 5. Protect routes

```tsx
// app/dashboard/page.tsx
'use client'
import { useRouter } from 'next/navigation'
import { useAuth, useApiClient, AuthGuard, ThemeToggle, MFASetup, Button } from '@platform/auth-ui'

export default function Dashboard() {
  const router = useRouter()

  return (
    <AuthGuard onUnauthenticated={() => router.push('/login')}>
      <DashboardContent />
    </AuthGuard>
  )
}

function DashboardContent() {
  const { user, logout } = useAuth()
  const api = useApiClient()

  // api.get/post/put/delete automatically attach the JWT
  const handleLoadData = async () => {
    const data = await api.get('/api/v1/products')
  }

  return (
    <div>
      <p>Welcome, {user?.display_name}</p>
      <ThemeToggle />
      <MFASetup />
      <Button onClick={logout}>Sign out</Button>
    </div>
  )
}
```

## API reference

### Providers

#### `<AuthProvider>`

Wraps your app. Manages auth state, token storage, auto-refresh.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `apiUrl` | `string` | required | BFF route prefix (e.g. `/api/auth`) |
| `onNavigate` | `(path: string) => void` | `window.location.href` | Navigation handler |
| `loginRedirect` | `string` | `/login` | Where to send unauthenticated users |
| `logoutRedirect` | `string` | `/login` | Where to send after logout |
| `dashboardRedirect` | `string` | `/dashboard` | Where to send authenticated users |

#### `<ThemeProvider>`

Wraps your app for dark/light mode support.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `defaultTheme` | `string` | `system` | Initial theme (`light`, `dark`, `system`) |
| `storageKey` | `string` | `pau-theme` | localStorage key for persistence |

### Hooks

#### `useAuth()`

Returns the auth context. Must be inside `<AuthProvider>`.

```ts
const {
  user,              // User | null
  isAuthenticated,   // boolean
  isLoading,         // boolean (true during initial session restore)
  login,             // (email, password, rememberMe?) => Promise<LoginResult>
  register,          // (email, password, displayName) => Promise<LoginResult>
  logout,            // () => Promise<void>
  completeMFALogin,  // (mfaToken, code) => Promise<LoginResult>
  forgotPassword,    // (email) => Promise<{ success, error? }>
  resetPassword,     // (token, newPassword) => Promise<{ success, error? }>
  enableMFA,         // () => Promise<EnableMFAResponse>
  disableMFA,        // (code) => Promise<{ success, error? }>
  getToken,          // () => string | null
  refreshSession,    // () => Promise<string | null>
} = useAuth()
```

#### `useApiClient()`

Returns an authenticated fetch wrapper. Automatically injects the access token and retries on 401.

```ts
const api = useApiClient()

const data = await api.get<Product[]>('/api/v1/products')
await api.post('/api/v1/orders', { items: [...] })
await api.put('/api/v1/users/me', { display_name: 'New Name' })
await api.delete('/api/v1/sessions/123')
```

#### `useTheme()`

Re-exported from `next-themes`. Returns `{ theme, setTheme, systemTheme }`.

### Page components

Full-page components with card layout, form validation, error handling, and navigation links.

| Component | Props |
|-----------|-------|
| `<LoginPage>` | `onNavigate`, `onSuccess`, `showOAuth`, `title`, `description` |
| `<RegisterPage>` | `onNavigate`, `onSuccess`, `showOAuth`, `title`, `description` |
| `<ForgotPasswordPage>` | `onNavigate`, `title`, `description` |
| `<ResetPasswordPage>` | `token`, `onNavigate`, `title`, `description` |

### Form components

Standalone forms without page chrome. Use these if you want custom layouts.

| Component | Props |
|-----------|-------|
| `<LoginForm>` | `onMFARequired`, `onSuccess`, `onNavigate` |
| `<RegisterForm>` | `onSuccess` |
| `<ForgotPasswordForm>` | `onSuccess` |
| `<ResetPasswordForm>` | `token`, `onSuccess` |
| `<MFAVerifyForm>` | `mfaToken`, `onSuccess`, `onBack` |
| `<MFASetup>` | `onComplete` |
| `<OAuthButtons>` | `providers`, `apiUrl`, `label` |

### Guards

| Component | Props | Behavior |
|-----------|-------|----------|
| `<AuthGuard>` | `onUnauthenticated`, `fallback` | Shows children if authenticated, calls `onUnauthenticated` otherwise |
| `<GuestGuard>` | `onAuthenticated`, `fallback` | Shows children if NOT authenticated, calls `onAuthenticated` otherwise |

### UI components

Vendored shadcn/ui-style components. Use them in your own pages if you want visual consistency.

`Button`, `Input`, `PasswordInput`, `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`, `Label`, `Separator`, `Switch`

### Server exports

Import from `@platform/auth-ui/server`:

#### `createBFFRouteHandler(config)`

Creates Next.js Route Handlers that proxy auth requests to your gateway.

```ts
import { createBFFRouteHandler } from '@platform/auth-ui/server'

export const { GET, POST, PUT, DELETE } = createBFFRouteHandler({
  gatewayUrl: 'http://localhost:8080',   // required
  cookieName: 'platform_refresh_token',  // default
  cookieMaxAge: 7 * 24 * 60 * 60,       // 7 days, default
  secureCookies: true,                   // default: true in production
})
```

## Token security model

### Remember me ON (default)

```
Browser                    Next.js BFF                 Gateway
  │                            │                          │
  │  POST /api/auth/login      │                          │
  │  X-Remember-Me: 1          │                          │
  │  {email, password}  ────►  │  POST /api/v1/auth/login │
  │                            │  ──────────────────────►  │
  │                            │  ◄── {access_token,       │
  │                            │       refresh_token}      │
  │  ◄── {access_token, user}  │                          │
  │  + Set-Cookie: httpOnly    │                          │
  │    (refresh_token, 7 days) │                          │
```

- Access token: in-memory (React state), never persisted
- Refresh token: httpOnly cookie, invisible to JS, survives browser restart
- New tabs auto-login via cookie
- Page refresh restores session

### Remember me OFF

```
Browser                    Next.js BFF                 Gateway
  │                            │                          │
  │  POST /api/auth/login      │                          │
  │  X-Remember-Me: 0          │                          │
  │  {email, password}  ────►  │  POST /api/v1/auth/login │
  │                            │  ──────────────────────►  │
  │                            │  ◄── {access_token,       │
  │                            │       refresh_token}      │
  │  ◄── {access_token,        │                          │
  │       refresh_token, user}  │  (no cookie set)         │
```

- Access token: in-memory
- Refresh token: in-memory (React ref), tab-scoped
- New tab = no session (must login again)
- Page refresh = session lost
- Browser close = session lost

## Customizing the theme

All colors use CSS custom properties with a `--pau-` prefix. Override them in your app's CSS:

```css
:root {
  --pau-primary: oklch(0.6 0.2 145);        /* green instead of purple */
  --pau-primary-foreground: oklch(1 0 0);
  --pau-radius: 0px;                         /* sharp corners */
  --pau-text-base: 16px;                     /* fixed font size */
}

.dark {
  --pau-primary: oklch(0.7 0.2 145);
  --pau-background: oklch(0.1 0 0);
}
```

Full list of variables available in `src/styles/globals.css`.

## Gateway API compatibility

The package expects these endpoints on your gateway:

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/v1/auth/register` | No | Create account |
| POST | `/api/v1/auth/login` | No | Sign in |
| POST | `/api/v1/auth/refresh` | No | Refresh tokens |
| POST | `/api/v1/auth/logout` | Bearer | Sign out |
| GET | `/api/v1/auth/me` | Bearer | Get current user |
| POST | `/api/v1/auth/forgot-password` | No | Request password reset |
| POST | `/api/v1/auth/reset-password` | No | Complete password reset |
| POST | `/api/v1/auth/mfa/enable` | Bearer | Start MFA setup |
| POST | `/api/v1/auth/mfa/verify` | No | Verify MFA code during login |
| POST | `/api/v1/auth/mfa/disable` | Bearer | Turn off MFA |
| GET | `/api/v1/auth/oauth/{provider}` | No | Get OAuth redirect URL |
| GET | `/api/v1/auth/oauth/{provider}/callback` | No | Exchange OAuth code for tokens |

## Building from source

```bash
bun install
bun run build
```

Output in `dist/`:
- `index.js` / `index.cjs` — Client bundle (ESM + CJS)
- `index.d.ts` — TypeScript declarations
- `server.js` / `server.cjs` — Server bundle (BFF handler)
- `server.d.ts` — Server declarations
- `styles.css` — Compiled Tailwind CSS

## Project structure

```
src/
├── index.ts              # Client exports
├── server.ts             # Server exports (BFF handler)
├── types.ts              # All TypeScript types
├── auth-client.ts        # Typed fetch wrapper for auth endpoints
├── api-client.ts         # Generic authenticated API client
├── token-manager.ts      # In-memory access token + JWT parsing
├── auth-context.tsx      # AuthProvider, useAuth, useApiClient
├── theme-provider.tsx    # ThemeProvider, ThemeToggle, useTheme
├── server/
│   └── bff-handler.ts    # createBFFRouteHandler()
├── components/ui/        # Vendored UI primitives
├── forms/                # Login, Register, MFA, OAuth forms
├── pages/                # Full-page components
├── guards/               # AuthGuard, GuestGuard
├── oauth/                # OAuth callback handler
├── lib/
│   └── utils.ts          # cn() helper
└── styles/
    └── globals.css       # Tailwind v4 theme + design tokens
```
