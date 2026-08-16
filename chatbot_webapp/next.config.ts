import type { NextConfig } from 'next'
import { resolve } from 'path'

const nextConfig: NextConfig = {
  output: 'standalone',
  transpilePackages: ['@platform/auth-ui'],
  turbopack: {
    root: resolve(__dirname),
  },
}

export default nextConfig
