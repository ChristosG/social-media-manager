import type { IconName } from '@/components/icons'

export interface NavItem {
  label: string
  href: string
  icon: IconName
}

export const navigation: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: 'home' },
  { label: 'Settings', href: '/settings', icon: 'settings' },
]
