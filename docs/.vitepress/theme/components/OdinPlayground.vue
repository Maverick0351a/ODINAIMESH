<template>
  <div class="odin-playground">
    <div class="playground-header">
      <h3>🚀 Try ODIN Protocol Now</h3>
      <p>Test secure AI-to-AI communication with live models. No registration required for demo.</p>
    </div>

    <div class="tabs">
      <button 
        :class="{ active: tab === 'demo' }" 
        @click="tab = 'demo'"
        class="tab-button"
      >
        <span class="tab-icon">⚡</span>
        Demo Model
        <span class="tab-badge">Free</span>
      </button>
      <button 
        :class="{ active: tab === 'byom' }" 
        @click="tab = 'byom'"
        class="tab-button"
      >
        <span class="tab-icon">🔑</span>
        Bring Your Own Model
        <span class="tab-badge">BYOM</span>
      </button>
    </div>

    <!-- Demo Panel -->
    <div v-if="tab === 'demo'" class="panel demo-panel">
      <div class="panel-header">
        <h4>Zero-friction demo with built-in models</h4>
        <div class="limits-info">
          <span class="limit-badge">⏱️ 10 requests/hour</span>
          <span class="limit-badge">📝 500 tokens max</span>
        </div>
      </div>

      <div class="form-group">
        <label>Model</label>
        <select v-model="demo.model" class="select-input">
          <option value="gemini-1.5-flash">Gemini 1.5 Flash (Recommended)</option>
          <option value="gpt-4o-mini">GPT-4o Mini</option>
        </select>
      </div>

      <div class="form-group">
        <label>Prompt</label>
        <textarea 
          v-model="demo.prompt" 
          rows="4" 
          placeholder="Try: 'Transform this invoice data to ISO 20022 format: {amount: 1000, currency: EUR, vendor: {iban: DE89370400440532013000}}'"
          class="textarea-input"
        ></textarea>
      </div>

      <button 
        :disabled="loading || !demo.prompt.trim()" 
        @click="runDemo"
        class="run-button demo-button"
      >
        <span v-if="loading" class="loading-spinner">⏳</span>
        <span v-else class="button-icon">🚀</span>
        {{ loading ? 'Running...' : 'Run Demo' }}
      </button>
    </div>

    <!-- BYOM Panel -->
    <div v-else class="panel byom-panel">
      <div class="panel-header">
        <h4>Use your own AI model credentials</h4>
        <div class="security-badge">
          <span class="security-icon">🔒</span>
          Keys never stored • 15min token expiry
        </div>
      </div>

      <div class="provider-grid">
        <div class="form-group">
          <label>Provider</label>
          <select v-model="byom.provider" class="select-input">
            <option value="openai">OpenAI</option>
            <option value="gemini_api">Google Gemini</option>
            <option value="anthropic">Anthropic</option>
            <option value="mistral">Mistral AI</option>
            <option value="vertex">Google Vertex</option>
            <option value="bedrock">AWS Bedrock</option>
          </select>
        </div>
        <div class="form-group">
          <label>Model</label>
          <input 
            v-model="byom.model" 
            placeholder="e.g., gpt-4o-mini"
            class="text-input"
          />
        </div>
      </div>

      <div class="key-section">
        <label>Provider API Key (not stored)</label>
        <div class="key-input-row">
          <input 
            v-model="byom.key" 
            type="password" 
            placeholder="Paste your API key here..."
            class="key-input"
          />
          <button 
            :disabled="loading || !byom.key.trim()" 
            @click="mintToken"
            class="connect-button"
          >
            <span v-if="loading" class="loading-spinner">⏳</span>
            <span v-else class="button-icon">🔗</span>
            {{ loading ? 'Connecting...' : 'Connect' }}
          </button>
        </div>
        <div v-if="byok.exp" class="token-status">
          <span class="status-icon">✅</span>
          Connected • Token expires {{ formatExpiry(byok.exp) }}
        </div>
      </div>

      <div class="form-group">
        <label>Prompt</label>
        <textarea 
          v-model="byom.prompt" 
          rows="4" 
          placeholder="Test your model with any prompt..."
          class="textarea-input"
        ></textarea>
      </div>

      <button 
        :disabled="loading || !byok.token || !byom.prompt.trim()" 
        @click="runByom"
        class="run-button byom-button"
      >
        <span v-if="loading" class="loading-spinner">⏳</span>
        <span v-else class="button-icon">🤖</span>
        {{ loading ? 'Running...' : 'Run with My Model' }}
      </button>
    </div>

    <!-- Output Section -->
    <div v-if="output || meta" class="results-section">
      <div v-if="output" class="output-panel">
        <h4>
          <span class="result-icon">💬</span>
          AI Response
        </h4>
        <div class="output-content">
          <pre>{{ output }}</pre>
        </div>
      </div>
      
      <div v-if="meta" class="meta-panel">
        <h4>
          <span class="result-icon">📊</span>
          Execution Details
        </h4>
        <div class="meta-content">
          <pre>{{ meta }}</pre>
        </div>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="error" class="error-panel">
      <h4>
        <span class="result-icon">❌</span>
        Error
      </h4>
      <div class="error-content">
        {{ error }}
      </div>
    </div>

    <!-- Research Engine CTA -->
    <div class="research-cta">
      <div class="cta-header">
        <h4>🔬 Ready for More Advanced Research?</h4>
        <p>Run controlled experiments with datasets, benchmarks, and reproducible receipts.</p>
      </div>
      <div class="cta-features">
        <div class="feature">
          <span class="feature-icon">📊</span>
          <div>
            <strong>Upload Datasets</strong>
            <p>Test with your own JSON/CSV data</p>
          </div>
        </div>
        <div class="feature">
          <span class="feature-icon">🧪</span>
          <div>
            <strong>A/B Experiments</strong>
            <p>Compare models, maps, and policies</p>
          </div>
        </div>
        <div class="feature">
          <span class="feature-icon">🧾</span>
          <div>
            <strong>Cryptographic Receipts</strong>
            <p>Reproduce any result from trace ID</p>
          </div>
        </div>
      </div>
      <button class="cta-button" @click="showResearchModal = true">
        <span class="button-icon">🚀</span>
        Try Research Engine
      </button>
    </div>

    <!-- Research Engine Modal -->
    <div v-if="showResearchModal" class="modal-overlay" @click="showResearchModal = false">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h3>🔬 ODIN Research Engine</h3>
          <button class="close-button" @click="showResearchModal = false">×</button>
        </div>
        <div class="modal-content">
          <p>Run controlled experiments across models and maps with cryptographic receipts, BYOM support, and built-in benchmarks.</p>
          
          <div class="research-features">
            <div class="feature-list">
              <div class="feature-item">
                <span class="check-icon">✅</span>
                <strong>Project Sandboxes</strong> - Isolated environments with quotas
              </div>
              <div class="feature-item">
                <span class="check-icon">✅</span>
                <strong>BYOM Tokens</strong> - 15-min secure tokens, keys never stored
              </div>
              <div class="feature-item">
                <span class="check-icon">✅</span>
                <strong>Built-in Benchmarks</strong> - Coverage, latency, cost analysis
              </div>
              <div class="feature-item">
                <span class="check-icon">✅</span>
                <strong>Receipt Chains</strong> - Cryptographic proof of execution
              </div>
            </div>
          </div>

          <div class="pricing-tiers">
            <div class="tier">
              <h4>Free Research</h4>
              <ul>
                <li>1 project</li>
                <li>1,000 requests/mo</li>
                <li>BYOM only</li>
                <li>Basic benchmarks</li>
              </ul>
              <button class="tier-button free" @click="createProject('free')">
                Start Free
              </button>
            </div>
            <div class="tier recommended">
              <div class="tier-badge">Recommended</div>
              <h4>Pro Research</h4>
              <ul>
                <li>3 projects</li>
                <li>50k requests/mo</li>
                <li>Router policies</li>
                <li>Data export</li>
              </ul>
              <button class="tier-button pro" @click="createProject('pro')">
                $99/mo
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Examples Section -->
    <div class="examples-section">
      <h4>💡 Try These Examples</h4>
      <div class="examples-grid">
        <div class="example-card" @click="loadExample('payment')">
          <h5>🏦 Payment Processing</h5>
          <p>Transform invoice to ISO 20022 banking format</p>
        </div>
        <div class="example-card" @click="loadExample('data')">
          <h5>📊 Data Analysis</h5>
          <p>Analyze JSON data and extract insights</p>
        </div>
        <div class="example-card" @click="loadExample('translation')">
          <h5>🌐 Format Translation</h5>
          <p>Convert between different data formats</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

