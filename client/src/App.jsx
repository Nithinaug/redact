import { useState, useRef, useCallback } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [file, setFile] = useState(null)
  const [batchFiles, setBatchFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [text, setText] = useState('')
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [inputText, setInputText] = useState('')
  const [mode, setMode] = useState('file')
  const [disabledIds, setDisabledIds] = useState(new Set())
  const fileRef = useRef()
  const addFileRef = useRef()
  const textRef = useRef()
  const abortRef = useRef(null)

  const MAX_FILE_SIZE = 25 * 1024 * 1024
  const MAX_BATCH_COUNT = 50

  const isZip = file && file.name.toLowerCase().endsWith('.zip')

  function validateBatch(arr) {
    if (arr.length > MAX_BATCH_COUNT) {
      setError(`Too many files. Maximum is ${MAX_BATCH_COUNT} per batch.`)
      return false
    }
    const oversized = arr.find(f => f.size > MAX_FILE_SIZE)
    if (oversized) {
      setError(`"${oversized.name}" is too large. Maximum size is 25MB per file.`)
      return false
    }
    return true
  }

  function handleFile(f) {
    if (!f) return
    if (f.size > MAX_FILE_SIZE) {
      setError('File too large. Maximum size is 25MB.')
      return
    }
    setFile(f)
    setBatchFiles([])
    setError('')
  }

  function handleFiles(fileList) {
    const arr = Array.from(fileList || [])
    if (!arr.length) return
    if (arr.length === 1) {
      handleFile(arr[0])
      return
    }
    if (!validateBatch(arr)) return
    setFile(null)
    setBatchFiles(arr)
    setError('')
  }

  function handleAddFiles(fileList) {
    const arr = Array.from(fileList || [])
    if (!arr.length) return
    const combined = [...(file ? [file] : []), ...arr]
    if (!validateBatch(combined)) return
    setFile(null)
    setBatchFiles(combined)
    setError('')
  }

  const [reviewFiles, setReviewFiles] = useState([])
  const [reviewMode, setReviewMode] = useState(null)
  const [zipErrors, setZipErrors] = useState([])

  async function handleAnalyzeBatch() {
    if (!batchFiles.length) return
    setLoading(true)
    setError('')
    const failures = []
    const analyzed = []
    await Promise.all(batchFiles.map(async (f) => {
      try {
        const form = new FormData()
        form.append('file', f)
        const res = await fetch(`${API}/analyze-file`, { method: 'POST', body: form })
        if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
        const data = await res.json()
        analyzed.push({ name: f.name, text: data.text, results: data.results, disabledIds: new Set() })
      } catch (e) {
        failures.push(`${f.name}: ${e.message}`)
      }
    }))
    setLoading(false)
    if (failures.length) setError(`${failures.length} file(s) failed to analyze: ${failures.join('; ')}`)
    if (analyzed.length) {
      setReviewFiles(analyzed)
      setReviewMode('batch')
    }
  }

  async function handleAnalyzeZip() {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/analyze-zip`, { method: 'POST', body: form })
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
      const data = await res.json()
      setReviewFiles(data.files.map(f => ({ name: f.name, text: f.text, results: f.results, disabledIds: new Set() })))
      setZipErrors(data.errors || [])
      setReviewMode('zip')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function toggleReviewInstance(fileIdx, r) {
    setReviewFiles(prev => prev.map((rf, i) => {
      if (i !== fileIdx) return rf
      const next = new Set(rf.disabledIds)
      const key = resultKey(r)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return { ...rf, disabledIds: next }
    }))
  }

  function toggleReviewType(fileIdx, type) {
    setReviewFiles(prev => prev.map((rf, i) => {
      if (i !== fileIdx) return rf
      const ofType = rf.results.filter(r => r.entity_type === type)
      const allEnabled = ofType.every(r => !rf.disabledIds.has(resultKey(r)))
      const next = new Set(rf.disabledIds)
      for (const r of ofType) {
        if (allEnabled) next.add(resultKey(r))
        else next.delete(resultKey(r))
      }
      return { ...rf, disabledIds: next }
    }))
  }

  function handleReviewBack() {
    setReviewFiles([])
    setReviewMode(null)
    setZipErrors([])
  }

  async function handleRedactReviewBatch() {
    setLoading(true)
    setError('')
    const failures = []
    await Promise.all(reviewFiles.map(async (rf) => {
      try {
        const originalFile = batchFiles.find(f => f.name === rf.name)
        if (!originalFile) throw new Error('original file not found')
        const filtered = rf.results.filter(r => !rf.disabledIds.has(resultKey(r)))
        const form = new FormData()
        form.append('file', originalFile)
        form.append('results', JSON.stringify(filtered))
        const res = await fetch(`${API}/redact-file`, { method: 'POST', body: form })
        if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `redacted_${rf.name}`
        a.click()
        URL.revokeObjectURL(url)
      } catch (e) {
        failures.push(`${rf.name}: ${e.message}`)
      }
    }))
    setLoading(false)
    if (failures.length) setError(`${failures.length} file(s) failed: ${failures.join('; ')}`)
    setReviewFiles([])
    setReviewMode(null)
    setBatchFiles([])
  }

  async function handleRedactReviewZip() {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const resultsMap = {}
      for (const rf of reviewFiles) {
        resultsMap[rf.name] = rf.results.filter(r => !rf.disabledIds.has(resultKey(r)))
      }
      const form = new FormData()
      form.append('file', file)
      form.append('results', JSON.stringify(resultsMap))
      const res = await fetch(`${API}/redact-zip`, { method: 'POST', body: form })
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `redacted_${file.name}`
      a.click()
      URL.revokeObjectURL(url)
      setFile(null)
      setReviewFiles([])
      setReviewMode(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const [textResults, setTextResults] = useState([])
  const [textRedacted, setTextRedacted] = useState(false)
  const textEntityTypes = [...new Set(textResults.map(r => r.entity_type))].sort()

  async function handleAnalyzeText() {
    if (!inputText.trim()) return
    setLoading(true)
    setError('')
    setTextResults([])
    setDisabledIds(new Set())
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

  const resultKey = r => `${r.start}-${r.end}`

  function toggleInstance(r) {
    setDisabledIds(prev => {
      const next = new Set(prev)
      const key = resultKey(r)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function toggleType(type, activeResults) {
    const ofType = activeResults.filter(r => r.entity_type === type)
    const allEnabled = ofType.every(r => !disabledIds.has(resultKey(r)))
    setDisabledIds(prev => {
      const next = new Set(prev)
      for (const r of ofType) {
        if (allEnabled) next.add(resultKey(r))
        else next.delete(resultKey(r))
      }
      return next
    })
  }

  function handleRedactText() {
    let redacted = inputText
    const filtered = [...textResults]
      .filter(r => !disabledIds.has(resultKey(r)))
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
    if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files)
  }, [])

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
  const filteredResults = results.filter(r => !disabledIds.has(resultKey(r)))

  return (
    <div className="app">
      {!results.length && !reviewFiles.length && (
        <div className="top-section">
          <div className="hero">
            <div className="page-header">
              <p className="page-heading">Upload Text & Files for Redaction</p>
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
                    onClick={() => !file && !batchFiles.length && fileRef.current?.click()}
                  >
                    {!file && !batchFiles.length ? (
                      <>
                        <div className="dropzone-icon"><svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg></div>
                        <p className="dropzone-hint">PDF, DOCX, XLSX, CSV, JPG, PNG, ZIP — up to 25MB.</p>
                      </>
                    ) : file ? (
                      <div className="file-ready">
                        <p className="file-ready-name">{file.name}</p>
                        <p className="file-ready-size">{file.size < 1024 ? file.size + ' B' : file.size < 1024 * 1024 ? (file.size / 1024).toFixed(1) + ' KB' : (file.size / (1024 * 1024)).toFixed(2) + ' MB'}</p>
                        <div className="file-ready-actions">
                          {isZip ? (
                            <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); handleAnalyzeZip() }} disabled={loading}>
                              {loading ? 'Analyzing...' : 'Analyze Zip'}
                            </button>
                          ) : (
                            <>
                              <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); handleAnalyzeFile(file) }}>Analyze</button>
                              <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); addFileRef.current?.click() }}>Add File</button>
                            </>
                          )}
                          <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); setFile(null) }}>Cancel</button>
                        </div>
                        <input
                          ref={addFileRef}
                          type="file"
                          multiple
                          accept=".pdf,.docx,.xlsx,.csv,.txt,.json,.jpg,.jpeg,.png,.tiff,.tif,.bmp"
                          onChange={e => { handleAddFiles(e.target.files); e.target.value = '' }}
                          hidden
                        />
                      </div>
                    ) : (
                      <div className="file-ready">
                        <p className="file-ready-name">{batchFiles.length} files selected</p>
                        <ul className="batch-file-list">
                          {batchFiles.map((f, i) => (
                            <li key={i}>{f.name} <span className="file-ready-size">({f.size < 1024 * 1024 ? (f.size / 1024).toFixed(1) + ' KB' : (f.size / (1024 * 1024)).toFixed(2) + ' MB'})</span></li>
                          ))}
                        </ul>
                        <div className="file-ready-actions">
                          <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); handleAnalyzeBatch() }} disabled={loading}>
                            {loading ? 'Analyzing...' : `Analyze All (${batchFiles.length})`}
                          </button>
                          <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); setBatchFiles([]) }}>Cancel</button>
                        </div>
                      </div>
                    )}
                    <input
                      ref={fileRef}
                      type="file"
                      multiple
                      accept=".pdf,.docx,.xlsx,.csv,.txt,.json,.jpg,.jpeg,.png,.tiff,.tif,.bmp,.zip"
                      onChange={e => handleFiles(e.target.files)}
                      hidden
                    />
                  </div>
                ) : (
                  <div className="text-input-area">
                    {textResults.length > 0 && !textRedacted ? (
                      <div className="text-input text-highlight-preview">
                        {(() => {
                          const sorted = [...textResults].sort((a, b) => a.start - b.start)
                          const parts = []
                          let prev = 0
                          for (const r of sorted) {
                            const disabled = disabledIds.has(resultKey(r))
                            if (r.start > prev) parts.push(<span key={`t${prev}`}>{inputText.slice(prev, r.start)}</span>)
                            parts.push(
                              <mark
                                key={`m${r.start}`}
                                title={`${r.entity_type} - click to ${disabled ? 'include' : 'exclude'}`}
                                className={disabled ? 'highlight highlight-disabled' : 'highlight'}
                                onClick={() => toggleInstance(r)}
                              >
                                {inputText.slice(r.start, r.end)}
                              </mark>
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
                              checked={textResults.filter(r => r.entity_type === type).every(r => !disabledIds.has(resultKey(r)))}
                              onChange={() => toggleType(type, textResults)}
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
            <button className="btn btn-secondary" onClick={() => { if (abortRef.current) abortRef.current.abort(); setLoading(false); setResults([]); setText(''); setFile(null); setInputText(''); setDisabledIds(new Set()) }}>
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
                        const pageResults = results.filter(r => r.start >= pageStart && r.end <= pageEnd)
                        if (!pageResults.length) return <span>{pageText}</span>
                        const sorted = [...pageResults].sort((a, b) => a.start - b.start)
                        const parts = []
                        let prev = pageStart
                        for (const r of sorted) {
                          const disabled = disabledIds.has(resultKey(r))
                          if (r.start > prev) parts.push(<span key={`t${prev}`}>{text.slice(prev, r.start)}</span>)
                          parts.push(
                            <mark
                              key={`m${r.start}`}
                              title={`${r.entity_type} (${r.score}) - click to ${disabled ? 'include' : 'exclude'}`}
                              className={disabled ? 'highlight highlight-disabled' : 'highlight'}
                              onClick={() => toggleInstance(r)}
                            >
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
                      checked={results.filter(r => r.entity_type === type).every(r => !disabledIds.has(resultKey(r)))}
                      onChange={() => toggleType(type, results)}
                    />
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {reviewFiles.length > 0 && (
        <div className="results-view">
          <div className="results-toolbar">
            <button className="btn btn-secondary" onClick={handleReviewBack} disabled={loading}>
              Back
            </button>
            <button
              className="btn btn-primary"
              onClick={reviewMode === 'zip' ? handleRedactReviewZip : handleRedactReviewBatch}
              disabled={loading}
            >
              {loading ? 'Redacting...' : `Redact All (${reviewFiles.length})`}
            </button>
          </div>
          {zipErrors.length > 0 && (
            <div className="batch-errors">
              {zipErrors.map((e, i) => <p key={i}>{e.name}: {e.error}</p>)}
            </div>
          )}
          <div className="review-file-list">
            {reviewFiles.map((rf, idx) => {
              const entityTypesForFile = [...new Set(rf.results.map(r => r.entity_type))].sort()
              return (
                <div className="review-file" key={rf.name}>
                  <div className="review-file-header">
                    <span className="review-file-name">{rf.name}</span>
                    <span className="review-file-count">{rf.results.length} detected</span>
                  </div>
                  <div className="review-file-body">
                    <div className="review-file-text">
                      {(() => {
                        if (!rf.results.length) return <span>{rf.text}</span>
                        const sorted = [...rf.results].sort((a, b) => a.start - b.start)
                        const parts = []
                        let prev = 0
                        for (const r of sorted) {
                          const disabled = rf.disabledIds.has(resultKey(r))
                          if (r.start > prev) parts.push(<span key={`t${prev}`}>{rf.text.slice(prev, r.start)}</span>)
                          parts.push(
                            <mark
                              key={`m${r.start}`}
                              title={`${r.entity_type} (${r.score}) - click to ${disabled ? 'include' : 'exclude'}`}
                              className={disabled ? 'highlight highlight-disabled' : 'highlight'}
                              onClick={() => toggleReviewInstance(idx, r)}
                            >
                              {rf.text.slice(r.start, r.end)}
                            </mark>
                          )
                          prev = r.end
                        }
                        if (prev < rf.text.length) parts.push(<span key="end">{rf.text.slice(prev)}</span>)
                        return parts
                      })()}
                    </div>
                    {entityTypesForFile.length > 0 && (
                      <div className="review-file-toggles">
                        {entityTypesForFile.map(type => (
                          <label key={type} className="entity-toggle">
                            <span className="entity-label">{type} ({rf.results.filter(r => r.entity_type === type).length})</span>
                            <input
                              type="checkbox"
                              checked={rf.results.filter(r => r.entity_type === type).every(r => !rf.disabledIds.has(resultKey(r)))}
                              onChange={() => toggleReviewType(idx, type)}
                            />
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {error && <div className="error-toast">{error}</div>}
    </div>
  )
}
