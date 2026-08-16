import * as React from 'react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card'
import { Separator } from '../components/ui/separator'
import { LoginForm } from '../forms/login-form'
import { MFAVerifyForm } from '../forms/mfa-verify'
import { OAuthButtons } from '../forms/oauth-buttons'
import { GuestGuard } from '../guards/guest-guard'

interface LoginPageProps {
  onNavigate?: (path: string) => void
  onSuccess?: () => void
  showOAuth?: boolean
  title?: string
  description?: string
}

function LoginPage({
  onNavigate,
  onSuccess,
  showOAuth = false,
  title = 'Welcome back',
  description = 'Sign in to your account',
}: LoginPageProps) {
  const [mfaToken, setMfaToken] = React.useState<string | null>(null)

  return (
    <GuestGuard onAuthenticated={() => onNavigate?.('/dashboard')}>
      <div className="flex min-h-screen items-center justify-center px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle style={{ fontSize: 'var(--pau-text-2xl)' }}>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <CardContent>
            {mfaToken ? (
              <MFAVerifyForm
                mfaToken={mfaToken}
                onSuccess={onSuccess}
                onBack={() => setMfaToken(null)}
              />
            ) : (
              <>
                <LoginForm
                  onMFARequired={setMfaToken}
                  onSuccess={onSuccess}
                  onNavigate={onNavigate}
                />

                {showOAuth && (
                  <>
                    <div className="relative my-6">
                      <Separator />
                      <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-2 text-xs text-muted-foreground">
                        or
                      </span>
                    </div>
                    <OAuthButtons />
                  </>
                )}
              </>
            )}
          </CardContent>
          <CardFooter className="justify-center">
            <p className="text-sm text-muted-foreground">
              Don&apos;t have an account?{' '}
              <button
                type="button"
                onClick={() => onNavigate?.('/register')}
                className="text-primary hover:underline"
              >
                Sign up
              </button>
            </p>
          </CardFooter>
        </Card>
      </div>
    </GuestGuard>
  )
}

export { LoginPage }
