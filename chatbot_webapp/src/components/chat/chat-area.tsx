'use client'
import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { Megaphone, ArrowRight, WandSparkles, Check, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useApiClient } from '@platform/auth-ui'
import { chatApi } from '@/lib/chat-api'
import { ChatHeader } from './chat-header'
import { MessageList } from './message-list'
import { ChatInput } from './chat-input'
import { DropZone } from './drop-zone'
import { FollowUpChips } from './follow-up-chips'
import { PublishPreviewDialog } from '@/components/publish/publish-preview-dialog'
import { useChat } from '@/hooks/use-chat'
import { useConversationDraft } from '@/hooks/use-publishing'
import { useUpdateCampaignPost } from '@/hooks/use-studio'
import { useFileAttachments } from '@/hooks/use-file-attachments'
import { useChatShell } from '@/components/chat-shell'

interface ChatAreaProps {
  conversationId: string
}

export function ChatArea({ conversationId }: ChatAreaProps) {
  const api = useApiClient()
  const { updateTitle: shellUpdateTitle } = useChatShell()
  const attachments = useFileAttachments()

  const [title, setTitle] = useState('New Conversation')
  const [model, setModel] = useState<string | undefined>()

  const handleTitleUpdate = useCallback((newTitle: string) => {
    setTitle(newTitle)
    shellUpdateTitle(conversationId, newTitle)
  }, [shellUpdateTitle, conversationId])

  const {
    messages,
    loading,
    streaming,
    streamingContent,
    streamingReasoning,
    statusMessage,
    followups,
    publishProposal,
    plannedCampaign,
    activePostId,
    activePostCaption,
    proposedCaption,
    resumePublish,
    loadMessages,
    sendMessage,
    retryMessage,
    stopStreaming,
  } = useChat(conversationId, { onTitleUpdate: handleTitleUpdate })

  // Persistent "Apply to post" for a draft opened via "Refine in chat": the per-message button scrolls out of
  // reach after follow-up turns (generate an image, etc.), so surface a sticky bar whenever the latest proposed
  // caption hasn't been written to the post yet — it stays until applied. (Images auto-attach on generation,
  // so this only commits the caption.) Staged caption: the live proposal if present, else the PERSISTED
  // conversation draft (so the bar survives a reload, when the client-only proposal is gone).
  const { data: draftData } = useConversationDraft(conversationId)
  const updatePost = useUpdateCampaignPost()
  const [appliedCaption, setAppliedCaption] = useState('')
  useEffect(() => { setAppliedCaption('') }, [conversationId])
  const stagedCaption = (proposedCaption || draftData?.draft?.caption || '').trim()
  const pendingApply = !!activePostId && !!stagedCaption
    && stagedCaption !== (activePostCaption || '').trim()
    && stagedCaption !== appliedCaption.trim()
  const onApplyToPost = useCallback(async () => {
    if (!activePostId || !stagedCaption) return
    try {
      await updatePost.mutateAsync({ id: activePostId, content: stagedCaption })
      setAppliedCaption(stagedCaption)
      toast.success('Caption saved to the post')
    } catch { toast.error('Could not apply — please try again') }
  }, [activePostId, stagedCaption, updatePost])

  // Load conversation details (single API call) and check for pending message
  useEffect(() => {
    loadMessages().then(data => {
      if (data) {
        setTitle(data.conversation.title)
        setModel(data.conversation.model || undefined)
      }
    })

    // Check for pending message from EmptyState
    try {
      const raw = sessionStorage.getItem('pending-message')
      if (raw) {
        const pending = JSON.parse(raw)
        if (pending.conversationId === conversationId) {
          sessionStorage.removeItem('pending-message')
          sendMessage(
            pending.content,
            Array.isArray(pending.attachmentIds) && pending.attachmentIds.length
              ? pending.attachmentIds
              : undefined,
            pending.sendOptions || undefined,
          )
        }
      }
    } catch {}
  }, [loadMessages, conversationId, sendMessage])

  const handleTitleChange = (newTitle: string) => {
    setTitle(newTitle)
    shellUpdateTitle(conversationId, newTitle)
  }

  // Upload files immediately when added (processing starts while user types)
  const handleAddFiles = useCallback((newFiles: File[]) => {
    attachments.addFiles(newFiles, (file) => chatApi.uploadAttachment(api, file))
  }, [api, attachments])

  const handleSend = useCallback(async (content: string, opts?: { groundSources?: boolean; reasoning?: boolean; webSearch?: boolean }) => {
    let attachmentIds: string[] | undefined
    if (attachments.hasFiles) {
      try {
        attachmentIds = await attachments.waitForUploads()
      } catch {
        // Upload failed — send message without attachments
      }
    }
    attachments.clearAll()
    sendMessage(content, attachmentIds?.length ? attachmentIds : undefined, opts)
  }, [attachments, sendMessage])

  return (
    <div className="flex flex-col h-full">
      <ChatHeader
        conversationId={conversationId}
        title={title}
        model={model}
        onTitleChange={handleTitleChange}
        onModelChange={setModel}
      />

      <DropZone onDrop={handleAddFiles} disabled={streaming}>
        <MessageList
          messages={messages}
          loading={loading}
          streamingContent={streaming ? streamingContent : undefined}
          streamingReasoning={streaming ? streamingReasoning : undefined}
          statusMessage={streaming ? statusMessage : undefined}
          onRetry={retryMessage}
        />
      </DropZone>

      {!streaming && plannedCampaign && (
        <div className="px-4 pb-1.5 sm:px-6">
          <Link
            href={`/workspace?tab=campaigns&c=${plannedCampaign.id}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/15"
          >
            <Megaphone className="h-3.5 w-3.5 shrink-0" />
            View the campaign you just planned
            <ArrowRight className="h-3.5 w-3.5 shrink-0" />
          </Link>
        </div>
      )}

      {!streaming && pendingApply && (
        <div className="px-4 pb-1.5 sm:px-6">
          <div className="flex items-center justify-between gap-3 rounded-xl border border-sage/30 bg-sage/10 px-3.5 py-2 text-xs">
            <span className="inline-flex items-center gap-1.5 text-sage">
              <WandSparkles className="h-3.5 w-3.5 shrink-0" />
              You have an unapplied caption for this post.
            </span>
            <button
              onClick={onApplyToPost}
              disabled={updatePost.isPending}
              className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-sage px-2.5 py-1 font-medium text-background transition-colors hover:bg-sage/90 disabled:opacity-60"
            >
              {updatePost.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
              Apply to post
            </button>
          </div>
        </div>
      )}

      {!streaming && followups.length > 0 && (
        <FollowUpChips options={followups} onSelect={handleSend} disabled={streaming} />
      )}

      <ChatInput
        onSend={handleSend}
        disabled={streaming}
        streaming={streaming}
        onStop={stopStreaming}
        files={attachments.files}
        onAddFiles={handleAddFiles}
        onRemoveFile={attachments.removeFile}
      />

      {/* HITL publish gate: the agent paused for approval — review/edit the preview, then approve (resume
          the graph to publish) or close (cancel). Reuses the same dialog as the "Post to socials" chip. */}
      {publishProposal && (
        <PublishPreviewDialog
          open
          onOpenChange={(v) => { if (!v) resumePublish({ approved: false }) }}
          initialCaption={publishProposal.caption}
          initialImages={publishProposal.images || []}
          onApprove={(d) => resumePublish(d)}
        />
      )}
    </div>
  )
}
