'use client'

import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useConversations } from '@/hooks/use-conversations'
import { ChatStreamProvider } from '@/contexts/chat-stream-context'
import { ConversationSidebar } from './chat/conversation-sidebar'
import { icons } from './icons'
import { PanelLeftClose, PanelLeft } from 'lucide-react'
import { cn } from '@/lib/utils'

const SIDEBAR_KEY = 'chat-sidebar-open'

interface ChatShellContextValue {
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void
  updateTitle: (id: string, title: string) => void
  createConversation: ReturnType<typeof useConversations>['create']
  refreshConversations: () => Promise<void>
  activeId: string | undefined
}

const ChatShellContext = createContext<ChatShellContextValue | null>(null)

export function useChatShell() {
  const ctx = useContext(ChatShellContext)
  if (!ctx) throw new Error('useChatShell must be used within ChatShell')
  return ctx
}

export function ChatShell({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const convState = useConversations()

  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileOverlay, setMobileOverlay] = useState(false)

  const activeId = pathname.match(/^\/chat\/(.+)/)?.[1]

  useEffect(() => {
    const saved = localStorage.getItem(SIDEBAR_KEY)
    if (saved === 'false') setSidebarOpen(false)
  }, [])

  const toggleSidebar = useCallback(() => {
    setSidebarOpen(prev => {
      const next = !prev
      localStorage.setItem(SIDEBAR_KEY, String(next))
      return next
    })
  }, [])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault()
        toggleSidebar()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [toggleSidebar])

  useEffect(() => {
    setMobileOverlay(false)
  }, [pathname])

  const handleNew = () => {
    // Land on the "What should we post?" hero + starters. The conversation is created lazily on first
    // send (EmptyState.handleSend) — so we don't spawn an empty orphan conversation on every click.
    router.push('/chat')
  }

  const handleSelect = (id: string) => {
    router.push(`/chat/${id}`)
  }

  const handleDelete = async (id: string) => {
    await convState.remove(id)
    if (activeId === id) router.push('/chat')
  }

  const updateTitleRef = useRef(convState.updateTitle)
  updateTitleRef.current = convState.updateTitle

  const stableUpdateTitle = useCallback((id: string, title: string) => {
    updateTitleRef.current(id, title)
  }, [])

  const ctx = useMemo<ChatShellContextValue>(() => ({
    sidebarOpen,
    setSidebarOpen,
    toggleSidebar,
    updateTitle: stableUpdateTitle,
    createConversation: convState.create,
    refreshConversations: convState.refresh,
    activeId,
  }), [sidebarOpen, setSidebarOpen, toggleSidebar, stableUpdateTitle, convState.create, convState.refresh, activeId])

  return (
    <ChatShellContext.Provider value={ctx}>
      <div className="flex h-full overflow-hidden">
        {/* Desktop conversation sub-sidebar */}
        <aside
          className={cn(
            'hidden lg:flex flex-col bg-sidebar border-r border-sidebar-border transition-[width] duration-200 overflow-hidden shrink-0',
            sidebarOpen ? 'w-64' : 'w-0',
          )}
        >
          <div className="flex items-center gap-2 h-14 px-3 shrink-0">
            <button
              onClick={handleNew}
              className="flex flex-1 items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:border-primary/40 hover:bg-accent hover:shadow-[0_6px_22px_-12px_var(--pau-glow-primary)] transition-all"
            >
              <icons.plus className="h-4 w-4 text-primary" />
              New chat
            </button>
            <button
              onClick={toggleSidebar}
              className="flex items-center justify-center h-9 w-9 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors shrink-0"
              aria-label="Close panel"
            >
              <PanelLeftClose className="h-5 w-5" />
            </button>
          </div>
          <div className="flex-1 overflow-hidden">
            <ConversationSidebar
              conversations={convState.conversations}
              activeId={activeId}
              loading={convState.loading}
              onNew={handleNew}
              onSelect={handleSelect}
              onRename={convState.rename}
              onDelete={handleDelete}
              onSearch={convState.search}
            />
          </div>
        </aside>

        {/* Mobile overlay for conversation list */}
        {mobileOverlay && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-in fade-in-0" onClick={() => setMobileOverlay(false)} />
            <aside className="absolute inset-y-0 left-0 w-[85vw] max-w-72 bg-sidebar border-r border-sidebar-border flex flex-col shadow-[0_0_80px_-10px_oklch(0_0_0/0.8)] animate-in slide-in-from-left-4 duration-200">
              <div className="flex items-center gap-2 h-14 px-3 shrink-0">
                <button onClick={handleNew} className="flex flex-1 items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:border-primary/40 hover:bg-accent transition-all" aria-label="New chat">
                  <icons.plus className="h-4 w-4 text-primary" />
                  New chat
                </button>
                <button onClick={() => setMobileOverlay(false)} className="flex items-center justify-center h-9 w-9 rounded-lg text-muted-foreground hover:bg-accent transition-colors" aria-label="Close">
                  <icons.x className="h-5 w-5" />
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                <ConversationSidebar
                  conversations={convState.conversations}
                  activeId={activeId}
                  loading={convState.loading}
                  onNew={handleNew}
                  onSelect={(id) => { handleSelect(id); setMobileOverlay(false) }}
                  onRename={convState.rename}
                  onDelete={handleDelete}
                  onSearch={convState.search}
                />
              </div>
            </aside>
          </div>
        )}

        {/* Main chat content */}
        <div className="flex flex-1 flex-col min-w-0 relative">
          {/* Toggle buttons */}
          <div className="absolute top-3 left-3 z-30 flex items-center gap-1">
            {!sidebarOpen && (
              <button
                onClick={toggleSidebar}
                className="hidden lg:flex items-center justify-center h-9 w-9 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                aria-label="Open conversations"
              >
                <PanelLeft className="h-5 w-5" />
              </button>
            )}
            <button
              onClick={() => setMobileOverlay(true)}
              className="flex lg:hidden items-center justify-center h-9 w-9 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
              aria-label="Open conversations"
            >
              <icons.messageSquare className="h-5 w-5" />
            </button>
          </div>
          <ChatStreamProvider>
            {children}
          </ChatStreamProvider>
        </div>
      </div>
    </ChatShellContext.Provider>
  )
}
