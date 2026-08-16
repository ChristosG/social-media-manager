'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'
import { Check } from 'lucide-react'

interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, id, ...props }, ref) => (
    <label
      htmlFor={id}
      className="flex cursor-pointer items-center gap-2 select-none"
    >
      <span className="relative flex h-4 w-4 shrink-0">
        <input
          ref={ref}
          id={id}
          type="checkbox"
          className={cn('peer sr-only', className)}
          {...props}
        />
        <span
          className={cn(
            'h-4 w-4 rounded border border-input bg-background/60 transition-colors',
            'peer-checked:border-primary peer-checked:bg-primary',
            'peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-1',
            'peer-disabled:opacity-50 peer-disabled:cursor-not-allowed',
          )}
        />
        <Check
          className="pointer-events-none absolute inset-0 m-auto h-3 w-3 text-primary-foreground opacity-0 peer-checked:opacity-100 transition-opacity"
          strokeWidth={3}
        />
      </span>
      {label && <span className="text-sm text-foreground">{label}</span>}
    </label>
  )
)
Checkbox.displayName = 'Checkbox'

export { Checkbox }
