'use client'

import { EmptyState } from '@/components/chat/empty-state'
import { useChatShell } from '@/components/chat-shell'

export default function ChatPage() {
  const { createConversation } = useChatShell()

  return <EmptyState onNewChat={createConversation} />
}
