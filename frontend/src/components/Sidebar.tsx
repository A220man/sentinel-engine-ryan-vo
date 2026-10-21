import { Bot, Key, Server, BarChart3, Settings, ChevronLeft, ChevronRight, Loader2, X } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useStore } from '../store'
import { api } from '../api/client'
import { ModelList } from './ModelList'

type Tab = 'models' | 'platforms' | 'keys' | 'stats' | 'settings'

export function Sidebar() {
  const [activeTab, setActiveTab] = useState<Tab>('models')
  const [collapsed, setCollapsed] = useState(false)
  const { setPlatforms, setKeys } = useStore()

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'models', label: 'Models', icon: <Bot className="w-5 h-5" /> },
    { id: 'platforms', label: 'Platforms', icon: <Server className="w-5 h-5" /> },
    { id: 'keys', label: 'API Keys', icon: <Key className="w-5 h-5" /> },
    { id: 'stats', label: 'Stats', icon: <BarChart3 className="w-5 h-5" /> },
    { id: 'settings', label: 'Settings', icon: <Settings className="w-5 h-5" /> },
  ]

  const loadPlatforms = async () => {
    try {
      const data = await api.listPlatforms()
      setPlatforms(data)
    } catch (err) {
      console.error('Failed to load platforms', err)
    }
  }

  const loadKeys = async () => {
    try {
      const data = await api.listKeys()
      setKeys(data)
    } catch (err) {
      console.error('Failed to load keys', err)
    }
  }

  return (
    <aside className={`${collapsed ? 'w-16' : 'w-72'} flex flex-col bg-slate-900/50 border-r border-slate-700 transition-all duration-200`}>
      <div className="flex items-center justify-between p-4 border-b border-slate-700">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <Bot className="w-6 h-6 text-blue-400" />
            <span className="font-semibold text-white">Sentinel Engine</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
        </button>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
            title={collapsed ? tab.label : undefined}
          >
            {tab.icon}
            {!collapsed && <span>{tab.label}</span>}
          </button>
        ))}
      </nav>

      {!collapsed && (
        <div className="p-4 border-t border-slate-700 bg-slate-800/50 flex-1 overflow-auto">
          {activeTab === 'models' && <ModelList />}
          {activeTab === 'platforms' && <PlatformsPanel onLoad={loadPlatforms} />}
          {activeTab === 'keys' && <KeysPanel onLoad={loadKeys} />}
          {activeTab === 'stats' && <StatsPanel />}
          {activeTab === 'settings' && <SettingsPanel />}
        </div>
      )}
    </aside>
  )
}

