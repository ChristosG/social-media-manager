'use client'
import { useEffect } from 'react'

interface Shortcuts {
  onToggleSidebar?: () => void
  onNewChat?: () => void
  onFocusSearch?: () => void
  onCloseMobile?: () => void
  onFocusInput?: () => void
}

export function useKeyboardShortcuts(shortcuts: Shortcuts) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey

      // Cmd+B → toggle sidebar (handled in ChatShell already)
      // Cmd+N → new conversation
      if (mod && e.key === 'n') {
        e.preventDefault()
        shortcuts.onNewChat?.()
        return
      }

      // Cmd+K → focus search
      if (mod && e.key === 'k') {
        e.preventDefault()
        shortcuts.onFocusSearch?.()
        return
      }

      // Escape → close mobile sidebar
      if (e.key === 'Escape') {
        shortcuts.onCloseMobile?.()
        return
      }

      // / → focus input (only when not in input/textarea)
      if (e.key === '/' && !isInputFocused()) {
        e.preventDefault()
        shortcuts.onFocusInput?.()
        return
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [shortcuts])
}

function isInputFocused() {
  const active = document.activeElement
  return active instanceof HTMLInputElement ||
    active instanceof HTMLTextAreaElement ||
    active?.getAttribute('contenteditable') === 'true'
}
