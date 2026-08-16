import * as React from 'react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card'
import { ForgotPasswordForm } from '../forms/forgot-password-form'

interface ForgotPasswordPageProps {
  onNavigate?: (path: string) => void
  title?: string
  description?: string
}

function ForgotPasswordPage({
  onNavigate,
  title = 'Forgot password?',
  description = 'Enter your email to receive a reset link',
}: ForgotPasswordPageProps) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle style={{ fontSize: 'var(--pau-text-2xl)' }}>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <ForgotPasswordForm />
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

export { ForgotPasswordPage }
