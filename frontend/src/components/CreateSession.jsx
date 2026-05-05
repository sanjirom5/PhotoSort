import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

export default function CreateSession() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleCreate() {
    setLoading(true)
    setError('')
    try {
      const res = await axios.post('/session/create')
      navigate(`/session/${res.data.session_id}`, { state: res.data })
    } catch (e) {
      setError(e.response?.data?.detail || 'Не удалось создать сессию. Проверьте бэкенд.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2>Новая сессия</h2>
      <p>
        Создайте сессию — получите ссылку на Google Drive и Telegram бот.
        Поделитесь ими с участниками: они смогут загружать фото через любой из каналов.
      </p>

      <button className="btn" onClick={handleCreate} disabled={loading}>
        {loading ? <><span className="spinner" /> Создаём…</> : '+ Создать сессию'}
      </button>

      {error && <p className="msg-error">{error}</p>}
    </div>
  )
}
