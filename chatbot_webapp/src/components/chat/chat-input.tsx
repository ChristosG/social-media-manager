'use client'
import { useState, useRef, useCallback, useEffect, useLayoutEffect } from 'react'
import { icons } from '@/components/icons'
import { cn } from '@/lib/utils'
import type { PendingFile } from '@/hooks/use-file-attachments'
import { useSources } from '@/hooks/use-studio'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

interface ChatInputProps {
  onSend: (content: string, opts?: { groundSources?: boolean; reasoning?: boolean; webSearch?: boolean }) => void
  disabled?: boolean
  streaming?: boolean
  onStop?: () => void
  files?: PendingFile[]
  onAddFiles?: (files: File[]) => void
  onRemoveFile?: (id: string) => void
  /** Seed the composer once (e.g. "Refine this campaign post: …" handed off from the Workspace). Prefill only. */
  initialValue?: string
}

// Persist composer toggles across messages/sessions.
function usePersistentToggle(key: string, initial: boolean): [boolean, (v: boolean) => void] {
  const [val, setVal] = useState(initial)
  useEffect(() => {
    try {
      const raw = localStorage.getItem(key)
      if (raw !== null) setVal(raw === '1')
    } catch { /* ignore */ }
  }, [key])
  const set = useCallback((v: boolean) => {
    setVal(v)
    try { localStorage.setItem(key, v ? '1' : '0') } catch { /* ignore */ }
  }, [key])
  return [val, set]
}

// Tri-state composer mode (e.g. reasoning: Auto | On | Off), persisted.
type ReasoningMode = 'auto' | 'on' | 'off'
function usePersistentMode(key: string, initial: ReasoningMode): [ReasoningMode, (v: ReasoningMode) => void] {
  const [val, setVal] = useState<ReasoningMode>(initial)
  useEffect(() => {
    try {
      const raw = localStorage.getItem(key)
      if (raw === 'auto' || raw === 'on' || raw === 'off') setVal(raw)
    } catch { /* ignore */ }
  }, [key])
  const set = useCallback((v: ReasoningMode) => {
    setVal(v)
    try { localStorage.setItem(key, v) } catch { /* ignore */ }
  }, [key])
  return [val, set]
}

