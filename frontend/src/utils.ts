import { ModelResponse } from './api/client'

export function getCapabilityBadgeColor(capability: ModelResponse['capability']): string {
  switch (capability) {
    case 'tool_capable':
      return 'bg-green-500/20 text-green-400 border-green-500/30'
    case 'chat_only':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
    case 'unavailable':
      return 'bg-red-500/20 text-red-400 border-red-500/30'
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
  }
}

export function getCapabilityLabel(capability: ModelResponse['capability']): string {
  switch (capability) {
    case 'tool_capable':
      return 'Tools ✓'
    case 'chat_only':
      return 'Chat Only'
    case 'unavailable':
      return 'Unavailable'
    default:
      return 'Unknown'
  }
}

export function formatModelName(model: ModelResponse): string {
  return model.display_name || model.id
}

export function formatTokens(prompt: number, completion: number): string {
  return `${prompt + completion} tokens (${prompt} ↓ / ${completion} ↑)`
}

export function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString()
}