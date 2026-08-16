'use client'

import { useState, useRef, useEffect } from 'react'
import { useApiClient } from '@platform/auth-ui'
import { chatApi } from '@/lib/chat-api'
import { ModelSelector } from './model-selector'

interface ChatHeaderProps {
  conversationId: string
  title: string
  model?: string
  onTitleChange?: (title: string) => void
  onModelChange?: (model: string) => void
}

export function ChatHeader({ conversationId, title, model, onTitleChange, onModelChange }: ChatHeaderProps) {
  const api = useApiClient()
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(title)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setEditTitle(title)
  }, [title])

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const handleSubmit = async () => {
    const trimmed = editTitle.trim()
    if (trimmed && trimmed !== title) {
      await chatApi.updateConversation(api, conversationId, { title: trimmed })
      onTitleChange?.(trimmed)
    } else {
      setEditTitle(title)
    }
    setEditing(false)
  }

  const handleModelChange = async (newModel: string) => {
    await chatApi.updateConversation(api, conversationId, { title, model: newModel })
    onModelChange?.(newModel)
  }

  return (
    <div className="flex items-center justify-center h-14 pl-12 lg:pl-4 pr-4 border-b border-border/60 bg-background/70 backdrop-blur-sm flex-shrink-0 relative z-20">
      {/* Title (center) */}
      <div className="flex items-center gap-2 max-w-40 sm:max-w-md">
        {editing ? (
          <input
            ref={inputRef}
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onBlur={handleSubmit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSubmit()
              if (e.key === 'Escape') { setEditTitle(title); setEditing(false) }
            }}
            className="bg-transparent border-none outline-none text-sm font-medium text-center text-foreground min-w-0 w-64"
          />
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="text-sm font-medium text-foreground hover:text-muted-foreground transition-colors truncate max-w-36 sm:max-w-64"
            title="Click to edit title"
          >
            {title}
          </button>
        )}
      </div>

      {/* Model selector (right) */}
      <div className="absolute right-4">
        <ModelSelector value={model} onChange={handleModelChange} />
      </div>
    </div>
  )
}
