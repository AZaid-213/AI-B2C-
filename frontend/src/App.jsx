import { useState, useRef } from 'react'

const API           = '/api/campaigns'
const DEFAULT_PHONE = '923422454713'

const PIPELINE_STEPS = [
  { id: 1, icon: '📤', label: 'Upload CSV' },
  { id: 2, icon: '🧹', label: 'Filter Data' },
  { id: 3, icon: '🤖', label: 'AI Generate' },
  { id: 4, icon: '👁️', label: 'Preview' },
  { id: 5, icon: '🎯', label: 'Audience' },
  { id: 6, icon: '🚀', label: 'Send' },
]

function isGroupId(v) { return String(v).includes('@g.us') }
function fmtRecipient(v) { return isGroupId(v) ? v : '+' + String(v).replace(/\D/g,'') }

// ── Step indicator ────────────────────────────────────────────────────────────
function StepBar({ current }) {
  return (
    <div className="step-indicator">
      {PIPELINE_STEPS.map((s,i) => (
        <div key={s.id} className="step-item">
          <div className={`step-circle ${current===s.id?'active':current>s.id?'done':''}`}>
            {current > s.id ? '✓' : s.icon}
          </div>
          {i < PIPELINE_STEPS.length-1 && <div className={`step-line ${current>s.id?'done':''}`}/>}
        </div>
      ))}
    </div>
  )
}

// ── WhatsApp bubble preview ───────────────────────────────────────────────────
function WaBubble({ message, imagePreview }) {
  return (
    <div className="wa-screen">
      <div className="wa-header">
        <div className="wa-avatar">W</div>
        <div><div className="wa-name">WhatsApp</div><div className="wa-status">online</div></div>
      </div>
      <div className="wa-body">
        <div className="wa-bubble">
          {imagePreview && <img src={imagePreview} alt="preview" className="wa-img-preview"/>}
          <pre className="wa-text">{message}</pre>
          <div className="wa-time">{new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})} ✓✓</div>
        </div>
      </div>
    </div>
  )
}

