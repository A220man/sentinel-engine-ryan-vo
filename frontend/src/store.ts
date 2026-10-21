import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface Model {
  id: string
  object: string
  owned_by: string
  capability: 'tool_capable' | 'chat_only' | 'unavailable' | 'unknown'
  platform: string
  display_name?: string
  context_window?: number
  max_output_tokens?: number
  supports_tools?: boolean
  supports_vision?: boolean
  supports_streaming: boolean
}

interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content?: string
  tool_calls?: unknown[]
  tool_call_id?: string
}

interface Platform {
  id: number
  name: string
  display_name: string
  base_url: string
  models_url?: string
  chat_url?: string
  adapter_type: string
  quota_pool_type: string
  default_concurrency: number
  enabled: boolean
}

interface ApiKey {
  id: number
  platform_id: number
  name: string
  enabled: boolean
  status: string
  concurrency_limit?: number
  scope: string
  created_at: string
  platform?: {
    id: number
    name: string
    display_name: string
  }
}

interface AppState {
  models: Model[]
  platforms: Platform[]
  keys: ApiKey[]
  selectedModel: string | null
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null

  setModels: (models: Model[]) => void
  setPlatforms: (platforms: Platform[]) => void
  setKeys: (keys: ApiKey[]) => void
  setSelectedModel: (model: string | null) => void
  addMessage: (message: ChatMessage) => void
  setMessages: (messages: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  clearError: () => void
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      models: [],
      platforms: [],
      keys: [],
      selectedModel: null,
      messages: [],
      isLoading: false,
      error: null,

      setModels: (models) => set({ models }),
      setPlatforms: (platforms) => set({ platforms }),
      setKeys: (keys) => set({ keys }),
      setSelectedModel: (model) => set({ selectedModel: model }),
      addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
      setMessages: (messages) => set((state) => ({ messages: typeof messages === 'function' ? messages(state.messages) : messages })),
      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),
      clearError: () => set({ error: null }),
    }),
    {
      name: 'sentinel-engine-store',
      partialize: (state) => ({
        selectedModel: state.selectedModel,
      }),
    }
  )
)