import { useState, useRef, useCallback, useMemo } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [text, setText] = useState('')
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [inputText, setInputText] = useState('')
  const [mode, setMode] = useState('file')
  const [disabledTypes, setDisabledTypes] = useState(new Set())
  const fileRef = useRef()
  const textRef = useRef()
  const abortRef = useRef(null)

  const fileUrl = useMemo(() => {
    if (file) return URL.createObjectURL(file)
    return null
  }, [file])

  function handleFile(f) {
    if (!f) return
    const maxSize = 25 * 1024 * 1024
    if (f.size > maxSize) {
      setError('File too large. Maximum size is 25MB.')
      return
    }
    setFile(f)
    setError('')
  }

  const [textResults, setTextResults] = useState([])
  const [textRedacted, setTextRedacted] = useState(false)
  const textEntityTypes = [...new Set(textResults.map(r => r.entity_type))].sort()

  async function handleAnalyzeText() {
    if (!inputText.trim()) return
    setLoading(true)
    setError('')
    setTextResults([])
    setDisabledTypes(new Set())
    try {
      const res = await fetch(`${API}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: inputText }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
      const data = await res.json()
      setTextResults(data.results)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleRedactText() {
    let redacted = inputText
    const filtered = [...textResults]
      .filter(r => !disabledTypes.has(r.entity_type))
      .sort((a, b) => b.start - a.start)
    for (const r of filtered) {
      redacted = redacted.slice(0, r.start) + `<${r.entity_type}>` + redacted.slice(r.end)
    }
    setInputText(redacted)
    setTextResults([])
    setTextRedacted(true)
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
    abortRef.current = new AbortController()
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('results', JSON.stringify(filteredResults))
      const res = await fetch(`${API}/redact-file`, { method: 'POST', body: form, signal: abortRef.current.signal })
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `redacted_${file.name}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    } finally {
      setLoading(false)
      abortRef.current = null
    }
  }

  const entityTypes = [...new Set(results.map(r => r.entity_type))].sort()
  const filteredResults = results.filter(r => !disabledTypes.has(r.entity_type))

  function toggleType(type) {
    setDisabledTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
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
      {!results.length && (
        <div className="top-section">
          <div className="hero">
            <div className="page-header">
              <p className="page-heading">Upload Text & Document for Redaction</p>
            </div>

            {loading ? (
              <div className="dropzone-card">
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: '48px 0' }}>
                  <div className="spinner" />
                </div>
              </div>
            ) : (
              <div className="dropzone-card">
                <div className="mode-tabs">
                  <button className={`mode-tab ${mode === 'file' ? 'active' : ''}`} onClick={() => setMode('file')}>Upload File</button>
                  <button className={`mode-tab ${mode === 'text' ? 'active' : ''}`} onClick={() => { setMode('text'); setTimeout(() => textRef.current?.focus(), 0) }}>Paste Text</button>
                </div>

                {mode === 'file' ? (
                  <div
                    className={`dropzone-inline ${dragActive ? 'dropzone-active' : ''}`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    onClick={() => !file && fileRef.current?.click()}
                  >
                    {!file ? (
                      <>
                        <div className="dropzone-icon"><svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg></div>
                        <p className="dropzone-hint">PDF, DOCX, XLSX, CSV — up to 25MB</p>
                      </>
                    ) : (
                      <div className="file-ready">
                        <p className="file-ready-name">{file.name}</p>
                        <p className="file-ready-size">{file.size < 1024 ? file.size + ' B' : file.size < 1024 * 1024 ? (file.size / 1024).toFixed(1) + ' KB' : (file.size / (1024 * 1024)).toFixed(2) + ' MB'}</p>
                        <div className="file-ready-actions">
                          <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); handleAnalyzeFile(file) }}>Analyze</button>
                          <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); setFile(null) }}>Cancel</button>
                        </div>
                      </div>
                    )}
                    <input
                      ref={fileRef}
                      type="file"
                      accept=".pdf,.docx,.xlsx,.csv,.txt,.json"
                      onChange={e => handleFile(e.target.files[0])}
                      hidden
                    />
                  </div>
                ) : (
                  <div className="text-input-area">
                    {textResults.length > 0 && !textRedacted ? (
                      <div className="text-input text-highlight-preview">
                        {(() => {
                          const filtered = textResults.filter(r => !disabledTypes.has(r.entity_type))
                          const sorted = [...filtered].sort((a, b) => a.start - b.start)
                          const parts = []
                          let prev = 0
                          for (const r of sorted) {
                            if (r.start > prev) parts.push(<span key={`t${prev}`}>{inputText.slice(prev, r.start)}</span>)
                            parts.push(
                              <mark key={`m${r.start}`} title={r.entity_type} className="highlight">{inputText.slice(r.start, r.end)}</mark>
                            )
                            prev = r.end
                          }
                          if (prev < inputText.length) parts.push(<span key="end">{inputText.slice(prev)}</span>)
                          return parts
                        })()}
                      </div>
                    ) : (
                      <textarea
                        ref={textRef}
                        className="text-input"
                        placeholder=""
                        value={inputText}
                        onChange={e => { setInputText(e.target.value); setTextResults([]); setTextRedacted(false) }}
                      />
                    )}
                    {textResults.length > 0 && !textRedacted && (
                      <div className="text-toggles">
                        {textEntityTypes.map(type => (
                          <label key={type} className="entity-toggle">
                            <span className="entity-label">{type} ({textResults.filter(r => r.entity_type === type).length})</span>
                            <input
                              type="checkbox"
                              checked={!disabledTypes.has(type)}
                              onChange={() => toggleType(type)}
                            />
                          </label>
                        ))}
                      </div>
                    )}
                    <div className="text-input-actions">
                      {!textRedacted && (
                        textResults.length === 0 ? (
                          <button className="btn btn-primary" onClick={handleAnalyzeText} disabled={!inputText.trim() || loading}>
                            {loading ? 'Analyzing...' : 'Analyze'}
                          </button>
                        ) : (
                          <button className="btn btn-primary" onClick={handleRedactText}>
                            Redact
                          </button>
                        )
                      )}
                      <button className="btn btn-secondary" onClick={() => { setInputText(''); setTextResults([]); setTextRedacted(false) }} disabled={!inputText || loading}>Clear</button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {results.length > 0 && (
        <div className="results-view">
          <div className="results-toolbar">
            <button className="btn btn-secondary" onClick={() => { if (abortRef.current) abortRef.current.abort(); setLoading(false); setResults([]); setText(''); setFile(null); setInputText(''); setDisabledTypes(new Set()) }}>
              Back
            </button>
            {file && (
              <button className="btn btn-primary" onClick={handleRedact} disabled={loading}>
                {loading ? 'Downloading...' : 'Download Redacted'}
              </button>
            )}
          </div>
          <div className="results-body-doc">
            <div className="doc-preview-container">
              <div className="doc-pages">
                {text.split('\n\n\n').map((pageText, pageIdx) => (
                  <div className="doc-page" key={pageIdx}>
                    <div className="doc-page-content">
                      {(() => {
                        if (!file) {
                          const parts = []
                          const regex = /<([A-Z_]+)>/g
                          let match, lastIdx = 0
                          const absStart = text.indexOf(pageText)
                          const pt = pageText
                          while ((match = regex.exec(pt)) !== null) {
                            if (match.index > lastIdx) parts.push(<span key={`t${absStart + lastIdx}`}>{pt.slice(lastIdx, match.index)}</span>)
                            parts.push(<span key={`b${absStart + match.index}`} className="blackbar" title={match[1]}>{match[0]}</span>)
                            lastIdx = match.index + match[0].length
                          }
                          if (lastIdx < pt.length) parts.push(<span key={`e${absStart + lastIdx}`}>{pt.slice(lastIdx)}</span>)
                          return parts.length ? parts : <span>{pt}</span>
                        }
                        const pageStart = text.indexOf(pageText)
                        const pageEnd = pageStart + pageText.length
                        const pageResults = filteredResults.filter(r => r.start >= pageStart && r.end <= pageEnd)
                        if (!pageResults.length) return <span>{pageText}</span>
                        const sorted = [...pageResults].sort((a, b) => a.start - b.start)
                        const parts = []
                        let prev = pageStart
                        for (const r of sorted) {
                          if (r.start > prev) parts.push(<span key={`t${prev}`}>{text.slice(prev, r.start)}</span>)
                          parts.push(
                            <mark key={`m${r.start}`} title={`${r.entity_type} (${r.score})`} className="highlight">
                              {text.slice(r.start, r.end)}
                            </mark>
                          )
                          prev = r.end
                        }
                        if (prev < pageEnd) parts.push(<span key={`e${prev}`}>{text.slice(prev, pageEnd)}</span>)
                        return parts
                      })()}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="entities-sidebar">
              <div className="entity-toggles">
                {entityTypes.map(type => (
                  <label key={type} className="entity-toggle">
                    <span className="entity-label">{type} ({results.filter(r => r.entity_type === type).length})</span>
                    <input
                      type="checkbox"
                      checked={!disabledTypes.has(type)}
                      onChange={() => toggleType(type)}
                    />
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {error && <div className="error-toast">{error}</div>}
    </div>
  )
}
