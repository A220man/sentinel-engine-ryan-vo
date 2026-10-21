import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { api } from './api/client'

// Mock the API client
vi.mock('./api/client', () => ({
  api: {
    listModels: vi.fn(),
    health: vi.fn(),
    chatCompletionStream: vi.fn(),
  },
}))

const mockModels = {
  object: 'list',
  data: [
    {
      id: 'gpt-4o-mini',
      object: 'model',
      owned_by: 'openai',
      capability: 'tool_capable' as const,
      platform: 'openai',
      display_name: 'GPT-4o Mini',
      context_window: 128000,
      max_output_tokens: 4096,
      supports_tools: true,
      supports_vision: true,
      supports_streaming: true,
    },
    {
      id: 'claude-3-haiku',
      object: 'model',
      owned_by: 'anthropic',
      capability: 'tool_capable' as const,
      platform: 'anthropic',
      display_name: 'Claude 3 Haiku',
      context_window: 200000,
      max_output_tokens: 4096,
      supports_tools: true,
      supports_vision: true,
      supports_streaming: true,
    },
  ],
}

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listModels).mockResolvedValue(mockModels)
    vi.mocked(api.health).mockResolvedValue({ status: 'healthy' })
    localStorage.clear()
  })

  it('renders the app header', async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Sentinel Engine')
    })
  })

  it('displays health indicator', async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument()
    })
  })
})

// Test utils
import { getCapabilityBadgeColor, getCapabilityLabel, formatTokens, formatLatency } from './utils'

describe('Utils', () => {
  it('returns correct badge colors', () => {
    expect(getCapabilityBadgeColor('tool_capable')).toContain('green')
    expect(getCapabilityBadgeColor('chat_only')).toContain('blue')
    expect(getCapabilityBadgeColor('unavailable')).toContain('red')
    expect(getCapabilityBadgeColor('unknown')).toContain('gray')
  })

  it('returns correct capability labels', () => {
    expect(getCapabilityLabel('tool_capable')).toBe('Tools ✓')
    expect(getCapabilityLabel('chat_only')).toBe('Chat Only')
    expect(getCapabilityLabel('unavailable')).toBe('Unavailable')
    expect(getCapabilityLabel('unknown')).toBe('Unknown')
  })

  it('formats tokens correctly', () => {
    expect(formatTokens(100, 50)).toBe('150 tokens (100 ↓ / 50 ↑)')
  })

  it('formats latency correctly', () => {
    expect(formatLatency(500)).toBe('500ms')
    expect(formatLatency(1500)).toBe('1.5s')
  })
})