// Configuration
const GATEWAY = (import.meta.env.VITE_ODIN_GATEWAY_URL || 'https://gateway.odin-protocol.dev').replace(/\/$/, '')

// Reactive state
const tab = ref('demo')
const loading = ref(false)
const output = ref('')
const meta = ref('')
const error = ref('')
const showResearchModal = ref(false)

// Demo state
const demo = ref({ 
  model: 'gemini-1.5-flash', 
  prompt: '' 
})

// BYOM state
const byom = ref({ 
  provider: 'openai', 
  model: 'gpt-4o-mini', 
  key: '', 
  prompt: '' 
})

const byok = ref({ 
  token: '', 
  exp: '' 
})

// Example prompts
const examples = {
  payment: {
    prompt: `Transform this invoice to ISO 20022 pain.001 format:

{
  "invoice_id": "INV-2024-001",
  "amount": 5000.00,
  "currency": "EUR", 
  "vendor": {
    "name": "ACME Software GmbH",
    "iban": "DE89370400440532013000",
    "bic": "COBADEFFXXX"
  },
  "buyer": {
    "name": "TechCorp Ltd",
    "reference": "PO-2024-Q1"
  }
}

Please return a valid ISO 20022 pain.001 XML message structure.`
  },
  data: {
    prompt: `Analyze this sales data and provide key insights:

{
  "sales": [
    {"month": "Jan", "revenue": 120000, "customers": 340},
    {"month": "Feb", "revenue": 135000, "customers": 380}, 
    {"month": "Mar", "revenue": 142000, "customers": 420}
  ],
  "costs": [
    {"month": "Jan", "marketing": 25000, "operations": 45000},
    {"month": "Feb", "marketing": 28000, "operations": 47000},
    {"month": "Mar", "marketing": 32000, "operations": 49000}
  ]
}

Provide growth trends, profit margins, and recommendations.`
  },
  translation: {
    prompt: `Convert this CSV-style data to a JSON API response format:

Name,Email,Role,Department,Salary
John Smith,john@company.com,Engineer,Engineering,95000
Jane Doe,jane@company.com,Manager,Sales,110000
Bob Wilson,bob@company.com,Analyst,Finance,75000

Create a proper REST API response with metadata, pagination info, and formatted employee records.`
  }
}

