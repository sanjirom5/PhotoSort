import { useEffect, useState } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import axios from 'axios'

const BADGE_CLASS = {
  collecting: 'badge-collecting',
  sorting:    'badge-sorting',
  done:       'badge-done',
  error:      'badge-error',
}

const BADGE_LABEL = {
  collecting: 'Ожидание загрузки',
  sorting:    'Сортировка…',
  done:       'Готово',
  error:      'Ошибка',
}

export default function SessionStatus() {
  const { id } = useParams()
  const { state } = useLocation()   // contains drive_folder_link & telegram_link from navigate()
  const navigate = useNavigate()

  const [status, setStatus] = useState(null)
  const [sortLoading, setSortLoading] = useState(false)
  const [sortTriggered, setSortTriggered] = useState(false)
  const [copyMsg, setCopyMsg] = useState('')

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const res = await axios.get(`/session/${id}/status`)
        if (cancelled) return
        setStatus(res.data)
        if (res.data.status === 'done') {
          navigate(`/session/${id}/results`)
        }
      } catch {
        // server might be starting up — keep polling silently
      }
    }

    poll()
    const interval = setInterval(poll, 5000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [id])

  async function handleSort() {
    setSortLoading(true)
    try {
      await axios.post(`/session/${id}/sort`)
      setSortTriggered(true)
    } catch (e) {
      alert(e.response?.data?.detail || 'Ошибка запуска сортировки')
    } finally {
      setSortLoading(false)
    }
  }

  function copyToClipboard(text, label) {
    navigator.clipboard.writeText(text).then(() => {
      setCopyMsg(`${label} скопировано`)
      setTimeout(() => setCopyMsg(''), 2000)
    })
  }

  const sessionLink = `${window.location.origin}/session/${id}`

  return (
    <div className="card">
      <h2>Сессия {id}</h2>

      {/* Share links */}
      {state && (
        <div className="link-block">
          <div className="link-block-row">
            <div>
              <div className="link-label">Google Drive</div>
              <a
                className="link-url"
                href={state.drive_folder_link}
                target="_blank"
                rel="noreferrer"
              >
                {state.drive_folder_link}
              </a>
            </div>
            <button
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}
              onClick={() => copyToClipboard(state.drive_folder_link, 'Ссылка на Drive')}
            >
              Копировать
            </button>
          </div>

          <div className="link-block-row">
            <div>
              <div className="link-label">Telegram бот</div>
              <a
                className="link-url"
                href={state.telegram_link}
                target="_blank"
                rel="noreferrer"
              >
                {state.telegram_link}
              </a>
            </div>
            <button
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}
              onClick={() => copyToClipboard(state.telegram_link, 'Ссылка на бот')}
            >
              Копировать
            </button>
          </div>
        </div>
      )}

      {copyMsg && <p className="msg-success">{copyMsg}</p>}

      {/* Live status */}
      <div className="status-box">
        <div className="photo-count">{status?.photo_count ?? '—'}</div>
        <div className="photo-count-label">фото загружено</div>
        {status && (
          <span className={`status-badge ${BADGE_CLASS[status.status] || ''}`}>
            {BADGE_LABEL[status.status] || status.status}
          </span>
        )}
        {status?.error && <p className="msg-error">{status.error}</p>}
      </div>

      {/* Sort button */}
      {!sortTriggered && status?.status === 'collecting' ? (
        <button
          className="btn"
          onClick={handleSort}
          disabled={sortLoading || !status || status.photo_count === 0}
        >
          {sortLoading
            ? <><span className="spinner" /> Запускаем…</>
            : 'Сортировать'}
        </button>
      ) : sortTriggered || status?.status === 'sorting' ? (
        <p className="msg-hint">
          Сортировка идёт — страница обновится автоматически когда закончит.
        </p>
      ) : null}

      <p className="msg-hint" style={{ marginTop: '1.5rem' }}>
        Ссылка на эту страницу:{' '}
        <a className="link-url" href={sessionLink}>{sessionLink}</a>
      </p>
    </div>
  )
}
