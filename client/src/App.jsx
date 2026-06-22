import { useState, useRef } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [text, setText] = useState('')
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const fileRef = useRef()

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
        <mark key={`m${r.start}`} title={`${r.entity_type} (${r.score})`} style={{ background: 'var(--accent-bg)', border: '1px solid var(--accent-border)', borderRadius: 3, padding: '0 2px' }}>
          {text.slice(r.start, r.end)}
        </mark>
      )
      prev = r.end
    }
    if (prev < text.length) parts.push(<span key="end">{text.slice(prev)}</span>)
    return parts
  }

  return (
    <div style={{ padding: '40px 24px', textAlign: 'left', maxWidth: 800, margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center' }}>DocRedact</h1>
      <p style={{ textAlign: 'center', marginBottom: 32 }}>Upload a document to detect and redact PII</p>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 24 }}>
        <input ref={fileRef} type="file" accept=".pdf,.docx,.xlsx,.txt" onChange={e => setFile(e.target.files[0])} style={{ flex: 1 }} />
        <button onClick={handleAnalyze} disabled={!file || loading} style={btnStyle}>
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
        {results.length > 0 && (
          <button onClick={handleRedact} disabled={loading} style={{ ...btnStyle, background: '#e74c3c' }}>
            Redact & Download
          </button>
        )}
      </div>

      {error && <p style={{ color: '#e74c3c', marginBottom: 16 }}>{error}</p>}

      {results.length > 0 && (
        <>
          <h2>Detected Entities ({results.length})</h2>
          <div style={{ overflowX: 'auto', marginBottom: 24 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr>
                  {['Type', 'Text', 'Score', 'Recognizer'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '2px solid var(--border)', color: 'var(--text-h)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={cellStyle}><code style={{ fontSize: 12 }}>{r.entity_type}</code></td>
                    <td style={cellStyle}>{text.slice(r.start, r.end)}</td>
                    <td style={cellStyle}>{r.score}</td>
                    <td style={cellStyle}>{r.recognizer}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>Highlighted Text</h2>
          <div style={{ background: 'var(--code-bg)', padding: 16, borderRadius: 8, whiteSpace: 'pre-wrap', fontFamily: 'var(--mono)', fontSize: 14, lineHeight: '160%', maxHeight: 500, overflow: 'auto' }}>
            {highlightText()}
          </div>
        </>
      )}
    </div>
  )
}

const btnStyle = { padding: '8px 20px', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 14 }
const cellStyle = { padding: '8px 12px' }
