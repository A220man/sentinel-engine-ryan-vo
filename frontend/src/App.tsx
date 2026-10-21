import { useEffect } from 'react'
import { Sidebar } from './components/Sidebar'
import { ChatPanel } from './components/ChatPanel'
import { api } from './api/client'
import { useStore } from './store'

export default function App() {
  const { setModels, setLoading, setError } = useStore()

  useEffect(() => {
    loadModels()
  }, [])

  async function loadModels() {
    try {
      const response = await api.listModels()
      setModels(response.data)
    } catch (err) {
      console.error('Failed to load models:', err)
      setError('Failed to load models. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex">
      <Sidebar />
      <main className="flex-1 p-4 md:p-6 lg:p-8 overflow-auto">
        <div className="max-w-5xl mx-auto h-[calc(100vh-2rem)] md:h-[calc(100vh-3rem)] lg:h-[calc(100vh-4rem)] flex flex-col">
          {/* Header */}
          <header className="mb-6 flex items-center justify-between">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-white">Sentinel Engine</h1>
              <p className="text-slate-400 mt-1">LLM Gateway - Smart routing, failover, and model probing</p>
            </div>
            <div className="flex items-center gap-3">
              <HealthIndicator />
            </div>
          </header>

          {/* Main Content */}
          <div className="flex-1 flex gap-4 min-h-0">
            <ChatPanel />
          </div>
        </div>
      </main>
    </div>
  )
}

function HealthIndicator() {
  const [healthy, setHealthy] = useState(false)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  async function checkHealth() {
    try {
      await api.health()
      setHealthy(true)
    } catch {
      setHealthy(false)
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700">
      <div className={`w-2 h-2 rounded-full ${checking ? 'bg-yellow-400 animate-pulse' : healthy ? 'bg-green-400' : 'bg-red-400'}`} />
      <span className="text-xs text-slate-300 font-medium">
        {checking ? 'Checking...' : healthy ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  )
}

import { useState } from 'react'