import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE = '/v1'

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      timeout: 60000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = localStorage.getItem('access_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('access_token')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  // Models
  async listModels(params?: { capability?: string; platform?: string; enabled_only?: boolean }) {
    const response = await this.client.get<ModelsListResponse>('/models', { params })
    return response.data
  }

  // Chat
  async chatCompletion(request: ChatCompletionRequest) {
    const response = await this.client.post<ChatCompletionResponse>('/chat/completions', request)
    return response.data
  }

  async chatCompletionStream(request: ChatCompletionRequest, onChunk: (chunk: string) => void) {
    const response = await this.client.post('/chat/completions/stream', request, {
      responseType: 'stream',
    })
    return new Promise<void>((resolve, reject) => {
      response.data.on('data', (chunk: Uint8Array) => {
        onChunk(new TextDecoder().decode(chunk))
      })
      response.data.on('end', () => resolve())
      response.data.on('error', reject)
    })
  }

  // Platforms
  async listPlatforms() {
    const response = await this.client.get<PlatformResponse[]>('/platforms')
    return response.data
  }

  async createPlatform(data: PlatformCreate) {
    const response = await this.client.post<PlatformResponse>('/platforms', data)
    return response.data
  }

  // Keys
  async listKeys(platformId?: number) {
    const response = await this.client.get<ApiKeyResponse[]>('/keys', { params: { platform_id: platformId } })
    return response.data
  }

  async createKey(data: ApiKeyCreate) {
    const response = await this.client.post<ApiKeyResponse>('/keys', data)
    return response.data
  }

  async deleteKey(keyId: number) {
    await this.client.delete(`/keys/${keyId}`)
  }

  // Health & Stats
  async health() {
    const response = await this.client.get('/health')
    return response.data
  }

  async stats() {
    const response = await this.client.get('/stats')
    return response.data
  }
}

export const api = new ApiClient()

// Types
export interface ModelResponse {
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

export interface ModelsListResponse {
  object: string
  data: ModelResponse[]
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content?: string
  tool_calls?: unknown[]
  tool_call_id?: string
}

export interface ChatCompletionRequest {
  model: string
  messages: ChatMessage[]
  temperature?: number
  max_tokens?: number
  stream?: boolean
  tools?: unknown[]
  tool_choice?: string
}

export interface ChatCompletionResponse {
  id: string
  object: string
  created: number
  model: string
  choices: unknown[]
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}

export interface PlatformResponse {
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

export interface PlatformCreate {
  name: string
  display_name: string
  base_url: string
  models_url?: string
  chat_url?: string
  adapter_type: string
  quota_pool_type?: string
  default_concurrency?: number
}

export interface ApiKeyResponse {
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

export interface ApiKeyCreate {
  platform_id: number
  name: string
  key: string
  concurrency_limit?: number
  scope?: string
}