// ── Contacts table ────────────────────────────────────────────────────────────
function ContactsTable({ contacts }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>#</th><th>Name</th><th>Phone</th><th>City</th></tr></thead>
        <tbody>
          {contacts.slice(0,10).map((c,i)=>(
            <tr key={c.id||i}>
              <td>{i+1}</td><td>{c.name||'—'}</td>
              <td className="mono">{c.phone}</td><td>{c.city||'—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {contacts.length > 10 && <p className="table-more">+{contacts.length-10} more</p>}
    </div>
  )
}

// ── Settings panel (sidebar overlay) ─────────────────────────────────────────
function SettingsPanel({ onClose }) {
  const [instanceId, setInstanceId] = useState('')
  const [apiToken,   setApiToken]   = useState('')
  const [baseUrl,    setBaseUrl]    = useState('https://api.green-api.com')
  const [saving,     setSaving]     = useState(false)
  const [testing,    setTesting]    = useState(false)
  const [msg,        setMsg]        = useState(null)  // {type:'success'|'error', text}
  const [current,    setCurrent]    = useState(null)

  useState(()=>{
    fetch('/api/settings').then(r=>r.json()).then(d=>{
      setCurrent(d)
      if (d.instance_id) setInstanceId(d.instance_id)
      if (d.base_url)    setBaseUrl(d.base_url)
    }).catch(()=>{})
  })

  async function save() {
    if (!instanceId.trim() || !apiToken.trim()) { setMsg({type:'error',text:'Both fields required.'}); return }
    setSaving(true); setMsg(null)
    try {
      const r = await fetch('/api/settings', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ instance_id: instanceId.trim(), api_token: apiToken.trim(), base_url: baseUrl.trim() })
      })
      if (!r.ok) throw new Error((await r.json()).detail || 'Save failed')
      setMsg({type:'success', text:'Credentials saved!'})
      setApiToken('')
    } catch(e) { setMsg({type:'error', text:e.message}) }
    finally { setSaving(false) }
  }

  async function test() {
    setTesting(true); setMsg(null)
    try {
      const r = await fetch('/api/settings/test', {method:'POST'})
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'Test failed')
      setMsg({type: d.authorized?'success':'error',
              text: d.authorized ? `✓ Authorized (${d.state})` : `Instance state: ${d.state}`})
    } catch(e) { setMsg({type:'error', text:e.message}) }
    finally { setTesting(false) }
  }

  return (
    <div className="settings-overlay" onClick={e=>{ if(e.target===e.currentTarget) onClose() }}>
      <div className="settings-panel">
        <div className="settings-hdr">
          <h2>⚙️ Settings</h2>
          <button className="settings-close" onClick={onClose}>✕</button>
        </div>

        {current?.is_configured && (
          <div className="settings-current">
            <span className="phone-dot" style={{background:'#34d399'}}/> GreenAPI connected
            <span className="settings-instance"> Instance: {current.instance_id}</span>
          </div>
        )}

        <div className="settings-body">
          <h3 className="settings-section-title">GreenAPI Credentials</h3>
          <p className="settings-hint">
            Get these from <a href="https://green-api.com" target="_blank" rel="noreferrer">green-api.com</a>
          </p>

          <label className="field">
            <span>Instance ID</span>
            <input className="input" placeholder="710701xxxxxx" value={instanceId} onChange={e=>setInstanceId(e.target.value)}/>
          </label>
          <label className="field">
            <span>API Token</span>
            <input className="input" type="password" placeholder="Enter new token (leave blank to keep current)" value={apiToken} onChange={e=>setApiToken(e.target.value)}/>
            {current?.api_token_masked && <span className="settings-hint">Current: {current.api_token_masked}</span>}
          </label>
          <label className="field">
            <span>Base URL <span className="optional">(optional)</span></span>
            <input className="input" value={baseUrl} onChange={e=>setBaseUrl(e.target.value)}/>
          </label>

          {msg && <div className={`alert ${msg.type}`}>{msg.text}</div>}

          <div className="settings-actions">
            <button className="btn-ghost" onClick={test} disabled={testing}>
              {testing ? <><span className="spinner-dark"/> Testing…</> : '🔌 Test Connection'}
            </button>
            <button className="btn-primary" onClick={save} disabled={saving}>
              {saving ? <><span className="spinner"/> Saving…</> : '💾 Save Credentials'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Recipient manager ─────────────────────────────────────────────────────────
function RecipientManager({ recipients, onChange, csvContacts }) {
  const [val, setVal] = useState('')
  const [err, setErr] = useState('')
  const ref = useRef()

  function add() {
    const v = val.trim().replace(/^\+/,'')
    if (!v) { setErr('Enter phone or group ID'); return }
    if (!isGroupId(v)) {
      const d = v.replace(/\D/g,'')
      if (d.length < 10 || d.length > 15) { setErr('10–15 digits required'); return }
    }
    if (recipients.some(r => (typeof r === 'string' ? r : r.phone) === v)) { setErr('Already in list'); return }
    onChange([...recipients, v])
    setVal(''); setErr('')
    ref.current?.focus()
  }

  function addFromCsv() {
    const phones = csvContacts.map(c => {
      const phone = c.phone
      const name  = c.name || ''
      return name ? `${name}::${phone}` : phone
    }).filter(Boolean)
    const existing = new Set(recipients.map(r => typeof r === 'string' ? r : r))
    const merged = [...recipients, ...phones.filter(p => !existing.has(p))]
    onChange([...new Set(merged)])
  }

  function remove(r) { onChange(recipients.filter(x => x !== r)) }

  const displayPhone = (r) => {
    if (r.includes('::')) return fmtRecipient(r.split('::')[1])
    return fmtRecipient(r)
  }
  const displayName = (r) => r.includes('::') ? r.split('::')[0] : null

  return (
    <div className="recipient-manager">
      <div className="recipient-input-row">
        <input ref={ref} className={`input ${err?'input-err':''}`}
          placeholder="923001234567 or 120363xxx@g.us"
          value={val} onChange={e=>{setVal(e.target.value);setErr('')}}
          onKeyDown={e=>{ if(e.key==='Enter'){e.preventDefault();add()} }}
        />
        <button className="btn-add" onClick={add}>+ Add</button>
      </div>
      {err && <p className="field-err">{err}</p>}
      {csvContacts.length > 0 && (
        <button className="btn-csv-import" onClick={addFromCsv}>
          📋 Add all {csvContacts.length} contacts from CSV (with names)
        </button>
      )}
      {recipients.length === 0 ? (
        <div className="recipient-empty">
          <span className="recipient-empty-icon">📭</span>
          <p>No recipients — default <strong>+{DEFAULT_PHONE}</strong> will be used.</p>
        </div>
      ) : (
        <div className="recipient-list">
          <div className="recipient-list-hdr">
            <span className="badge green">{recipients.length} recipient{recipients.length>1?'s':''}</span>
            <button className="btn-clear-all" onClick={()=>onChange([])}>Clear all</button>
          </div>
          <div className="recipient-chips">
            {recipients.map(r=>(
              <div key={r} className={`chip ${isGroupId(r)?'chip-group':'chip-phone'}`}>
                {displayName(r) && <span className="chip-name">{displayName(r)}</span>}
                <span className="chip-icon">{isGroupId(r)?'👥':'📱'}</span>
                <span className="chip-val">{displayPhone(r)}</span>
                <button className="chip-remove" onClick={()=>remove(r)}>×</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [step,         setStep]         = useState(1)
  const [showSettings, setShowSettings] = useState(false)

  // CSV data
  const [allContacts,      setAllContacts]      = useState([])
  const [filteredContacts, setFilteredContacts] = useState([])
  const [summary,          setSummary]          = useState(null)
  const [uploadErr,        setUploadErr]        = useState('')
  const [uploading,        setUploading]        = useState(false)

  // City filter
  const [cityFilter, setCityFilter] = useState('All')

  // AI step
  const [userQuery,   setUserQuery]   = useState('')
  const [tone,        setTone]        = useState('Friendly')
  const [generating,  setGenerating]  = useState(false)
  const [genErr,      setGenErr]      = useState('')
  const [preview,     setPreview]     = useState(null)
  const [editedMsg,   setEditedMsg]   = useState('')

  // Image upload
  const [imageFile,    setImageFile]    = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [imageUrl,     setImageUrl]     = useState(null)
  const [imgUploading, setImgUploading] = useState(false)

  // Audience / recipients
  const [recipients, setRecipients] = useState([])

  // Send
  const [sending,    setSending]    = useState(false)
  const [sendResult, setSendResult] = useState(null)
  const [sendErr,    setSendErr]    = useState('')

  const effectiveCount = recipients.length || 1

  // ── Unique cities from all contacts ────────────────────────────────────────
  const allCities = ['All', ...Array.from(new Set(allContacts.map(c => c.city).filter(Boolean))).sort()]

  // ── Apply city filter ──────────────────────────────────────────────────────
  function applyFilter(contacts, city) {
    if (!city || city === 'All') return contacts
    return contacts.filter(c => c.city && c.city.toLowerCase() === city.toLowerCase())
  }

  function handleCityChange(city) {
    setCityFilter(city)
    setFilteredContacts(applyFilter(allContacts, city))
  }

  // ── Step 1: Upload CSV ─────────────────────────────────────────────────────
  async function handleUpload(e) {
    const file = e.target.files?.[0]; if (!file) return
    setUploadErr(''); setSummary(null); setAllContacts([]); setFilteredContacts([])
    setPreview(null); setCityFilter('All')
    setUploading(true)
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${API}/upload-contacts`, { method:'POST', body:fd })
      if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed')
      const data = await res.json()
      if (!data.contacts?.length)
        throw new Error(`No valid contacts. ${data.summary.invalid} invalid rows. Check phone numbers include country code.`)
      setAllContacts(data.contacts)
      setFilteredContacts(data.contacts)
      setSummary(data.summary)
      setStep(2)
    } catch(err) { setUploadErr(err.message) }
    finally { setUploading(false) }
  }

  // ── Image upload ───────────────────────────────────────────────────────────
  async function handleImageSelect(e) {
    const file = e.target.files?.[0]; if (!file) return
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
    setImgUploading(true)
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${API}/media/upload`, { method:'POST', body:fd })
      if (!res.ok) throw new Error((await res.json()).detail || 'Image upload failed')
      const data = await res.json()
      setImageUrl(data.url)
    } catch(err) { alert('Image upload failed: ' + err.message) }
    finally { setImgUploading(false) }
  }

  function removeImage() { setImageFile(null); setImagePreview(null); setImageUrl(null) }

  // ── Step 3: AI Generate ────────────────────────────────────────────────────
  async function handleGenerate() {
    setGenErr(''); setGenerating(true); setPreview(null)
    const contacts = filteredContacts.length ? filteredContacts : allContacts
    try {
      const res = await fetch(`${API}/mvp/generate`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          contacts_json: contacts.map(c => ({ name:c.name, phone:c.phone, city:c.city })),
          user_query: userQuery,
          tone,
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Generation failed')
      const data = await res.json()
      setPreview(data)
      setEditedMsg([data.headline, data.message, data.cta].filter(Boolean).join('\n\n'))
    } catch(err) { setGenErr(err.message) }
    finally { setGenerating(false) }
  }

  // ── Step 6: Send ───────────────────────────────────────────────────────────
  async function handleSend() {
    setSendErr(''); setSendResult(null); setSending(true)
    try {
      const res = await fetch(`${API}/mvp/send`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          message:    editedMsg,
          image_url:  imageUrl || null,
          recipients: recipients.length ? recipients : [],
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Send failed')
      setSendResult(await res.json())
    } catch(err) { setSendErr(err.message) }
    finally { setSending(false) }
  }

  function restart() {
    setStep(1); setAllContacts([]); setFilteredContacts([]); setSummary(null)
    setPreview(null); setEditedMsg(''); setSendResult(null); setSendErr('')
    setUploadErr(''); setRecipients([]); setImageFile(null)
    setImagePreview(null); setImageUrl(null); setUserQuery(''); setCityFilter('All')
  }

  const activeContacts = filteredContacts.length ? filteredContacts : allContacts
  const currentStep    = PIPELINE_STEPS[step - 1]

  return (
    <div className="shell">
      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}

      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-icon">💬</span>
          <span className="logo-text">AI B2C</span>
        </div>

        <nav className="nav">
          {PIPELINE_STEPS.map(s => (
            <button key={s.id}
              className={`nav-btn ${step===s.id?'active':''} ${step>s.id?'done':''}`}
              onClick={() => { if (s.id <= step) setStep(s.id) }}
            >
              <span className="nav-icon">{step > s.id ? '✓' : s.icon}</span>
              <span>{s.label}</span>
              {step === s.id && <span className="nav-dot"/>}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="phone-badge">
            <span className="phone-dot"/>
            {recipients.length > 0
              ? <><strong>{recipients.length}</strong> recipient{recipients.length>1?'s':''} set</>
              : <>Default: <strong>+{DEFAULT_PHONE}</strong></>}
          </div>
          <button className="btn-settings" onClick={() => setShowSettings(true)}>
            ⚙️ Settings
          </button>
          <p className="footer-note">AI B2C · MVP Pipeline</p>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main">
        <div className="topbar">
          <div>
            <h2 className="page-title">{currentStep.icon} {currentStep.label}</h2>
            <p className="page-sub">
              {step===1 && 'Upload your contacts CSV to begin'}
              {step===2 && `${allContacts.length} contacts · filtering by city · ${activeContacts.length} selected`}
              {step===3 && 'Describe your campaign — AI generates personalised copy'}
              {step===4 && 'Edit message · upload banner image'}
              {step===5 && `Audience ready · ${effectiveCount} recipient${effectiveCount>1?'s':''}`}
              {step===6 && `Sending to ${effectiveCount} recipient${effectiveCount>1?'s':''}`}
            </p>
          </div>
          <StepBar current={step} />
        </div>

        <div className="card">

          {/* ══ STEP 1: Upload ══ */}
          {step === 1 && (
            <div className="step-body">
              <label className="dropzone">
                <input type="file" accept=".csv" onChange={handleUpload} disabled={uploading}/>
                <div className="dropzone-inner">
                  <div className="dropzone-icon">📂</div>
                  <p className="dropzone-title">{uploading ? 'Uploading…' : 'Drop CSV or click to browse'}</p>
                  <p className="dropzone-hint">Columns: name, phone, city</p>
                </div>
              </label>
              {uploadErr && <div className="alert error">{uploadErr}</div>}
              {summary && (
                <div className="summary-grid">
                  <div className="stat-card blue"><div className="stat-val">{summary.total}</div><div className="stat-lbl">Total Rows</div></div>
                  <div className="stat-card green"><div className="stat-val">{summary.valid}</div><div className="stat-lbl">Valid</div></div>
                  <div className="stat-card yellow"><div className="stat-val">{summary.duplicates}</div><div className="stat-lbl">Dupes</div></div>
                  <div className="stat-card red"><div className="stat-val">{summary.invalid}</div><div className="stat-lbl">Invalid</div></div>
                </div>
              )}
              <div className="actions">
                <button className="btn-primary" onClick={() => setStep(2)} disabled={!allContacts.length}>
                  Next — Filter Data →
                </button>
              </div>
            </div>
          )}

          {/* ══ STEP 2: Filter Data ══ */}
          {step === 2 && (
            <div className="step-body">
              <div className="filter-bar">
                <div className="section-hdr">
                  <h3>Filter by City</h3>
                  <span className="badge green">{activeContacts.length} selected</span>
                </div>
                <div className="city-pills">
                  {allCities.map(city => (
                    <button key={city}
                      className={`city-pill ${cityFilter === city ? 'active' : ''}`}
                      onClick={() => handleCityChange(city)}
                    >
                      {city === 'All' ? '🌍 All' : `📍 ${city}`}
                      <span className="city-count">
                        {city === 'All' ? allContacts.length : allContacts.filter(c => c.city === city).length}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {activeContacts.length === 0
                ? <div className="alert error">No contacts match the selected city filter.</div>
                : <ContactsTable contacts={activeContacts} />
              }

              <div className="info-box">
                <span>💡</span>
                <span>CSV data is <strong>AI context</strong>. Control who receives the message in the <strong>Audience</strong> step. Client names will be personalised in the message.</span>
              </div>
              <div className="actions row">
                <button className="btn-ghost" onClick={() => setStep(1)}>← Back</button>
                <button className="btn-primary" onClick={() => setStep(3)} disabled={!activeContacts.length}>
                  Next — AI Generate →
                </button>
              </div>
            </div>
          )}

          {/* ══ STEP 3: AI Generate ══ */}
          {step === 3 && (
            <div className="step-body">
              <div className="ai-form">
                <label className="field">
                  <span>Campaign Brief <span className="optional">(tell AI what to write)</span></span>
                  <textarea className="input" rows={3}
                    placeholder="e.g. Clothing store summer sale — 30% off all items this weekend only. Target young women in Lahore."
                    value={userQuery} onChange={e => setUserQuery(e.target.value)}
                  />
                </label>
                <label className="field">
                  <span>Tone</span>
                  <select className="input" value={tone} onChange={e => setTone(e.target.value)}>
                    {['Friendly','Professional','Urgent','Casual','Exciting'].map(t=><option key={t}>{t}</option>)}
                  </select>
                </label>

                <div className="csv-context-pill">
                  <strong>AI context from CSV:</strong> {activeContacts.length} contacts
                  {activeContacts[0]?.city && ` · ${[...new Set(activeContacts.map(c=>c.city).filter(Boolean))].slice(0,3).join(', ')}`}
                  {activeContacts[0]?.name && ` · names like "${activeContacts[0].name}"`}
                  {activeContacts.some(c=>c.name) && <span className="name-badge"> · ✨ Will personalise with client names</span>}
                </div>

                <button className="btn-ai" onClick={handleGenerate} disabled={generating}>
                  {generating ? <><span className="spinner"/> Generating…</> : <><span>✨</span> Generate Campaign with AI</>}
                </button>
              </div>

              {genErr && <div className="alert error">{genErr}</div>}

              {preview && (
                <div className="generated-result">
                  <div className="gen-hdr">
                    <span className="gen-badge">✨ AI Generated</span>
                    <div className="score-pills">
                      <span className={`pill ${preview.spam_score<30?'green':preview.spam_score<60?'yellow':'red'}`}>Spam: {preview.spam_score}</span>
                      <span className="pill blue">Quality: {preview.quality}</span>
                    </div>
                  </div>
                  <div className="gen-fields">
                    <div className="gen-field"><span className="gen-lbl">Headline</span><span>{preview.headline}</span></div>
                    <div className="gen-field"><span className="gen-lbl">Message</span><span>{preview.message}</span></div>
                    <div className="gen-field"><span className="gen-lbl">CTA</span><span>{preview.cta}</span></div>
                    {preview.emojis && <div className="gen-field"><span className="gen-lbl">Emojis</span><span>{preview.emojis}</span></div>}
                  </div>
                  {editedMsg.includes('{{name}}') && (
                    <div className="name-hint">
                      ✨ <code>{'{{name}}'}</code> will be replaced with each contact's real name when sending.
                    </div>
                  )}
                </div>
              )}

              <div className="actions row">
                <button className="btn-ghost" onClick={() => setStep(2)}>← Back</button>
                <button className="btn-primary" onClick={() => setStep(4)} disabled={!preview}>Next — Preview →</button>
              </div>
            </div>
          )}

          {/* ══ STEP 4: Preview + Image ══ */}
          {step === 4 && (
            <div className="step-body preview-layout">
              <div className="preview-left">
                <h3>Edit Message</h3>
                <p className="hint">Use <code>{'{{name}}'}</code> where you want the client's name.</p>
                <textarea className="msg-editor" value={editedMsg} onChange={e => setEditedMsg(e.target.value)}/>
                <div className="msg-meta">
                  <span>{editedMsg.length} chars</span>
                  {editedMsg.includes('{{name}}') && <span className="name-badge">✨ Personalised</span>}
                </div>

                <div className="img-upload-section">
                  <h3>Banner Image <span className="optional">(optional)</span></h3>
                  {!imagePreview ? (
                    <label className="img-dropzone">
                      <input type="file" accept="image/*" onChange={handleImageSelect}/>
                      <div className="img-dropzone-inner">
                        <span className="img-icon">🖼️</span>
                        <span>{imgUploading ? 'Uploading…' : 'Click to upload image'}</span>
                        <span className="img-hint">JPG, PNG, GIF · max 10MB</span>
                      </div>
                    </label>
                  ) : (
                    <div className="img-preview-wrap">
                      <img src={imagePreview} alt="banner" className="img-preview-thumb"/>
                      <div className="img-preview-info">
                        <span>{imageFile?.name}</span>
                        {imageUrl
                          ? <span className="pill green">✓ Uploaded</span>
                          : <span className="pill yellow">Uploading…</span>}
                        <button className="btn-remove-img" onClick={removeImage}>Remove</button>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="preview-right">
                <h3>WhatsApp Preview</h3>
                <p className="hint">Shows <code>{'{{name}}'}</code> as placeholder</p>
                <WaBubble message={editedMsg} imagePreview={imagePreview}/>
              </div>

              <div className="actions row full">
                <button className="btn-ghost" onClick={() => setStep(3)}>← Back</button>
                <button className="btn-primary" onClick={() => setStep(5)} disabled={!editedMsg.trim()}>
                  Next — Set Audience →
                </button>
              </div>
            </div>
          )}

          {/* ══ STEP 5: Audience ══ */}
          {step === 5 && (
            <div className="step-body">
              <div className="section-hdr">
                <h3>Select Audience</h3>
                <span className="badge blue">{activeContacts.length} from filtered CSV</span>
              </div>

              <div className="audience-options">
                <div className="audience-card" onClick={() => { setRecipients([]); }}>
                  <div className="aud-icon">🎯</div>
                  <div>
                    <strong>Default test number</strong>
                    <p className="hint">Send to +{DEFAULT_PHONE} only (safe testing)</p>
                  </div>
                  <div className={`aud-radio ${recipients.length===0?'selected':''}`}/>
                </div>
                <div className="audience-card" onClick={() => {
                  const entries = activeContacts.map(c => c.name ? `${c.name}::${c.phone}` : c.phone)
                  setRecipients([...new Set(entries)])
                }}>
                  <div className="aud-icon">📋</div>
                  <div>
                    <strong>All filtered contacts ({activeContacts.length})</strong>
                    <p className="hint">Send personalised message to each contact in filtered CSV</p>
                  </div>
                  <div className={`aud-radio ${recipients.length===activeContacts.length?'selected':''}`}/>
                </div>
              </div>

              <div className="divider-or">or add manually</div>

              <RecipientManager
                recipients={recipients}
                onChange={setRecipients}
                csvContacts={activeContacts}
              />

              {imageUrl && (
                <div className="info-box">
                  <span>🖼️</span>
                  <span>Banner image attached — will be sent as image + caption to each recipient.</span>
                </div>
              )}

              <div className="actions row">
                <button className="btn-ghost" onClick={() => setStep(4)}>← Back</button>
                <button className="btn-primary" onClick={() => setStep(6)}>
                  Next — Send to {effectiveCount} recipient{effectiveCount>1?'s':''} →
                </button>
              </div>
            </div>
          )}

          {/* ══ STEP 6: Confirm Send ══ */}
          {step === 6 && !sendResult && (
            <div className="step-body send-layout">
              <div className="send-summary">
                <div className="send-row">
                  <span className="send-lbl">Recipients</span>
                  <span className="send-val">
                    {recipients.length > 0
                      ? <>{recipients.length} custom recipient{recipients.length>1?'s':''}</>
                      : <>Default: <span className="mono">+{DEFAULT_PHONE}</span></>}
                  </span>
                </div>
                <div className="send-row">
                  <span className="send-lbl">Image attached</span>
                  <span className="send-val">{imageUrl ? <span className="pill green">Yes</span> : <span className="pill">No</span>}</span>
                </div>
                <div className="send-row">
                  <span className="send-lbl">Personalised names</span>
                  <span className="send-val">{editedMsg.includes('{{name}}') ? <span className="pill green">Yes</span> : <span className="pill">No</span>}</span>
                </div>
                <div className="send-row">
                  <span className="send-lbl">Anti-spam delay</span>
                  <span className="send-val">1–10s random</span>
                </div>
              </div>

              {imagePreview && <img src={imagePreview} alt="banner" className="send-img-thumb"/>}

              <div className="msg-preview-box">
                <p className="msg-preview-label">Message</p>
                <pre className="msg-preview-text">{editedMsg}</pre>
              </div>

              {sendErr && <div className="alert error">{sendErr}</div>}
              <div className="actions row">
                <button className="btn-ghost" onClick={() => setStep(5)}>← Back</button>
                <button className="btn-send" onClick={handleSend} disabled={sending}>
                  {sending
                    ? <><span className="spinner"/> Sending to {effectiveCount}…</>
                    : <><span>📨</span> Send to {effectiveCount} recipient{effectiveCount>1?'s':''}</>}
                </button>
              </div>
            </div>
          )}

          {/* ══ SUCCESS ══ */}
          {step === 6 && sendResult && (
            <div className="step-body success-layout">
              <div className="success-icon">{sendResult.failed===0?'🎉':'⚠️'}</div>
              <h2 className="success-title">
                {sendResult.failed===0 ? 'All Sent!' : `${sendResult.sent}/${sendResult.total} Sent`}
              </h2>
              <p className="success-sub">{sendResult.sent} sent · {sendResult.failed} failed · {sendResult.total} total</p>
              <div className="result-table-wrap">
                <table className="result-table">
                  <thead><tr><th>Name</th><th>Recipient</th><th>Status</th><th>Delay</th><th>Message ID</th></tr></thead>
                  <tbody>
                    {sendResult.results.map((r,i)=>(
                      <tr key={i}>
                        <td>{r.name||'—'}</td>
                        <td className="mono">{fmtRecipient(r.recipient)}</td>
                        <td><span className={`pill ${r.status==='sent'?'green':'red'}`}>{r.status}</span></td>
                        <td>{r.delay_seconds}s</td>
                        <td className="mono small">{r.message_id||r.error||'—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button className="btn-primary" onClick={restart}>← New Campaign</button>
            </div>
          )}

        </div>
      </main>
    </div>
  )
}
