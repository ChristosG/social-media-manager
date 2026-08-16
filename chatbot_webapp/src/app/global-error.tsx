'use client'

/**
 * Last-resort boundary: catches errors thrown in the ROOT layout itself (before the (app) error boundary can
 * mount). It replaces the whole document, so the global stylesheet/theme tokens aren't available — hence the
 * inline styles tuned to the dark Sanctuary palette. Kept intentionally tiny; its only job is to never show
 * Next.js's stark unstyled default and to offer a one-click reload.
 */
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1rem',
          background: '#0c0a09',
          color: '#e7e5e4',
          fontFamily: 'ui-sans-serif, system-ui, sans-serif',
          textAlign: 'center',
          padding: '2rem',
        }}
      >
        <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>This page couldn’t load</h1>
        <p style={{ fontSize: '0.9rem', color: '#a8a29e', maxWidth: '24rem', margin: 0 }}>
          Something interrupted the load — usually temporary. Try again.
        </p>
        <button
          onClick={() => reset()}
          style={{
            marginTop: '0.5rem',
            borderRadius: '0.5rem',
            border: 'none',
            background: '#f97316',
            color: '#1c1917',
            padding: '0.6rem 1.1rem',
            fontSize: '0.9rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Reload
        </button>
      </body>
    </html>
  )
}
