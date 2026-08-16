import type { ApiClient, ApiClientConfig } from './types'

class ApiRequestError extends Error {
  status: number
  data: unknown
  constructor(message: string, status: number, data?: unknown) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.data = data
  }
}

export function createApiClient(config: ApiClientConfig): ApiClient {
  const { getAccessToken, refreshToken, baseUrl = '' } = config

  let refreshPromise: Promise<string | null> | null = null

  async function doRefresh(): Promise<string | null> {
    if (!refreshPromise) {
      refreshPromise = refreshToken().finally(() => {
        refreshPromise = null
      })
    }
    return refreshPromise
  }

  async function request<T>(
    path: string,
    options: RequestInit = {},
    isRetry = false,
  ): Promise<T> {
    const token = getAccessToken()
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
    const headers: Record<string, string> = {
      // Let the browser set Content-Type (with boundary) for FormData
      ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers as Record<string, string> || {}),
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const url = `${baseUrl}${path}`
    const res = await fetch(url, { ...options, headers })

    if (res.status === 401 && !isRetry) {
      const newToken = await doRefresh()
      if (newToken) {
        return request<T>(path, options, true)
      }
    }

    if (!res.ok) {
      let data: unknown
      try {
        data = await res.json()
      } catch {
        data = null
      }
      const msg = (data && typeof data === 'object' && 'message' in data)
        ? String((data as Record<string, unknown>).message)
        : `Request failed with status ${res.status}`
      throw new ApiRequestError(msg, res.status, data)
    }

    if (res.status === 204) return undefined as T

    return res.json() as Promise<T>
  }

  return {
    get: <T = unknown>(path: string, options?: RequestInit) =>
      request<T>(path, { ...options, method: 'GET' }),

    post: <T = unknown>(path: string, body?: unknown, options?: RequestInit) =>
      request<T>(path, {
        ...options,
        method: 'POST',
        body: body
          ? (typeof FormData !== 'undefined' && body instanceof FormData ? body : JSON.stringify(body))
          : undefined,
      }),

    put: <T = unknown>(path: string, body?: unknown, options?: RequestInit) =>
      request<T>(path, {
        ...options,
        method: 'PUT',
        body: body
          ? (typeof FormData !== 'undefined' && body instanceof FormData ? body : JSON.stringify(body))
          : undefined,
      }),

    patch: <T = unknown>(path: string, body?: unknown, options?: RequestInit) =>
      request<T>(path, {
        ...options,
        method: 'PATCH',
        body: body
          ? (typeof FormData !== 'undefined' && body instanceof FormData ? body : JSON.stringify(body))
          : undefined,
      }),

    delete: <T = unknown>(path: string, options?: RequestInit) =>
      request<T>(path, { ...options, method: 'DELETE' }),
  }
}

export { ApiRequestError }
