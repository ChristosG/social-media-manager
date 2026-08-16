import * as React from 'react'
import { useAuth } from '../auth-context'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'

interface MFAVerifyFormProps {
  mfaToken: string
  onSuccess?: () => void
  onBack?: () => void
}

function MFAVerifyForm({ mfaToken, onSuccess, onBack }: MFAVerifyFormProps) {
  const { completeMFALogin } = useAuth()
  const [code, setCode] = React.useState('')
  const [error, setError] = React.useState('')
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      const result = await completeMFALogin(mfaToken, code)

      if (result.success) {
        onSuccess?.()
      } else {
        setError(result.error || 'Invalid code')
      }
    } catch {
      setError('An unexpected error occurred')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="mfa-code">Authentication code</Label>
        <Input
          id="mfa-code"
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={6}
          placeholder="000000"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
          required
          autoComplete="one-time-code"
          autoFocus
          className="text-center text-lg tracking-widest"
        />
        <p className="text-xs text-muted-foreground">
          Enter the 6-digit code from your authenticator app
        </p>
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting || code.length !== 6}>
        {isSubmitting ? 'Verifying...' : 'Verify'}
      </Button>

      {onBack && (
        <Button type="button" variant="ghost" className="w-full" onClick={onBack}>
          Back to login
        </Button>
      )}
    </form>
  )
}

export { MFAVerifyForm }