export function ChatInput({ onSend, disabled, streaming, onStop, files = [], onAddFiles, onRemoveFile, initialValue }: ChatInputProps) {
  const [value, setValue] = useState(initialValue ?? '')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Apply a prefill handed off from elsewhere (e.g. "Refine this campaign post: …") without clobbering
  // anything the user has already typed.
  useEffect(() => {
    if (initialValue) setValue((v) => v || initialValue)
  }, [initialValue])

  // --- Grounding state ---
  const { data: sourcesData } = useSources()
  const sourceCount = sourcesData?.sources?.length ?? 0
  const [groundSources, setGroundSources] = useState<boolean>(sourceCount > 0)

  // When sources load, default ON if there are any
  useEffect(() => {
    setGroundSources(sourceCount > 0)
  }, [sourceCount])

  // Reasoning mode (Auto = the assistant decides per turn) + web-search toggle (persisted).
  const [reasoningMode, setReasoningMode] = usePersistentMode('composer.reasoningMode', 'auto')
  const [webSearch, setWebSearch] = usePersistentToggle('composer.webSearch', false)
  // In Auto the router may still think — only an explicit On/Off counts as a "set" control here.
  const anyControlOn = groundSources || reasoningMode !== 'auto' || webSearch
  // Auto → undefined (let the backend router decide); On → true; Off → false.
  const reasoningOpt = reasoningMode === 'auto' ? undefined : reasoningMode === 'on'
  // ----------------------

  const canSend = value.trim().length > 0 || files.length > 0

  // Auto-grow the composer to fit its content up to ~10 lines, then scroll. Driven by `value` (not just
  // onChange) so it also resizes on the campaign prefill seed and after a send-reset clears the box.
  const MAX_COMPOSER_PX = 220 // ~10 lines at text-sm (20px line-height) + vertical padding
  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, MAX_COMPOSER_PX) + 'px'
  }, [value])

  const handleSubmit = useCallback(() => {
    if (!canSend || disabled) return
    onSend(value.trim(), { groundSources, reasoning: reasoningOpt, webSearch })
    setValue('') // height resets via the layout effect when value becomes empty
  }, [value, canSend, disabled, onSend, groundSources, reasoningOpt, webSearch])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value) // height is handled by the layout effect keyed on `value`
  }

  const handleFileSelect = () => {
    fileInputRef.current?.click()
  }

  const handleFilesAdded = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && onAddFiles) {
      onAddFiles(Array.from(e.target.files))
    }
    e.target.value = ''
  }

  return (
    <div className="p-2 sm:p-4 pb-[max(0.75rem,env(safe-area-inset-bottom,0.75rem))] sm:pb-[max(1.25rem,env(safe-area-inset-bottom,1.25rem))]">
      <div className="max-w-[var(--pau-chat-width)] mx-auto">
        <div className="rounded-2xl border border-border bg-card overflow-hidden transition-all focus-within:border-primary/50 focus-within:shadow-[0_0_0_3px_var(--pau-glow-primary)]">
          {/* File attachment chips */}
          {files.length > 0 && (
            <div className="flex flex-wrap gap-2 px-3 pt-3">
              {files.map(f => (
                <div
                  key={f.id}
                  className="flex items-center gap-1.5 rounded-lg bg-muted px-2.5 py-1 text-xs"
                >
                  {f.preview ? (
                    <img src={f.preview} alt={f.file.name} className="h-6 w-6 rounded object-cover" />
                  ) : f.file.type.startsWith('image/') ? (
                    <icons.image className="h-3.5 w-3.5 text-muted-foreground" />
                  ) : (
                    <icons.fileText className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                  <span className="max-w-32 truncate">{f.file.name}</span>
                  <span className="text-muted-foreground">
                    ({(f.file.size / 1024).toFixed(0)}KB)
                  </span>
                  {f.uploading && <icons.loader className="h-3 w-3 animate-spin text-primary" />}
                  <button
                    onClick={() => onRemoveFile?.(f.id)}
                    className="ml-0.5 text-muted-foreground hover:text-foreground"
                    aria-label="Remove file"
                  >
                    <icons.x className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Input area */}
          <div className="flex items-end gap-2 p-2">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFilesAdded}
              accept="text/*,image/*,application/pdf"
            />

            {/* Attach file button */}
            <button
              onClick={handleFileSelect}
              disabled={disabled}
              className="flex-shrink-0 flex items-center justify-center h-10 w-10 sm:h-8 sm:w-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors disabled:opacity-50"
              aria-label="Attach file"
            >
              <icons.paperclip className="h-4 w-4" />
            </button>

            {/* Composer Controls button + popover */}
            <TooltipProvider delayDuration={400}>
              <Popover>
                <PopoverTrigger asChild>
                  <button
                    disabled={disabled}
                    className={cn(
                      'relative flex-shrink-0 flex items-center justify-center h-10 w-10 sm:h-8 sm:w-8 rounded-lg transition-colors disabled:opacity-50',
                      anyControlOn
                        ? 'text-primary hover:text-primary hover:bg-primary/10'
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent',
                    )}
                    aria-label="Composer controls"
                  >
                    <icons.slidersHorizontal className="h-4 w-4" />
                    {/* Active indicator dot — visible when any control is ON */}
                    {anyControlOn && (
                      <span
                        className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_6px_var(--pau-glow-primary)]"
                        aria-hidden="true"
                      />
                    )}
                  </button>
                </PopoverTrigger>

                <PopoverContent side="top" align="start" className="w-72">
                  {/* ── GROUNDING section ── */}
                  <div className="space-y-3">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Grounding
                    </p>

                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-medium text-foreground leading-snug">
                          Ground in my sources
                        </span>
                        {sourceCount > 0 && (
                          <span className="shrink-0 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                            {sourceCount} {sourceCount === 1 ? 'source' : 'sources'}
                          </span>
                        )}
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="shrink-0 cursor-help text-muted-foreground hover:text-foreground transition-colors">
                              <icons.info className="h-3.5 w-3.5" />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-[220px] text-center">
                            When on, every message searches your connected sources and cites them.
                          </TooltipContent>
                        </Tooltip>
                      </div>

                      <Switch
                        checked={groundSources}
                        onCheckedChange={setGroundSources}
                        aria-label="Ground in my sources"
                        disabled={disabled}
                      />
                    </div>
                  </div>

                  {/* ── Separator ── */}
                  <div className="my-3 h-px bg-border" />

                  {/* ── REASONING + WEB SEARCH ── */}
                  <div className="space-y-3">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Model
                    </p>

                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <icons.sparkles className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        <span className="text-sm font-medium text-foreground leading-snug">Reasoning</span>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="shrink-0 cursor-help text-muted-foreground hover:text-foreground transition-colors">
                              <icons.info className="h-3.5 w-3.5" />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-[240px] text-center">
                            <b>Auto</b> lets the assistant decide when a turn needs to think
                            (corrections, comparisons, complex asks). <b>On</b> always thinks
                            (slower, shown in a collapsible block); <b>Off</b> stays fast.
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <div role="radiogroup" aria-label="Reasoning mode"
                           className="inline-flex shrink-0 rounded-lg border border-border bg-panel/40 p-0.5">
                        {(['auto', 'on', 'off'] as const).map((m) => (
                          <button
                            key={m}
                            type="button"
                            role="radio"
                            aria-checked={reasoningMode === m}
                            disabled={disabled}
                            onClick={() => setReasoningMode(m)}
                            className={cn(
                              'rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-colors',
                              reasoningMode === m
                                ? 'bg-primary/15 text-primary'
                                : 'text-muted-foreground hover:text-foreground',
                            )}
                          >
                            {m}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <icons.search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        <span className="text-sm font-medium text-foreground leading-snug">Web search</span>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="shrink-0 cursor-help text-muted-foreground hover:text-foreground transition-colors">
                              <icons.info className="h-3.5 w-3.5" />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-[220px] text-center">
                            Lets the assistant search the public web when it needs current facts, and cite
                            the sources it used.
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <Switch
                        checked={webSearch}
                        onCheckedChange={setWebSearch}
                        aria-label="Web search"
                        disabled={disabled}
                      />
                    </div>
                  </div>

                </PopoverContent>
              </Popover>
            </TooltipProvider>

            <textarea
              ref={textareaRef}
              value={value}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Send a message..."
              disabled={disabled}
              rows={1}
              className="flex-1 resize-none border-none bg-transparent px-1 py-1.5 text-sm outline-none placeholder:text-muted-foreground disabled:opacity-50 max-h-[220px] overflow-y-auto"
            />

            {streaming ? (
              <button
                onClick={onStop}
                className="flex-shrink-0 flex items-center justify-center h-10 w-10 sm:h-9 sm:w-9 rounded-xl bg-destructive text-destructive-foreground hover:brightness-110 transition-all"
                aria-label="Stop generating"
              >
                <icons.squareStop className="h-4 w-4" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={disabled || !canSend}
                className={cn(
                  'flex-shrink-0 flex items-center justify-center h-10 w-10 sm:h-9 sm:w-9 rounded-xl transition-all',
                  canSend && !disabled
                    ? 'bg-primary text-primary-foreground hover:brightness-110 shadow-[0_4px_14px_-4px_var(--pau-glow-primary)]'
                    : 'bg-muted text-muted-foreground',
                )}
                aria-label="Send message"
              >
                <icons.arrowUp className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
        <p className="hidden sm:block mt-1.5 text-center text-xs text-muted-foreground">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
