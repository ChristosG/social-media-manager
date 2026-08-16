'use client'

import { use } from 'react'
import { ChatArea } from '@/components/chat/chat-area'

export default function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)

  return <ChatArea conversationId={id} />
}