// Utility functions
function traceId() {
  return crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2)
}

function formatExpiry(exp) {
  const date = new Date(exp)
  const now = new Date()
  const diffMin = Math.round((date - now) / 60000)
  return diffMin > 0 ? `in ${diffMin} min` : 'expired'
}

function clearResults() {
  output.value = ''
  meta.value = ''
  error.value = ''
}

function loadExample(type) {
  if (examples[type]) {
    const example = examples[type]
    if (tab.value === 'demo') {
      demo.value.prompt = example.prompt
    } else {
      byom.value.prompt = example.prompt
    }
    clearResults()
  }
}

// BYOK token management
async function mintToken() {
  loading.value = true
  clearResults()
  
  try {
    const res = await fetch(`${GATEWAY}/v1/byok/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: byom.value.provider,
        api_key: byom.value.key,
        model: byom.value.model,
        ttl_seconds: 900
      }),
      credentials: 'omit',
      mode: 'cors'
    })
    
    if (!res.ok) {
      const errorData = await res.json()
      throw new Error(errorData.detail || `Token creation failed: ${res.status}`)
    }
    
    const data = await res.json()
    byok.value.token = data.byok_token
    byok.value.exp = data.exp
    
    // Clear the API key from memory immediately
    byom.value.key = ''
    
  } catch (e) {
    error.value = `Connection failed: ${e.message}`
  } finally {
    loading.value = false
  }
}

// Demo execution
async function runDemo() {
  await runInvoke('demo')
}

// BYOM execution
async function runByom() {
  await runInvoke('byom')
}

// Research Engine functions
async function createProject(tier) {
  loading.value = true
  
  try {
    const projectName = `Research Project ${Math.random().toString(36).slice(2, 8)}`
    
    const res = await fetch(`${GATEWAY}/v1/projects`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-ODIN-Agent': 'did:odin:playground'
      },
      body: JSON.stringify({
        name: projectName,
        description: `${tier} tier research project`,
        tier: tier
      }),
      credentials: 'omit',
      mode: 'cors'
    })
    
    if (!res.ok) {
      const errorData = await res.json()
      throw new Error(errorData.detail || `Project creation failed: ${res.status}`)
    }
    
    const project = await res.json()
    
    // Store project ID locally for demo
    localStorage.setItem('odin_research_project', JSON.stringify(project))
    
    showResearchModal.value = false
    
    // Show success message
    output.value = `Research project created successfully!\n\nProject ID: ${project.id}\nTier: ${project.tier}\nQuota: ${project.quota_requests_limit} requests/month`
    
    meta.value = JSON.stringify({
      project_id: project.id,
      created_at: project.created_at,
      tier: project.tier,
      next_steps: [
        "Upload a dataset (JSON/CSV)",
        "Create an experiment",
        "Run controlled tests with receipts"
      ]
    }, null, 2)
    
  } catch (e) {
    error.value = `Project creation failed: ${e.message}`
  } finally {
    loading.value = false
  }
}

// Main execution function
async function runInvoke(mode) {
  loading.value = true
  clearResults()
  
  try {
    const isByom = mode === 'byom'
    const currentTraceId = traceId()
    
    const body = isByom ? {
      byok_token: byok.value.token,
      provider: byom.value.provider,
      model: byom.value.model,
      input_type: 'plain_text',
      payload: { prompt: byom.value.prompt },
      options: { temperature: 0 }
    } : {
      prompt: demo.value.prompt,
      model: demo.value.model,
      temperature: 0
    }

    const url = isByom ? `${GATEWAY}/v1/byok/mesh` : `${GATEWAY}/v1/demo/mesh`
    
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-ODIN-Trace-Id': currentTraceId,
        'X-ODIN-Agent': 'did:odin:playground',
        'X-ODIN-Target-Realm': 'business'
      },
      body: JSON.stringify(body),
      credentials: 'omit',
      mode: 'cors'
    })
    
    const data = await res.json()
    
    if (!res.ok) {
      throw new Error(data.detail || `HTTP ${res.status}`)
    }
    
    // Format output
    const result = data.result || data
    output.value = result.text || JSON.stringify(result, null, 2)
    
    // Format metadata
    const metaInfo = {
      ok: data.ok,
      trace_id: data.trace_id,
      model: isByom ? byom.value.model : demo.value.model,
      provider: result.provider || (isByom ? byom.value.provider : 'demo'),
      tokens_in: result.tokens_in || 0,
      tokens_out: result.tokens_out || 0
    }
    
    if (data.receipt_cid) metaInfo.receipt_cid = data.receipt_cid
    if (!isByom && data.usage_limits) metaInfo.usage_limits = data.usage_limits
    
    meta.value = JSON.stringify(metaInfo, null, 2)
    
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.odin-playground {
  max-width: 900px;
  margin: 2rem auto;
  padding: 2rem;
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  background: var(--vp-c-bg-soft);
}

.playground-header {
  text-align: center;
  margin-bottom: 2rem;
}

.playground-header h3 {
  margin: 0 0 0.5rem 0;
  color: var(--vp-c-brand);
}

.playground-header p {
  margin: 0;
  color: var(--vp-c-text-2);
}

.tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 2rem;
  border-bottom: 1px solid var(--vp-c-divider);
}

.tab-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  transition: all 0.2s ease;
  font-weight: 500;
}

.tab-button:hover {
  background: var(--vp-c-bg);
}

.tab-button.active {
  background: var(--vp-c-bg);
  border-bottom: 2px solid var(--vp-c-brand);
  color: var(--vp-c-brand);
}

.tab-icon {
  font-size: 1.1rem;
}

.tab-badge {
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--vp-c-brand-soft);
  color: var(--vp-c-brand);
}

.panel {
  display: grid;
  gap: 1.5rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--vp-c-divider-light);
}

.panel-header h4 {
  margin: 0;
  color: var(--vp-c-text-1);
}

.limits-info {
  display: flex;
  gap: 0.5rem;
}

.limit-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  background: var(--vp-c-yellow-soft);
  color: var(--vp-c-yellow);
}

.security-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  background: var(--vp-c-green-soft);
  color: var(--vp-c-green);
  font-size: 0.85rem;
  font-weight: 500;
}

.security-icon {
  font-size: 1rem;
}

.form-group {
  display: grid;
  gap: 0.5rem;
}

.form-group label {
  font-weight: 600;
  color: var(--vp-c-text-1);
}

.provider-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.select-input,
.text-input,
.textarea-input,
.key-input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--vp-c-divider);
  border-radius: 6px;
  background: var(--vp-c-bg);
  color: var(--vp-c-text-1);
  font-family: inherit;
  transition: border-color 0.2s ease;
}

.select-input:focus,
.text-input:focus,
.textarea-input:focus,
.key-input:focus {
  outline: none;
  border-color: var(--vp-c-brand);
}

.textarea-input {
  resize: vertical;
  min-height: 100px;
  font-family: 'Courier New', monospace;
}

.key-section {
  display: grid;
  gap: 0.5rem;
}

.key-section label {
  font-weight: 600;
  color: var(--vp-c-text-1);
}

.key-input-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.75rem;
  align-items: center;
}

.connect-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  border: 1px solid var(--vp-c-brand);
  border-radius: 6px;
  background: var(--vp-c-brand);
  color: white;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.connect-button:hover:not(:disabled) {
  background: var(--vp-c-brand-dark);
}

.connect-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.token-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  background: var(--vp-c-green-soft);
  color: var(--vp-c-green);
  font-size: 0.85rem;
  font-weight: 500;
}

.status-icon {
  font-size: 1rem;
}

.run-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1rem 2rem;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.demo-button {
  background: var(--vp-c-brand);
  color: white;
}

.demo-button:hover:not(:disabled) {
  background: var(--vp-c-brand-dark);
  transform: translateY(-1px);
}

.byom-button {
  background: var(--vp-c-purple);
  color: white;
}

.byom-button:hover:not(:disabled) {
  background: var(--vp-c-purple-dark);
  transform: translateY(-1px);
}

.run-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.button-icon {
  font-size: 1.2rem;
}

.loading-spinner {
  font-size: 1.2rem;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.results-section {
  display: grid;
  gap: 1.5rem;
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid var(--vp-c-divider);
}

.output-panel,
.meta-panel,
.error-panel {
  display: grid;
  gap: 1rem;
}

.output-panel h4,
.meta-panel h4,
.error-panel h4 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  color: var(--vp-c-text-1);
}

.result-icon {
  font-size: 1.1rem;
}

.output-content,
.meta-content,
.error-content {
  padding: 1rem;
  border-radius: 6px;
  background: var(--vp-c-bg);
  border: 1px solid var(--vp-c-divider);
}

.output-content pre,
.meta-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Courier New', monospace;
  font-size: 0.9rem;
  line-height: 1.5;
}

.error-content {
  background: var(--vp-c-red-soft);
  border-color: var(--vp-c-red);
  color: var(--vp-c-red-dark);
}

.examples-section {
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid var(--vp-c-divider);
}

.examples-section h4 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-text-1);
}

.examples-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.example-card {
  padding: 1rem;
  border: 1px solid var(--vp-c-divider);
  border-radius: 6px;
  background: var(--vp-c-bg);
  cursor: pointer;
  transition: all 0.2s ease;
}

.example-card:hover {
  border-color: var(--vp-c-brand);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.example-card h5 {
  margin: 0 0 0.5rem 0;
  color: var(--vp-c-brand);
  font-size: 0.9rem;
}

.example-card p {
  margin: 0;
  color: var(--vp-c-text-2);
  font-size: 0.85rem;
  line-height: 1.4;
}

@media (max-width: 768px) {
  .odin-playground {
    margin: 1rem;
    padding: 1.5rem;
  }
  
  .provider-grid {
    grid-template-columns: 1fr;
  }
  
  .key-input-row {
    grid-template-columns: 1fr;
  }
  
  .panel-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }
  
  .examples-grid {
    grid-template-columns: 1fr;
  }
}

/* Research Engine Styles */
.research-cta {
  margin-top: 2rem;
  padding: 2rem;
  border: 2px solid var(--vp-c-brand);
  border-radius: 12px;
  background: linear-gradient(135deg, var(--vp-c-brand-soft) 0%, var(--vp-c-bg-soft) 100%);
}

.cta-header {
  text-align: center;
  margin-bottom: 1.5rem;
}

.cta-header h4 {
  margin: 0 0 0.5rem 0;
  color: var(--vp-c-brand);
  font-size: 1.3rem;
}

.cta-header p {
  margin: 0;
  color: var(--vp-c-text-2);
}

.cta-features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.feature {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 1rem;
  border-radius: 8px;
  background: var(--vp-c-bg);
}

.feature-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.feature strong {
  display: block;
  margin-bottom: 0.25rem;
  color: var(--vp-c-text-1);
}

.feature p {
  margin: 0;
  color: var(--vp-c-text-2);
  font-size: 0.9rem;
}

.cta-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  width: 100%;
  padding: 1rem 2rem;
  border: none;
  border-radius: 8px;
  background: var(--vp-c-brand);
  color: white;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cta-button:hover {
  background: var(--vp-c-brand-dark);
  transform: translateY(-2px);
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal {
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
  background: var(--vp-c-bg);
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid var(--vp-c-divider);
}

.modal-header h3 {
  margin: 0;
  color: var(--vp-c-brand);
}

.close-button {
  width: 2rem;
  height: 2rem;
  border: none;
  background: transparent;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--vp-c-text-2);
  border-radius: 4px;
  transition: all 0.2s ease;
}

.close-button:hover {
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
}

.modal-content {
  padding: 2rem;
}

.modal-content p {
  margin: 0 0 2rem 0;
  color: var(--vp-c-text-2);
  line-height: 1.6;
}

.research-features {
  margin-bottom: 2rem;
}

.feature-list {
  display: grid;
  gap: 0.75rem;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 6px;
  background: var(--vp-c-bg-soft);
}

.check-icon {
  font-size: 1rem;
  color: var(--vp-c-green);
}

.pricing-tiers {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.tier {
  position: relative;
  padding: 1.5rem;
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  background: var(--vp-c-bg-soft);
  text-align: center;
}

.tier.recommended {
  border-color: var(--vp-c-brand);
  transform: scale(1.05);
}

.tier-badge {
  position: absolute;
  top: -0.5rem;
  left: 50%;
  transform: translateX(-50%);
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  background: var(--vp-c-brand);
  color: white;
  font-size: 0.75rem;
  font-weight: 600;
}

.tier h4 {
  margin: 0 0 1rem 0;
  color: var(--vp-c-text-1);
}

.tier ul {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem 0;
}

.tier li {
  padding: 0.25rem 0;
  color: var(--vp-c-text-2);
  font-size: 0.9rem;
}

.tier-button {
  width: 100%;
  padding: 0.75rem;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tier-button.free {
  background: var(--vp-c-bg);
  border: 1px solid var(--vp-c-brand);
  color: var(--vp-c-brand);
}

.tier-button.free:hover {
  background: var(--vp-c-brand-soft);
}

.tier-button.pro {
  background: var(--vp-c-brand);
  color: white;
}

.tier-button.pro:hover {
  background: var(--vp-c-brand-dark);
}

@media (max-width: 768px) {
  .cta-features {
    grid-template-columns: 1fr;
  }
  
  .pricing-tiers {
    grid-template-columns: 1fr;
  }
  
  .tier.recommended {
    transform: none;
  }
  
  .modal {
    margin: 1rem;
    max-height: calc(100vh - 2rem);
  }
  
  .modal-content {
    padding: 1.5rem;
  }
}
</style>
