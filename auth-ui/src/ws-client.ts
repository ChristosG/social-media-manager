export interface WSClientConfig {
  getAccessToken: () => string | null
  refreshToken: () => Promise<string | null>
  baseUrl?: string
}

export interface AuthenticatedWebSocket {
  socket: WebSocket
  close: () => void
}

export function createWSClient(config: WSClientConfig) {
  const { getAccessToken, refreshToken, baseUrl = '' } = config

  async function connect(
    path: string,
    protocols?: string[],
  ): Promise<AuthenticatedWebSocket> {
    const token = getAccessToken()
    const url = buildURL(path, token)

    return new Promise((resolve, reject) => {
      const socket = new WebSocket(url, protocols)

      socket.addEventListener('open', () => {
        resolve({
          socket,
          close: () => socket.close(),
        })
      })

      socket.addEventListener('error', async (event) => {
        // Only attempt refresh on initial connection failure
        if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.CLOSED) {
          try {
            const newToken = await refreshToken()
            if (newToken) {
              const retryUrl = buildURL(path, newToken)
              const retrySocket = new WebSocket(retryUrl, protocols)

              retrySocket.addEventListener('open', () => {
                resolve({
                  socket: retrySocket,
                  close: () => retrySocket.close(),
                })
              })

              retrySocket.addEventListener('error', () => {
                reject(new Error('WebSocket connection failed after token refresh'))
              })
              return
            }
          } catch {
            // refresh failed
          }
          reject(new Error('WebSocket connection failed'))
        }
      })
    })
  }

  function buildURL(path: string, token: string | null): string {
    const base = baseUrl || `${typeof window !== 'undefined' ? window.location.origin : ''}`
    const wsBase = base.replace(/^http/, 'ws')
    const url = new URL(path, wsBase)
    if (token) {
      url.searchParams.set('token', token)
    }
    return url.toString()
  }

  return { connect }
}
