import { useEffect, useState } from 'react'
import { Search, Filter, ChevronDown, Loader2 } from 'lucide-react'
import { useStore } from '../store'
import { api } from '../api/client'
import { getCapabilityBadgeColor, getCapabilityLabel, formatModelName } from '../utils'

export function ModelList() {
  const { models, setModels, selectedModel, setSelectedModel, isLoading, setLoading, setError, clearError } = useStore()

  const [search, setSearch] = useState('')
  const [capabilityFilter, setCapabilityFilter] = useState<string>('')
  const [platformFilter, setPlatformFilter] = useState<string>('')
  const [showFilters, setShowFilters] = useState(false)

  const platforms = [...new Set(models.map(m => m.platform))].sort()
  const capabilities = ['tool_capable', 'chat_only', 'unavailable', 'unknown'] as const

  const filteredModels = models.filter(m => {
    const matchesSearch = m.id.toLowerCase().includes(search.toLowerCase()) ||
      m.display_name?.toLowerCase().includes(search.toLowerCase())
    const matchesCapability = !capabilityFilter || m.capability === capabilityFilter
    const matchesPlatform = !platformFilter || m.platform === platformFilter
    return matchesSearch && matchesCapability && matchesPlatform
  })

  useEffect(() => {
    loadModels()
  }, [])

  async function loadModels() {
    setLoading(true)
    clearError()
    try {
      const response = await api.listModels()
      setModels(response.data)
    } catch (err) {
      setError('Failed to load models')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-slate-900/50 rounded-xl border border-slate-700 overflow-hidden">
      <div className="flex flex-col sm:flex-row gap-3 p-4 border-b border-slate-700 bg-slate-800/50">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
          <input
            type="text"
            placeholder="Search models..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm text-slate-300 hover:bg-slate-600 transition-colors"
          >
            <Filter className="w-4 h-4" />
            Filters
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      {showFilters && (
        <div className="p-4 border-b border-slate-700 bg-slate-800/50 flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-400">Capability:</label>
            <select
              value={capabilityFilter}
              onChange={(e) => setCapabilityFilter(e.target.value)}
              className="px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All</option>
              {capabilities.map(cap => (
                <option key={cap} value={cap}>{getCapabilityLabel(cap)}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-400">Platform:</label>
            <select
              value={platformFilter}
              onChange={(e) => setPlatformFilter(e.target.value)}
              className="px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All</option>
              {platforms.map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-auto">
        {isLoading && models.length === 0 ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
          </div>
        ) : filteredModels.length === 0 ? (
          <div className="flex items-center justify-center h-64 text-slate-500">
            No models found
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-800/80 backdrop-blur-sm z-10">
              <tr className="border-b border-slate-700">
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Model</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Platform</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Capability</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Context</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredModels.map((model) => (
                <tr
                  key={model.id}
                  className={`border-b border-slate-700/50 hover:bg-slate-800/50 transition-colors ${
                    selectedModel === model.id ? 'bg-blue-500/10' : ''
                  }`}
                  onClick={() => setSelectedModel(selectedModel === model.id ? null : model.id)}
                >
                  <td className="px-4 py-3">
                    <div className="font-mono text-white">{formatModelName(model)}</div>
                    {model.context_window && (
                      <div className="text-xs text-slate-500">{model.context_window.toLocaleString()} ctx</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-300 capitalize">{model.platform}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${getCapabilityBadgeColor(model.capability)}`}>
                      {getCapabilityLabel(model.capability)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 font-mono">
                    {model.context_window ? model.context_window.toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedModel(selectedModel === model.id ? null : model.id)
                      }}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                        selectedModel === model.id
                          ? 'bg-blue-500 text-white'
                          : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                      }`}
                    >
                      {selectedModel === model.id ? 'Deselect' : 'Select'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}