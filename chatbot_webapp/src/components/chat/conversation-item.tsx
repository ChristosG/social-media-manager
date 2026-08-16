'use client'
import { useState, useRef, useEffect } from 'react'
import { icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import type { Conversation } from '@/lib/chat-api'

interface ConversationItemProps {
  conversation: Conversation
  isActive: boolean
  onSelect: () => void
  onRename: (title: string) => void
  onDelete: () => void
}

export function ConversationItem({
  conversation,
  isActive,
  onSelect,
  onRename,
  onDelete,
}: ConversationItemProps) {
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [title, setTitle] = useState(conversation.title)
  const inputRef = useRef<HTMLInputElement>(null)

  // Sync title when prop updates (e.g. auto-title from server)
  useEffect(() => {
    if (!editing) setTitle(conversation.title)
  }, [conversation.title, editing])

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const handleSubmit = () => {
    if (title.trim() && title !== conversation.title) {
      onRename(title.trim())
    } else {
      setTitle(conversation.title)
    }
    setEditing(false)
  }

  return (
    <div
      className={cn(
        'group relative flex items-center gap-2 rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors',
        isActive
          ? 'bg-primary/12 text-foreground'
          : 'text-muted-foreground hover:bg-accent/70 hover:text-foreground',
      )}
      onClick={() => !editing && onSelect()}
    >
      {isActive && (
        <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-primary" />
      )}
      <icons.messageSquare className={cn('h-4 w-4 flex-shrink-0', isActive && 'text-primary')} />

      {editing ? (
        <input
          ref={inputRef}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={handleSubmit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSubmit()
            if (e.key === 'Escape') { setTitle(conversation.title); setEditing(false) }
          }}
          className="flex-1 bg-transparent border-none outline-none text-sm min-w-0"
          onClick={(e) => e.stopPropagation()}
        />
      ) : (
        <span className="flex-1 truncate">{conversation.title}</span>
      )}

      {!editing && (
        <div className={cn(
          'flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity',
          isActive && 'opacity-100',
        )}>
          <button
            onClick={(e) => { e.stopPropagation(); setEditing(true) }}
            className="rounded p-1 hover:bg-black/10 dark:hover:bg-white/10"
            aria-label="Rename"
          >
            <icons.pencil className="h-3 w-3" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); setConfirmDelete(true) }}
            className="rounded p-1 hover:bg-black/10 dark:hover:bg-white/10 text-destructive"
            aria-label="Delete"
          >
            <icons.trash className="h-3 w-3" />
          </button>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title="Delete conversation"
        description="Delete this conversation? This cannot be undone."
        confirmLabel="Delete"
        destructive
        onConfirm={() => { setConfirmDelete(false); onDelete() }}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  )
}
