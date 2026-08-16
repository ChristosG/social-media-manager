import { defineConfig } from 'tsup'

const isDev = !!process.env.DEV_MODE

export default defineConfig([
  {
    entry: ['src/index.ts'],
    format: ['esm', 'cjs'],
    dts: true,
    sourcemap: true,
    external: ['react', 'react-dom', 'next-themes'],
    banner: {
      js: '"use client";',
    },
    outDir: 'dist',
    clean: !isDev,
  },
  {
    entry: ['src/server.ts'],
    format: ['esm', 'cjs'],
    dts: true,
    sourcemap: true,
    external: ['react', 'react-dom'],
    outDir: 'dist',
  },
])
