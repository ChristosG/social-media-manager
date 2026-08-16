'use client'

import * as React from 'react'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import { cn } from '@/lib/utils'

const Tabs = TabsPrimitive.Root

const TabsList = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => {
  // Keep the ACTIVE tab scrolled into view, and show a thin scrollbar when the bar overflows. On a phone
  // the Workspace bar has 7 tabs that overflow horizontally; previously the scrollbar was hidden with no
  // affordance, so 'Your socials' + later tabs were invisible/unreachable. Auto-scroll fixes deep-links
  // (e.g. ?tab=campaigns) and the thin scrollbar makes the overflow discoverable.
  const localRef = React.useRef<HTMLDivElement | null>(null)
  const setRef = React.useCallback((node: HTMLDivElement | null) => {
    localRef.current = node
    if (typeof ref === 'function') ref(node)
    else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = node
  }, [ref])
  React.useEffect(() => {
    const el = localRef.current
    if (!el) return
    const scrollActive = () => {
      const active = el.querySelector('[data-state="active"]') as HTMLElement | null
      active?.scrollIntoView({ inline: 'center', block: 'nearest' })
    }
    scrollActive()
    const obs = new MutationObserver(scrollActive)
    obs.observe(el, { attributes: true, attributeFilter: ['data-state'], subtree: true })
    return () => obs.disconnect()
  }, [])
  return (
    <TabsPrimitive.List
      ref={setRef}
      className={cn(
        'inline-flex max-w-full items-center justify-center gap-1 overflow-x-auto scroll-smooth rounded-xl border border-border bg-muted/40 p-1 text-muted-foreground',
        '[scrollbar-width:thin] [scrollbar-color:var(--pau-border)_transparent] [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border/70',
        className,
      )}
      {...props}
    />
  )
})
TabsList.displayName = TabsPrimitive.List.displayName

const TabsTrigger = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
      'hover:text-foreground data-[state=active]:bg-primary/15 data-[state=active]:text-primary data-[state=active]:shadow-[0_0_0_1px_var(--pau-border)]',
      '[&_svg]:size-4 [&_svg]:shrink-0',
      className,
    )}
    {...props}
  />
))
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName

const TabsContent = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn('mt-4 ring-offset-background focus-visible:outline-none', className)}
    {...props}
  />
))
TabsContent.displayName = TabsPrimitive.Content.displayName

export { Tabs, TabsList, TabsTrigger, TabsContent }
