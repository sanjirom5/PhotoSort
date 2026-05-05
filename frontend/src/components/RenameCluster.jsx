import { useState } from 'react'
import axios from 'axios'

export default function RenameCluster({ sessionId, onRenamed }) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [renamed, setRenamed] = useState(null)
  const [error, setError] = useState('')

  async function handleRename() {
    if (!text.trim()) return
    setLoading(true)
    setRenamed(null)
    setError('')
    try {
      const res = await axios.post(`/session/${sessionId}/rename`, { text })
      setRenamed(res.data.renamed)
      setText('')
      if (onRenamed && res.data.renamed.length > 0) onRenamed()
    } catch (e) {
      setError(e.response?.data?.detail || 'Ошибка переименования')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rename-box">
      <p>
        Переименуйте кластеры свободным текстом — например,<br />
        <em>«Person_1 это Саня, Person_2 это Диас»</em>
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Person_1 это Саня, Person_2 это Диас"
        rows={2}
      />
      <button
        className="btn"
        style={{ marginTop: '0.75rem' }}
        onClick={handleRename}
        disabled={loading || !text.trim()}
      >
        {loading ? <><span className="spinner" /> Обрабатываем…</> : 'Переименовать'}
      </button>

      {renamed && renamed.length > 0 && (
        <p className="msg-success">
          Переименовано: {renamed.map((r) => `${r.from} → ${r.to}`).join(', ')}
        </p>
      )}
      {renamed && renamed.length === 0 && (
        <p className="msg-hint">Не удалось распознать кластеры в тексте</p>
      )}
      {error && <p className="msg-error">{error}</p>}
    </div>
  )
}
