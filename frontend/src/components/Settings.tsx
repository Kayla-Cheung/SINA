import { useState, useEffect } from 'react'
import type { LLMConfig } from '../types'

interface Props {
  onSave: (config: LLMConfig) => Promise<void>
  getConfig?: () => Promise<{ success: boolean; config: LLMConfig }>
  disabled?: boolean
}

export function Settings({ onSave, getConfig, disabled }: Props) {
  const [baseUrl, setBaseUrl] = useState('https://api.deepseek.com/v1')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('deepseek-v4-flash')
  const [thinkingEnabled, setThinkingEnabled] = useState(false)
  const [embeddingProvider, setEmbeddingProvider] = useState<'google' | 'openai'>('google')
  const [embeddingBaseUrl, setEmbeddingBaseUrl] = useState('https://generativelanguage.googleapis.com/v1beta')
  const [embeddingApiKey, setEmbeddingApiKey] = useState('')
  const [embeddingModel, setEmbeddingModel] = useState('gemini-embedding-2')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!getConfig) {
      setLoaded(true)
      return
    }
    getConfig()
      .then((resp) => {
        const c = resp.config
        if (c.base_url) setBaseUrl(c.base_url)
        if (c.api_key) setApiKey(c.api_key)
        if (c.model) setModel(c.model)
        if (typeof c.thinking_enabled === 'boolean') setThinkingEnabled(c.thinking_enabled)
        if (c.embedding_base_url) setEmbeddingBaseUrl(c.embedding_base_url)
        if (c.embedding_api_key) setEmbeddingApiKey(c.embedding_api_key)
        if (c.embedding_model) setEmbeddingModel(c.embedding_model)
        if (c.embedding_provider) setEmbeddingProvider(c.embedding_provider as 'google' | 'openai')
        if (c.api_key) setMessage('Loaded saved API configuration.')
      })
      .catch(() => {
        // No saved config yet — keep defaults
      })
      .finally(() => setLoaded(true))
  }, [getConfig])

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      await onSave({
        base_url: baseUrl,
        api_key: apiKey,
        model,
        embedding_base_url: embeddingBaseUrl,
        embedding_api_key: embeddingApiKey,
        embedding_model: embeddingModel,
        embedding_provider: embeddingProvider,
        thinking_enabled: thinkingEnabled,
      })
      setMessage('Configuration saved. It will auto-load next time.')
    } catch (e: any) {
      setMessage(`Error: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const fieldClass =
    'w-full bg-white border border-border rounded px-3 py-2 text-stone-900 text-sm'

  if (!loaded) {
    return (
      <div className="bg-panel border border-border rounded-lg p-4 shadow-sm">
        <p className="text-sm text-stone-500">Loading saved configuration...</p>
      </div>
    )
  }

  return (
    <div className="bg-panel border border-border rounded-lg p-4 space-y-3 shadow-sm">
      <h2 className="text-lg font-semibold text-stone-900">Chat LLM Configuration</h2>

      <div>
        <label className="block text-sm text-stone-500 mb-1">Chat Base URL</label>
        <input
          type="text"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          disabled={disabled}
          className={fieldClass}
          placeholder="https://api.deepseek.com/v1"
        />
      </div>

      <div>
        <label className="block text-sm text-stone-500 mb-1">Chat API Key</label>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          disabled={disabled}
          className={fieldClass}
          placeholder="sk-..."
        />
      </div>

      <div>
        <label className="block text-sm text-stone-500 mb-1">Chat Model</label>
        <input
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          disabled={disabled}
          className={fieldClass}
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-stone-700 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={thinkingEnabled}
          onChange={(e) => setThinkingEnabled(e.target.checked)}
          disabled={disabled}
          className="accent-accent"
        />
        Enable thinking mode
        <span className="text-xs text-stone-400">(default: off — faster & cheaper)</span>
      </label>

      <hr className="border-border" />

      <h2 className="text-lg font-semibold text-stone-900">Embedding Configuration</h2>

      <div>
        <label className="block text-sm text-stone-500 mb-1">Provider</label>
        <select
          value={embeddingProvider}
          onChange={(e) => setEmbeddingProvider(e.target.value as 'google' | 'openai')}
          disabled={disabled}
          className={fieldClass}
        >
          <option value="google">Google Gemini</option>
          <option value="openai">OpenAI-compatible</option>
        </select>
      </div>

      <div>
        <label className="block text-sm text-stone-500 mb-1">Embedding Base URL</label>
        <input
          type="text"
          value={embeddingBaseUrl}
          onChange={(e) => setEmbeddingBaseUrl(e.target.value)}
          disabled={disabled}
          className={fieldClass}
          placeholder="https://generativelanguage.googleapis.com/v1beta"
        />
      </div>

      <div>
        <label className="block text-sm text-stone-500 mb-1">Embedding API Key</label>
        <input
          type="password"
          value={embeddingApiKey}
          onChange={(e) => setEmbeddingApiKey(e.target.value)}
          disabled={disabled}
          className={fieldClass}
          placeholder="..."
        />
      </div>

      <div>
        <label className="block text-sm text-stone-500 mb-1">Embedding Model</label>
        <input
          type="text"
          value={embeddingModel}
          onChange={(e) => setEmbeddingModel(e.target.value)}
          disabled={disabled}
          className={fieldClass}
          placeholder="gemini-embedding-2"
        />
      </div>

      <button
        onClick={handleSave}
        disabled={disabled || saving || !apiKey || !embeddingApiKey}
        className="w-full bg-accent hover:bg-stone-800 disabled:bg-stone-300 text-white py-2 rounded font-medium transition"
      >
        {saving ? 'Saving...' : 'Save Configuration'}
      </button>

      {message && (
        <p className={`text-sm ${message.startsWith('Error') ? 'text-red-600' : 'text-emerald-700'}`}>
          {message}
        </p>
      )}
    </div>
  )
}
