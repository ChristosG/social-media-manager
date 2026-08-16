import { createBFFRouteHandler } from '@platform/auth-ui/server'

export const { GET, POST, PUT, DELETE } = createBFFRouteHandler({
  gatewayUrl: process.env.GATEWAY_URL || 'http://localhost:8080',
})