function PlatformsPanel({ onLoad }: { onLoad: () => Promise<void> }) {
  const { platforms } = useStore()
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', display_name: '', base_url: '', adapter_type: 'openai-compatible' })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await api.createPlatform(form)
      setShowForm(false)
      setForm({ name: '', display_name: '', base_url: '', adapter_type: 'openai-compatible' })
      await onLoad()
    } catch (err) {
      console.error('Failed to create platform', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <button
        onClick={() => setShowForm(true)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm text-slate-300 hover:bg-slate-600 transition-colors"
      >
        <Server className="w-4 h-4" />
        Add Platform
      </button>

      {showForm && (
        <form onSubmit={handleSubmit} className="space-y-3 p-3 bg-slate-800/50 rounded-lg border border-slate-700">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Name (slug)</label>
            <input
              type="text"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="openai"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Display Name</label>
            <input
              type="text"
              value={form.display_name}
              onChange={e => setForm({ ...form, display_name: e.target.value })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="OpenAI"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Base URL</label>
            <input
              type="url"
              value={form.base_url}
              onChange={e => setForm({ ...form, base_url: e.target.value })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="https://api.openai.com/v1"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Adapter Type</label>
            <select
              value={form.adapter_type}
              onChange={e => setForm({ ...form, adapter_type: e.target.value })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="openai-compatible">OpenAI Compatible</option>
              <option value="anthropic">Anthropic</option>
              <option value="gemini">Gemini</option>
              <option value="ollama">Ollama</option>
            </select>
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-3 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Creating...' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-3 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm font-medium hover:bg-slate-600 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {platforms.length === 0 ? (
          <p className="text-slate-500 text-sm text-center py-8">No platforms configured</p>
        ) : (
          platforms.map(p => (
            <div key={p.id} className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-white">{p.display_name}</div>
                  <div className="text-xs text-slate-500 font-mono">{p.name}</div>
                </div>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${p.enabled ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                  {p.enabled ? 'Enabled' : 'Disabled'}
                </span>
              </div>
              <div className="mt-1 text-xs text-slate-500 font-mono">{p.adapter_type}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function KeysPanel({ onLoad }: { onLoad: () => Promise<void> }) {
  const { keys, platforms } = useStore()
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ platform_id: '', name: '', key: '', scope: 'chat' })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await api.createKey({ ...form, platform_id: Number(form.platform_id) })
      setShowForm(false)
      setForm({ platform_id: '', name: '', key: '', scope: 'chat' })
      await onLoad()
    } catch (err) {
      console.error('Failed to create key', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (keyId: number) => {
    if (!confirm('Delete this API key?')) return
    try {
      await api.deleteKey(keyId)
      await onLoad()
    } catch (err) {
      console.error('Failed to delete key', err)
    }
  }

  return (
    <div className="space-y-4">
      <button
        onClick={() => setShowForm(true)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm text-slate-300 hover:bg-slate-600 transition-colors"
      >
        <Key className="w-4 h-4" />
        Add API Key
      </button>

      {showForm && (
        <form onSubmit={handleSubmit} className="space-y-3 p-3 bg-slate-800/50 rounded-lg border border-slate-700">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Platform</label>
            <select
              value={form.platform_id}
              onChange={e => setForm({ ...form, platform_id: e.target.value })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            >
              <option value="">Select platform</option>
              {platforms.map(p => (
                <option key={p.id} value={p.id}>{p.display_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Key Name</label>
            <input
              type="text"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="My OpenAI Key"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">API Key Value</label>
            <input
              type="password"
              value={form.key}
              onChange={e => setForm({ ...form, key: e.target.value })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="sk-..."
              required
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Scope</label>
            <select
              value={form.scope}
              onChange={e => setForm({ ...form, scope: e.target.value })}
              className="w-full px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="chat">Chat</option>
              <option value="embeddings">Embeddings</option>
              <option value="images">Images</option>
              <option value="all">All</option>
            </select>
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-3 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Creating...' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-3 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm font-medium hover:bg-slate-600 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {keys.length === 0 ? (
          <p className="text-slate-500 text-sm text-center py-8">No API keys configured</p>
        ) : (
          keys.map(k => (
            <div key={k.id} className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-white">{k.name}</div>
                  <div className="text-xs text-slate-500 capitalize">{k.platform?.display_name || 'Unknown'}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${k.enabled ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                    {k.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-300 border border-slate-600">
                    {k.status}
                  </span>
                  <button
                    onClick={() => handleDelete(k.id)}
                    className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                    title="Delete"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function StatsPanel() {
  const [stats, setStats] = useState({ models: 0, keys: 0, platforms: 0, requests_24h: 0, success_rate: 0 })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true)
      try {
        const data = await api.stats()
        setStats(data)
      } catch (err) {
        console.error('Failed to load stats', err)
      } finally {
        setLoading(false)
      }
    }
    fetchStats()
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="space-y-4">
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <StatCard label="Models" value={stats.models} />
          <StatCard label="API Keys" value={stats.keys} />
          <StatCard label="Platforms" value={stats.platforms} />
          <StatCard label="Requests (24h)" value={stats.requests_24h} />
        </div>
      )}
      <div className="pt-4 border-t border-slate-700">
        <div className="text-xs text-slate-400 mb-2">Success Rate (24h)</div>
        <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
          <div
            className="h-full bg-green-500 rounded-full transition-all duration-300"
            style={{ width: `${stats.success_rate}%` }}
          />
        </div>
        <div className="text-sm text-slate-300 mt-1 text-right">{stats.success_rate.toFixed(1)}%</div>
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700">
      <div className="text-xs text-slate-400 mb-1">{label}</div>
      <div className="text-2xl font-bold text-white font-mono">{value.toLocaleString()}</div>
    </div>
  )
}

function SettingsPanel() {
  const [demoMode, setDemoMode] = useState(false)

  return (
    <div className="space-y-4">
      <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
        <div className="font-medium text-white mb-2">Demo Mode</div>
        <p className="text-sm text-slate-400 mb-4">
          Demo mode allows using the gateway without configuring external providers.
          Only works on localhost. Refuses to start in production.
        </p>
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={demoMode}
            onChange={e => setDemoMode(e.target.checked)}
            className="w-4 h-4 accent-blue-500"
          />
          <span className="text-sm text-slate-300">Enable demo mode (localhost only)</span>
        </label>
      </div>

      <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
        <div className="font-medium text-white mb-2">About</div>
        <p className="text-sm text-slate-400">Sentinel Engine v1.0.0</p>
        <p className="text-sm text-slate-400">LLM Gateway with smart routing and model probing</p>
      </div>
    </div>
  )
}