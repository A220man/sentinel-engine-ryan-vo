import { useEffect, useRef, useState } from 'react'
import { Send, Loader2, X, Bot, User } from 'lucide-react'
import { useStore } from '../store'
import { api } from '../api/client'
import { ChatMessage, ChatCompletionRequest } from '../api/client'

export function ChatPanel() {
  const { selectedModel, messages, setMessages, addMessage, setLoading, error, setError, clearError } = useStore()
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || !selectedModel || isStreaming) return

    const userMessage: ChatMessage = { role: 'user', content: input }
    addMessage(userMessage)
    setInput('')
    setIsStreaming(true)
    setStreamingContent('')
    clearError()
    setLoading(true)

    try {
      const request: ChatCompletionRequest = {
        model: selectedModel,
        messages: [...messages, userMessage],
        stream: true,
        temperature: 0.7,
      }

      await api.chatCompletionStream(request, (chunk) => {
        setStreamingContent((prev: string) => prev + chunk)
      })

      const assistantMessage: ChatMessage = { role: 'assistant', content: streamingContent }
      setMessages((prev: ChatMessage[]) => [...prev.slice(0, -1), assistantMessage])
    } catch (err) {
      setError('Failed to get response')
      setMessages((prev: ChatMessage[]) => prev.slice(0, -1))
    } finally {
      setIsStreaming(false)
      setStreamingContent('')
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  if (!selectedModel) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-500 p-8">
        <Bot className="w-16 h-16 mb-4 opacity-50" />
        <h3 className="text-lg font-medium mb-2">Select a model to start chatting</h3>
        <p className="text-sm">Choose a model from the sidebar</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-slate-900/50 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700 bg-slate-800/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bot className="w-5 h-5 text-blue-400" />
          <div>
            <div className="font-mono text-white">{selectedModel}</div>
            <div className="text-xs text-slate-500">Streaming: {isStreaming ? 'Active' : 'Ready'}</div>
          </div>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-400">
          {messages.length > 0 && (
            <span>{messages.filter(m => m.role === 'user').length} messages</span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
              msg.role === 'user' ? 'bg-blue-500/20 text-blue-400' : 'bg-green-500/20 text-green-400'
            }`}>
              {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>
            <div className={`max-w-[80%] ${msg.role === 'user' ? 'text-right' : ''}`}>
              <div className={`inline-block px-4 py-2 rounded-2xl ${
                msg.role === 'user'
                  ? 'bg-blue-500/10 text-blue-100 border border-blue-500/20'
                  : 'bg-slate-800 text-white border border-slate-700'
              }`}>
                <pre className="whitespace-pre-wrap text-sm">{msg.content || streamingContent}</pre>
              </div>
            </div>
          </div>
        ))}

        {isStreaming && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-green-500/20 text-green-400 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-slate-800 border border-slate-700 rounded-2xl px-4 py-2 max-w-[80%]">
              <pre className="whitespace-pre-wrap text-sm">{streamingContent}<span className="animate-pulse">▌</span></pre>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="p-4 border-t border-slate-700 bg-slate-800/50">
        <div className="flex gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? 'Waiting for response...' : 'Type a message...'}
            disabled={isStreaming || !selectedModel}
            rows={1}
            className="flex-1 px-4 py-3 bg-slate-700 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none min-h-[48px] max-h-48"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming || !selectedModel}
            className="px-6 py-3 bg-blue-500 text-white rounded-xl font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <Send className="w-5 h-5" />
            {isStreaming ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Send'}
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
          <span>Shift+Enter for new line</span>
          <span>{input.length} chars</span>
        </div>
      </form>

      {error && (
        <div className="mx-4 mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={clearError} className="text-red-400 hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}