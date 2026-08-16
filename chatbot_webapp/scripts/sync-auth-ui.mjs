/**
 * Replaces bun's symlinked @platform/auth-ui with a real copy.
 * Turbopack cannot follow bun's file: symlinks, so we copy the dist
 * files after install. This runs automatically via postinstall.
 *
 * Skips gracefully in Docker builds (where ../auth-ui doesn't exist)
 * since the Dockerfile handles the copy separately.
 */
import { cpSync, rmSync, mkdirSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')
const authUiSrc = resolve(root, '../auth-ui')
const authUiDest = resolve(root, 'node_modules/@platform/auth-ui')

if (!existsSync(authUiSrc) || !existsSync(resolve(authUiSrc, 'dist/index.js'))) {
  console.log('[sync-auth-ui] auth-ui not available, skipping (expected in Docker)')
  process.exit(0)
}

rmSync(authUiDest, { recursive: true, force: true })
mkdirSync(authUiDest, { recursive: true })
cpSync(resolve(authUiSrc, 'package.json'), resolve(authUiDest, 'package.json'))
cpSync(resolve(authUiSrc, 'dist'), resolve(authUiDest, 'dist'), { recursive: true })

console.log('[sync-auth-ui] copied auth-ui dist to node_modules')
