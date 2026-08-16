import type { BFFConfig } from '../types'

interface RouteContext {
  params: Promise<{ path?: string[] }>
}

function createCookieHeader(
  name: string,
  value: string,
  maxAge: number,
  secure: boolean,
): string {
  const parts = [
    `${name}=${value}`,
    `Path=/`,
    `HttpOnly`,
    `SameSite=Strict`,
    `Max-Age=${maxAge}`,
  ]
  if (secure) parts.push('Secure')
  return parts.join('; ')
}

function clearCookieHeader(name: string, secure: boolean): string {
  const parts = [
    `${name}=`,
    `Path=/`,
    `HttpOnly`,
    `SameSite=Strict`,
    `Max-Age=0`,
  ]
  if (secure) parts.push('Secure')
  return parts.join('; ')
}

function getCookieValue(cookieHeader: string | null, name: string): string | null {
  if (!cookieHeader) return null
  const match = cookieHeader.match(new RegExp(`(?:^|;)\\s*${name}=([^;]+)`))
  return match ? match[1] : null
}

export function createBFFRouteHandler(config: BFFConfig) {
  const {
    gatewayUrl,
    cookieName = 'platform_refresh_token',
    cookieMaxAge = 7 * 24 * 60 * 60, // 7 days
    secureCookies = process.env.NODE_ENV === 'production',
  } = config

  async function handleAuth(
    req: Request,
    context: RouteContext,
  ): Promise<Response> {
    const { path: pathSegments = [] } = await context.params
    const authPath = pathSegments.join('/')
    const gatewayPath = `/api/v1/auth/${authPath}`

    const url = new URL(req.url)
    const queryString = url.search

    const isTokenEndpoint = ['login', 'register', 'mfa/verify', 'tenants/create'].includes(authPath)
    const isRefreshEndpoint = authPath === 'refresh'
    const isLogoutEndpoint = authPath === 'logout'
    const isOAuthCallback = authPath.match(/^oauth\/[^/]+\/callback$/)

    // Build headers to forward
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    // Forward authorization header
    const authHeader = req.headers.get('authorization')
    if (authHeader) {
      headers['Authorization'] = authHeader
    }

    // For refresh, try cookie first, then fall back to body (ephemeral mode)
    if (isRefreshEndpoint) {
      const cookieRefreshToken = getCookieValue(
        req.headers.get('cookie'),
        cookieName,
      )

      let bodyRefreshToken: string | null = null
      if (!cookieRefreshToken) {
        try {
          const parsed = await req.json() as Record<string, unknown>
          bodyRefreshToken = (parsed.refresh_token as string) || null
        } catch {
          // no body
        }
      }

      const refreshToken = cookieRefreshToken || bodyRefreshToken

      if (!refreshToken) {
        // Return 200 with empty body instead of 401 to avoid noisy
        // console errors on initial page load when no session exists.
        return new Response(
          JSON.stringify({}),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }

      const isEphemeral = !cookieRefreshToken && !!bodyRefreshToken

      const gatewayRes = await fetch(`${gatewayUrl}${gatewayPath}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ refresh_token: refreshToken }),
      })

      const data = await gatewayRes.json()

      if (!gatewayRes.ok) {
        const responseHeaders = new Headers({ 'Content-Type': 'application/json' })
        if (cookieRefreshToken) {
          responseHeaders.set(
            'Set-Cookie',
            clearCookieHeader(cookieName, secureCookies),
          )
        }
        return new Response(JSON.stringify(data), {
          status: gatewayRes.status,
          headers: responseHeaders,
        })
      }

      const responseHeaders = new Headers({ 'Content-Type': 'application/json' })

      if (isEphemeral) {
        // Ephemeral mode: return both tokens in body, no cookie
        return new Response(
          JSON.stringify({
            access_token: data.access_token,
            refresh_token: data.refresh_token,
            ephemeral: true,
          }),
          { status: 200, headers: responseHeaders },
        )
      }

      // Persistent mode: set cookie, return only access token
      if (data.refresh_token) {
        responseHeaders.set(
          'Set-Cookie',
          createCookieHeader(cookieName, data.refresh_token, cookieMaxAge, secureCookies),
        )
      }

      return new Response(
        JSON.stringify({ access_token: data.access_token }),
        { status: 200, headers: responseHeaders },
      )
    }

    // For logout, include refresh token from cookie
    if (isLogoutEndpoint) {
      const cookieRefreshToken = getCookieValue(
        req.headers.get('cookie'),
        cookieName,
      )

      let bodyRefreshToken: string | null = null
      try {
        const cloned = req.clone()
        const parsed = await cloned.json() as Record<string, unknown>
        bodyRefreshToken = (parsed.refresh_token as string) || null
      } catch {
        // no body
      }

      const refreshToken = cookieRefreshToken || bodyRefreshToken
      const body = refreshToken
        ? JSON.stringify({ refresh_token: refreshToken })
        : '{}'

      const gatewayRes = await fetch(`${gatewayUrl}${gatewayPath}`, {
        method: 'POST',
        headers,
        body,
      })

      const data = await gatewayRes.json().catch(() => ({ message: 'Logged out' }))

      const responseHeaders = new Headers({ 'Content-Type': 'application/json' })
      responseHeaders.set(
        'Set-Cookie',
        clearCookieHeader(cookieName, secureCookies),
      )

      return new Response(JSON.stringify(data), {
        status: gatewayRes.ok ? 200 : gatewayRes.status,
        headers: responseHeaders,
      })
    }

    // For OAuth callbacks (GET with query params)
    if (isOAuthCallback) {
      const gatewayRes = await fetch(`${gatewayUrl}${gatewayPath}${queryString}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      })

      const data = await gatewayRes.json()

      if (!gatewayRes.ok) {
        return new Response(JSON.stringify(data), {
          status: gatewayRes.status,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      const responseHeaders = new Headers({ 'Content-Type': 'application/json' })
      if (data.refresh_token) {
        responseHeaders.set(
          'Set-Cookie',
          createCookieHeader(cookieName, data.refresh_token, cookieMaxAge, secureCookies),
        )
      }

      const { refresh_token: _, ...clientData } = data
      return new Response(JSON.stringify(clientData), {
        status: 200,
        headers: responseHeaders,
      })
    }

    // For login/register/MFA verify — intercept tokens
    if (isTokenEndpoint && req.method === 'POST') {
      // "0" = ephemeral (no cookie), "1"/absent = persistent (cookie)
      const rememberMe = req.headers.get('x-remember-me')
      const isEphemeral = rememberMe === '0'

      let body: string
      try {
        const parsed = await req.json()
        body = JSON.stringify(parsed)
      } catch {
        body = '{}'
      }

      const gatewayRes = await fetch(`${gatewayUrl}${gatewayPath}`, {
        method: 'POST',
        headers,
        body,
      })

      const data = await gatewayRes.json()

      if (!gatewayRes.ok) {
        return new Response(JSON.stringify(data), {
          status: gatewayRes.status,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      const responseHeaders = new Headers({ 'Content-Type': 'application/json' })

      if (isEphemeral) {
        // Ephemeral mode: return both tokens in body, no cookie set
        // Client keeps refresh token in memory (tab-scoped)
        return new Response(JSON.stringify(data), {
          status: 200,
          headers: responseHeaders,
        })
      }

      // Persistent mode: set httpOnly cookie, strip refresh_token from body
      if (data.refresh_token) {
        responseHeaders.set(
          'Set-Cookie',
          createCookieHeader(cookieName, data.refresh_token, cookieMaxAge, secureCookies),
        )
      }

      const { refresh_token: _, ...clientData } = data
      return new Response(JSON.stringify(clientData), {
        status: 200,
        headers: responseHeaders,
      })
    }

    // Generic proxy for all other endpoints (GET /me, POST /forgot-password, etc.)
    const fetchOptions: RequestInit = {
      method: req.method,
      headers,
    }

    if (req.method !== 'GET' && req.method !== 'HEAD') {
      try {
        const body = await req.text()
        if (body) fetchOptions.body = body
      } catch {
        // no body
      }
    }

    const targetUrl = `${gatewayUrl}${gatewayPath}${queryString}`
    const gatewayRes = await fetch(targetUrl, fetchOptions)

    const responseData = await gatewayRes.text()
    return new Response(responseData, {
      status: gatewayRes.status,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  return {
    GET: (req: Request, ctx: RouteContext) => handleAuth(req, ctx),
    POST: (req: Request, ctx: RouteContext) => handleAuth(req, ctx),
    PUT: (req: Request, ctx: RouteContext) => handleAuth(req, ctx),
    DELETE: (req: Request, ctx: RouteContext) => handleAuth(req, ctx),
  }
}
