import { useState, useRef, useCallback } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [text, setText] = useState('')
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const fileRef = useRef()

  function handleFile(f) {
    if (!f) return
    const maxSize = 50 * 1024 * 1024
    if (f.size > maxSize) {
      setError('File too large. Maximum size is 50MB.')
      return
    }
    setFile(f)
    setError('')
    setTimeout(() => handleAnalyzeFile(f), 0)
  }

  async function handleAnalyzeFile(f) {
    setLoading(true)
    setError('')
    setText('')
    setResults([])
    try {
      const form = new FormData()
      form.append('file', f)
      const res = await fetch(`${API}/analyze-file`, { method: 'POST', body: form })
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
      const data = await res.json()
      setText(data.text)
      setResults(data.results)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDrag = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true)
    else if (e.type === 'dragleave') setDragActive(false)
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files?.[0]) handleFile(e.dataTransfer.files[0])
  }, [])

  async function handleAnalyze() {
    if (!file) return
    setLoading(true)
    setError('')
    setText('')
    setResults([])
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/analyze-file`, { method: 'POST', body: form })
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
      const data = await res.json()
      setText(data.text)
      setResults(data.results)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleRedact() {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/redact-file`, { method: 'POST', body: form })
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `redacted_${file.name}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function highlightText() {
    if (!text || !results.length) return text
    const sorted = [...results].sort((a, b) => a.start - b.start)
    const parts = []
    let prev = 0
    for (const r of sorted) {
      if (r.start > prev) parts.push(<span key={`t${prev}`}>{text.slice(prev, r.start)}</span>)
      parts.push(
        <mark key={`m${r.start}`} title={`${r.entity_type} (${r.score})`} className="highlight">
          {text.slice(r.start, r.end)}
        </mark>
      )
      prev = r.end
    }
    if (prev < text.length) parts.push(<span key="end">{text.slice(prev)}</span>)
    return parts
  }

  return (
    <div className="app">
      {/* Header area */}
      {!results.length && (
        <div className="top-section">
          <div className="hero">
            <div className="page-header" onClick={() => window.location.reload()}>
              <h1>DocRedact</h1>
              <p className="page-heading">Upload Document for Redaction of Sensitive Information</p>
            </div>

            {loading ? (
              <div className="dropzone-card">
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: '48px 0' }}>
                  <div className="spinner" />
                </div>
              </div>
            ) : (
              <div className="dropzone-card">
                <div
                  className={`dropzone-inline ${dragActive ? 'dropzone-active' : ''}`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileRef.current?.click()}
                >
                  <div className="dropzone-icon"><svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg></div>
                  <p className="dropzone-hint">PDF, DOCX, XLSX, CSV,TEXT — up to 50MB</p>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".pdf,.docx,.xlsx,.csv,.txt,.json"
                    onChange={e => handleFile(e.target.files[0])}
                    hidden
                  />
                </div>

              </div>
            )}
          </div>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="results-view">
          <div className="results-header">
            <div className="results-title">
              <h2>Analysis Results</h2>
              <span className="badge">{results.length} entities found</span>
            </div>
            <div className="results-actions">
              <button className="btn btn-secondary" onClick={() => { setResults([]); setText(''); setFile(null) }}>
                New Analysis
              </button>
              <button className="btn btn-danger" onClick={handleRedact} disabled={loading}>
                Redact &amp; Download
              </button>
            </div>
          </div>

          <div className="results-body">
            <div className="panel">
              <h3>Detected Entities</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Text</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((r, i) => (
                      <tr key={i}>
                        <td><code>{r.entity_type}</code></td>
                        <td className="entity-text">{text.slice(r.start, r.end)}</td>
                        <td><span className="score">{r.score}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="panel">
              <h3>Highlighted Text</h3>
              <div className="text-preview">
                {highlightText()}
              </div>
            </div>
          </div>
        </div>
      )}

      {error && <div className="error-toast">{error}</div>}
    </div>
  )
}
