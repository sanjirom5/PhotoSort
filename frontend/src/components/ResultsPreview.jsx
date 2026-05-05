import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import axios from 'axios'
import RenameCluster from './RenameCluster'

export default function ResultsPreview() {
  const { id } = useParams()
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searching, setSearching] = useState(false)

  async function fetchResults() {
    try {
      const res = await axios.get(`/session/${id}/results`)
      setResults(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Ошибка загрузки результатов')
    }
  }

  useEffect(() => { fetchResults() }, [id])

  async function handleSearch() {
    if (!searchQuery.trim()) return
    setSearching(true)
    setSearchResults(null)
    try {
      const res = await axios.post(`/session/${id}/search`, { query: searchQuery })
      setSearchResults(res.data)
    } catch (e) {
      alert(e.response?.data?.detail || 'Ошибка поиска')
    } finally {
      setSearching(false)
    }
  }

  if (error) {
    return (
      <div className="card">
        <p className="msg-error">{error}</p>
      </div>
    )
  }

  if (!results) {
    return (
      <div className="card">
        <p style={{ color: 'var(--muted)' }}>Загружаем результаты…</p>
      </div>
    )
  }

  const totalPhotos =
    results.people.reduce((s, p) => s + p.photo_count, 0) +
    results.uncategorized

  return (
    <div className="card">
      <h2>Результаты</h2>

      {results.output_folder_link && (
        <a
          className="folder-link"
          href={results.output_folder_link}
          target="_blank"
          rel="noreferrer"
        >
          Открыть отсортированную папку →
        </a>
      )}

      {/* Summary tiles */}
      <div className="results-grid">
        <div className="results-tile">
          <div className="results-tile-title">Людей найдено</div>
          <div className="results-tile-value">{results.people.length}</div>
        </div>
        <div className="results-tile">
          <div className="results-tile-title">Без категории</div>
          <div className="results-tile-value">{results.uncategorized}</div>
        </div>
      </div>

      {/* People clusters */}
      {results.people.length > 0 && (
        <>
          <h3>Люди</h3>
          <ul className="people-list">
            {results.people.map((p) => (
              <li key={p.cluster_id}>
                <span>{p.label}</span>
                <span className="count-badge">{p.photo_count} фото</span>
              </li>
            ))}
          </ul>

          <RenameCluster sessionId={id} onRenamed={fetchResults} />
        </>
      )}

      <hr className="divider" />

      {/* Scenes */}
      {Object.keys(results.scenes).length > 0 && (
        <>
          <h3>Сцены</h3>
          <ul className="scene-list">
            {Object.entries(results.scenes).map(([scene, count]) => (
              <li key={scene}>
                <span>{scene}</span>
                <span className="count-badge">{count} фото</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <hr className="divider" />

      {/* Smart search */}
      <h3>Умный поиск</h3>
      <p style={{ marginBottom: '0.25rem' }}>
        Напишите по-русски, что хотите найти — например, «фото где мы едим у моря».
      </p>
      <div className="search-box">
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Опишите фото…"
        />
        <button className="btn" onClick={handleSearch} disabled={searching || !searchQuery.trim()}>
          {searching ? <span className="spinner" /> : 'Найти'}
        </button>
      </div>

      {searchResults && (
        <div className="search-results">
          {Object.keys(searchResults.scenes).length === 0 && searchResults.people.length === 0 ? (
            <p style={{ color: 'var(--muted)' }}>Ничего не найдено</p>
          ) : (
            <>
              {Object.entries(searchResults.scenes).map(([scene, count]) => (
                <p key={scene}>{scene}: {count} фото</p>
              ))}
              {searchResults.people.map((p) => (
                <p key={p.label}>{p.label}: {p.count} фото</p>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
