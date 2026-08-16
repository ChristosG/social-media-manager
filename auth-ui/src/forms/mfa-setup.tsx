import * as React from 'react'
import QRCode from 'qrcode'
import { useAuth } from '../auth-context'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import type { EnableMFAResponse } from '../types'

interface MFASetupProps {
  onComplete?: () => void
}

function QRCodeImage({ value }: { value: string }) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null)

  React.useEffect(() => {
    if (canvasRef.current) {
      QRCode.toCanvas(canvasRef.current, value, {
        width: 192,
        margin: 2,
        color: { dark: '#000000', light: '#ffffff' },
      })
    }
  }, [value])

  return <canvas ref={canvasRef} className="rounded-lg border" />
}

function MFASetup({ onComplete }: MFASetupProps) {
  const { enableMFA, disableMFA, user } = useAuth()
  const [setupData, setSetupData] = React.useState<EnableMFAResponse | null>(null)
  const [error, setError] = React.useState('')
  const [isLoading, setIsLoading] = React.useState(false)
  const [disableCode, setDisableCode] = React.useState('')
  const [showDisable, setShowDisable] = React.useState(false)

  const handleEnable = async () => {
    setError('')
    setIsLoading(true)
    try {
      const data = await enableMFA()
      setSetupData(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to enable MFA')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDisable = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      const result = await disableMFA(disableCode)
      if (result.success) {
        setShowDisable(false)
        setDisableCode('')
        onComplete?.()
      } else {
        setError(result.error || 'Failed to disable MFA')
      }
    } catch {
      setError('An unexpected error occurred')
    } finally {
      setIsLoading(false)
    }
  }

  if (user?.mfa_enabled && !showDisable) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg bg-primary/10 p-4">
          <p className="text-sm font-medium">Two-factor authentication is enabled</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Your account is protected with an authenticator app.
          </p>
        </div>
        <Button variant="destructive" onClick={() => setShowDisable(true)} className="w-full">
          Disable two-factor authentication
        </Button>
      </div>
    )
  }

  if (showDisable) {
    return (
      <form onSubmit={handleDisable} className="space-y-4">
        {error && (
          <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="space-y-2">
          <Label htmlFor="disable-mfa-code">Enter authenticator code to disable</Label>
          <Input
            id="disable-mfa-code"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            placeholder="000000"
            value={disableCode}
            onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, ''))}
            required
            className="text-center text-lg tracking-widest"
          />
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" className="flex-1" onClick={() => setShowDisable(false)}>
            Cancel
          </Button>
          <Button type="submit" variant="destructive" className="flex-1" disabled={isLoading || disableCode.length !== 6}>
            {isLoading ? 'Disabling...' : 'Disable'}
          </Button>
        </div>
      </form>
    )
  }

  if (setupData) {
    return (
      <div className="space-y-4">
        <div className="space-y-2 text-center">
          <p className="text-sm font-medium">Scan this QR code with your authenticator app</p>
          <div className="flex justify-center p-4">
            <QRCodeImage value={setupData.qr_code_url} />
          </div>
          <p className="text-xs text-muted-foreground">
            Use Google Authenticator, Authy, or any TOTP app
          </p>
          <details className="text-left">
            <summary className="cursor-pointer text-xs text-muted-foreground">
              Can&apos;t scan? Enter this key manually
            </summary>
            <code className="mt-2 block break-all rounded bg-muted p-2 text-xs">
              {setupData.secret}
            </code>
          </details>
        </div>

        {setupData.recovery_codes && setupData.recovery_codes.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Recovery codes</p>
            <p className="text-xs text-muted-foreground">
              Save these codes in a safe place. Each code can only be used once.
            </p>
            <div className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-3">
              {setupData.recovery_codes.map((code) => (
                <code key={code} className="text-xs">
                  {code}
                </code>
              ))}
            </div>
          </div>
        )}

        <Button onClick={() => { setSetupData(null); onComplete?.() }} className="w-full">
          Done
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
      <div className="rounded-lg border p-4">
        <p className="text-sm font-medium">Two-factor authentication</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Add an extra layer of security to your account by requiring a code from your authenticator app.
        </p>
      </div>
      <Button onClick={handleEnable} className="w-full" disabled={isLoading}>
        {isLoading ? 'Setting up...' : 'Enable two-factor authentication'}
      </Button>
    </div>
  )
}

export { MFASetup }
