import * as React from 'react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card'
import { ResetPasswordForm } from '../forms/reset-password-form'

interface ResetPasswordPageProps {
  token: string
  onNavigate?: (path: string) => void
  title?: string
  description?: string
}

function ResetPasswordPage({
  token,
  onNavigate,
  title = 'Reset password',
  description = 'Enter your new password',
}: ResetPasswordPageProps) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle style={{ fontSize: 'var(--pau-text-2xl)' }}>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <ResetPasswordForm
            token={token}
            onSuccess={() => onNavigate?.('/login')}
          />
        </CardContent>
        <CardFooter className="justify-center">
          <button
            type="button"
            onClick={() => onNavigate?.('/login')}
            className="text-sm text-primary hover:underline"
          >
            Back to sign in
          </button>
        </CardFooter>
      </Card>
    </div>
  )
}

export { ResetPasswordPage }
