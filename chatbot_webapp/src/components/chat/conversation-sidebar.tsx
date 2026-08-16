'use client'
import { useState } from 'react'
import { icons } from '@/components/icons'
import type { Conversation } from '@/lib/chat-api'
import { ConversationItem } from './conversation-item'

interface ConversationSidebarProps {
  conversations: Conversation[]
  activeId?: string
  loading: boolean
  onNew: () => void
  onSelect: (id: string) => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
  onSearch: (query: string) => void
}

export function ConversationSidebar({
  conversations,
  activeId,
  loading,
  onSelect,
  onRename,
  onDelete,
  onSearch,
}: ConversationSidebarProps) {
  const [searchQuery, setSearchQuery] = useState('')

  const handleSearch = (value: string) => {
    setSearchQuery(value)
    onSearch(value)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="p-2">
        <div className="relative">
          <icons.search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="w-full rounded-lg border border-input bg-background/60 py-2 pl-8 pr-3 text-sm shadow-[inset_0_1px_2px_0_oklch(0_0_0/0.25)] placeholder:text-muted-foreground focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
          />
        </div>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <icons.loader className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            {searchQuery ? 'No conversations found' : 'No conversations yet'}
          </div>
        ) : (
          <div className="space-y-0.5 p-1">
            {conversations.map((conv) => (
              <ConversationItem
                key={conv.id}
                conversation={conv}
                isActive={conv.id === activeId}
                onSelect={() => onSelect(conv.id)}
                onRename={(title) => onRename(conv.id, title)}
                onDelete={() => onDelete(conv.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
