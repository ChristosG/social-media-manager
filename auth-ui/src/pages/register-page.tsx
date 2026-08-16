import * as React from 'react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card'
import { Separator } from '../components/ui/separator'
import { RegisterForm } from '../forms/register-form'
import { OAuthButtons } from '../forms/oauth-buttons'
import { GuestGuard } from '../guards/guest-guard'

interface RegisterPageProps {
  onNavigate?: (path: string) => void
  onSuccess?: () => void
  showOAuth?: boolean
  title?: string
  description?: string
}

function RegisterPage({
  onNavigate,
  onSuccess,
  showOAuth = false,
  title = 'Create an account',
  description = 'Get started in seconds',
}: RegisterPageProps) {
  return (
    <GuestGuard onAuthenticated={() => onNavigate?.('/dashboard')}>
      <div className="flex min-h-screen items-center justify-center px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle style={{ fontSize: 'var(--pau-text-2xl)' }}>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <CardContent>
            <RegisterForm onSuccess={onSuccess} />

            {showOAuth && (
              <>
                <div className="relative my-6">
                  <Separator />
                  <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-2 text-xs text-muted-foreground">
                    or
                  </span>
                </div>
                <OAuthButtons label="Sign up with" />
              </>
            )}
          </CardContent>
          <CardFooter className="justify-center">
            <p className="text-sm text-muted-foreground">
              Already have an account?{' '}
              <button
                type="button"
                onClick={() => onNavigate?.('/login')}
                className="text-primary hover:underline"
              >
                Sign in
              </button>
            </p>
          </CardFooter>
        </Card>
      </div>
    </GuestGuard>
  )
}

export { RegisterPage }
