import { Routes, Route, Link } from 'react-router-dom'
import CreateSession from './components/CreateSession'
import SessionStatus from './components/SessionStatus'
import ResultsPreview from './components/ResultsPreview'

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">PhotoSort</Link>
        <span className="logo-sub">Умная сортировка фото</span>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<CreateSession />} />
          <Route path="/session/:id" element={<SessionStatus />} />
          <Route path="/session/:id/results" element={<ResultsPreview />} />
        </Routes>
      </main>
    </div>
  )
}
