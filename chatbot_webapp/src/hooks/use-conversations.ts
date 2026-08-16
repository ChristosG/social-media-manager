'use client'
import { useState, useEffect, useCallback, useMemo } from 'react'
import { useApiClient } from '@platform/auth-ui'
import { chatApi, type Conversation } from '@/lib/chat-api'

export function useConversations() {
  const api = useApiClient()
  const [allConversations, setAllConversations] = useState<Conversation[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await chatApi.listConversations(api)
      setAllConversations(data.conversations || [])
    } catch (err) {
      console.error('Failed to load conversations', err)
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { refresh() }, [refresh])

  // Client-side filtering — handles partial words like "coo" matching "cool conversation"
  const conversations = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) return allConversations
    const terms = q.split(/\s+/)
    return allConversations.filter(c => {
      const title = c.title.toLowerCase()
      return terms.every(term => title.includes(term))
    })
  }, [allConversations, searchQuery])

  const create = useCallback(async (title?: string, model?: string) => {
    const data = await chatApi.createConversation(api, title, model || '/models/Qwen3.5-9B')
    setAllConversations(prev => [data.conversation, ...prev])
    return data.conversation
  }, [api])

  const rename = useCallback(async (id: string, title: string) => {
    await chatApi.updateConversation(api, id, { title })
    setAllConversations(prev => prev.map(c => c.id === id ? { ...c, title } : c))
  }, [api])

  const remove = useCallback(async (id: string) => {
    await chatApi.deleteConversation(api, id)
    setAllConversations(prev => prev.filter(c => c.id !== id))
  }, [api])

  const search = useCallback((query: string) => {
    setSearchQuery(query)
  }, [])

  const updateTitle = useCallback((id: string, title: string) => {
    setAllConversations(prev => prev.map(c => c.id === id ? { ...c, title } : c))
  }, [])

  return { conversations, loading, create, rename, remove, search, refresh, updateTitle }
}
