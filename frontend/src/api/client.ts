import axios from 'axios'
import i18n from 'i18next'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 90000,
})

// Attach JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 → redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export default api

// ── Asset Relationships ──────────────────────────────────────────

export const getAssetHierarchy = (id: number) =>
  api.get(`/assets/${id}/hierarchy`)

export const listRelationships = (params?: { asset_id?: number }) =>
  api.get('/asset-relationships', { params })

export const createRelationship = (data: {
  parent_id: number
  child_id: number
  relation_type: string
  description?: string
}) => api.post('/asset-relationships', data)

export const deleteRelationship = (id: number) =>
  api.delete(`/asset-relationships/${id}`)

// ── AI & Executive Dashboard ─────────────────────────────────────

export const getExecutiveDashboard = () =>
  api.get('/ai/dashboard')

export const getLLMConfig = () =>
  api.get('/ai/config')

export const updateLLMConfig = (data: {
  provider?: string
  api_key?: string
  base_url?: string
  model?: string
  enabled?: boolean
}) => api.put('/ai/config', data)

export interface LLMConfigResponse {
  id: number
  provider: string
  api_key_set: boolean
  base_url: string | null
  model: string
  enabled: boolean
  created_at: string
}

export const generateAIReport = (data: {
  asset_id?: number
  scan_job_id?: number
  report_type?: string
  lang?: string
}) => api.post('/ai/report', data)

export const naturalLanguageSearch = (q: string) =>
  api.post('/ai/search', null, { params: { q } })

// ── Identity Threat Analysis ─────────────────────────────────────────

export interface ThreatLayerSignal {
  type: string
  detail: string
  severity: string
  evidence?: string
  node_id?: string
  snapshot_id?: number
  mitre_id?: string
  mitre_ids?: string[]
  mitre_tactic?: string
  mitre_tactic_label?: string
  mitre_confidence?: number
  mitre_rationale?: string
  mitre_detection_opportunity?: string
  mitre_remediation?: string
}

export interface ThreatNode {
  id: string
  snapshot_id: number
  username: string
  uid_sid: string
  asset_id: number
  asset_code?: string
  ip?: string
  hostname?: string
  is_admin: boolean
  lifecycle: string
  last_login?: string | null
  sudo_config?: Record<string, unknown>
  raw_info?: Record<string, unknown>
  groups?: string[]
  shell?: string | null
  home_dir?: string | null
  account_status?: string
  identity_id?: number | null
  account_score: number
  account_level: string
  nhi_type?: string
}

export interface ThreatEdge {
  source: string
  target: string
  edge_type: string
  weight: number
}

export interface ThreatGraphData {
  nodes: ThreatNode[]
  edges: ThreatEdge[]
}

export interface ThreatAccountSignal {
  id: number
  analysis_id: number
  snapshot_id?: number
  username: string
  asset_id: number
  asset_code?: string
  semiotic_flags: ThreatLayerSignal[]
  causal_flags: ThreatLayerSignal[]
  ontological_flags: ThreatLayerSignal[]
  cognitive_flags: ThreatLayerSignal[]
  anthropological_flags: ThreatLayerSignal[]
  account_score: number
  account_level: string
  created_at: string
}

export interface AnalysisResponse {
  id: number
  analysis_type: string
  scope: string
  overall_score: number
  overall_level: string
  analyzed_count: number
  duration_ms?: number
  llm_report?: string
  created_at: string
}

export interface AnalysisDetail extends AnalysisResponse {
  scope_id?: number
  semiotic_score: number
  causal_score: number
  ontological_score: number
  cognitive_score: number
  anthropological_score: number
  semiotic_signals: ThreatLayerSignal[]
  causal_signals: ThreatLayerSignal[]
  ontological_signals: ThreatLayerSignal[]
  cognitive_signals: ThreatLayerSignal[]
  anthropological_signals: ThreatLayerSignal[]
  threat_graph: ThreatGraphData
  total_nodes: number
  total_edges: number
  total_semiotic: number
  total_causal: number
  total_ontological: number
  total_cognitive: number
  total_anthropological: number
}

export const triggerIdentityThreatAnalysis = (body: {
  scope?: string
  scope_id?: number
  lang?: string
}) => api.post<AnalysisResponse>('/identity-threat/analyze', body)

export const listIdentityThreatAnalyses = (params?: { limit?: number; offset?: number }) =>
  api.get<AnalysisResponse[]>('/identity-threat/analyses', { params })

export const getIdentityThreatAnalysis = (
  id: number,
  lang?: string,
  includeGraph = false,
  signalsLimit = 0,
  includeReport = false,
) =>
  api.get<AnalysisDetail>(`/identity-threat/analyses/${id}`, {
    params: { lang, include_graph: includeGraph, signals_limit: signalsLimit, include_report: includeReport },
  })

// Fetch signals for a specific layer (used by tab components to lazy-load full signals)
export const getLayerSignals = (
  analysisId: number,
  layer: 'semiotic' | 'causal' | 'ontological' | 'cognitive' | 'anthropological',
  lang?: string,
) =>
  api.get<{ layer: string; signals: ThreatLayerSignal[]; total: number }>(
    `/identity-threat/analyses/${analysisId}/signals/${layer}`,
    { params: { lang } }
  )

export const getAccountThreatSignals = (analysisId: number, params?: { lang?: string; min_score?: number; limit?: number }) =>
  api.get<ThreatAccountSignal[]>(`/identity-threat/accounts/${analysisId}`, { params })

export const getThreatGraph = (analysisId: number) =>
  api.get<ThreatGraphData>(`/identity-threat/graph/${analysisId}`)

export const regenerateThreatReport = (analysisId: number, lang?: string) =>
  api.post<AnalysisResponse>(`/identity-threat/report/${analysisId}`, null, { params: { lang } })

// MITRE ATT&CK Navigator layer export
export const getMitreLayer = (analysisId: number) =>
  api.get<Record<string, unknown>>(`/identity-threat/mitre-layer/${analysisId}`)

// ── What-If Attack Simulation ─────────────────────────────────────────

export interface WhatIfReachableNode {
  snapshot_id: number
  username: string
  uid_sid: string
  asset_id: number
  asset_code?: string
  ip?: string
  hostname?: string
  is_admin: boolean
  lifecycle: string
  account_status: string
  hops: number
  entry_edge_type: string
  entry_edge_weight: number
}

export interface WhatIfMitredTechnique {
  technique_id: string
  name: string
  tactic: string
  tactic_label: string
  severity: string
  rationale: string
}

export interface WhatIfSimulationResult {
  source_node: Record<string, unknown>
  total_reachable: number
  human_reachable: number
  admin_reachable: number
  privileged_reachable: number
  asset_count: number
  unique_assets: number[]
  mitre_techniques: WhatIfMitredTechnique[]
  blast_radius_score: number
  blast_radius_level: string
  reachable_nodes: WhatIfReachableNode[]
  hop_distribution: Record<number, number>
}

export const whatifSimulate = (analysisId: number, sourceId: string, maxHops = 5) =>
  api.get<WhatIfSimulationResult>(`/identity-threat/whatif/${analysisId}`, {
    params: { source_id: sourceId, max_hops: maxHops },
  })

// ── Attack Paths ────────────────────────────────────────────────────

export interface AttackPathEdge {
  source: string
  target: string
  edge_type: string
  weight: number
}

export interface AttackPathNode {
  id: string
  snapshot_id: number
  username: string
  asset_id: number
  ip?: string
  hostname?: string
  is_admin: boolean
  account_status: string
}

export interface AttackPathEntry {
  source_id: number
  source_name: string
  source_ip?: string
  source_has_credential_leak: boolean
  source_has_nopasswd: boolean
  hops: AttackPathEdge[]
  targets: AttackPathNode[]
}

export interface AttackPathsResponse {
  analysis_id: number
  max_hops: number
  total_paths: number
  paths: AttackPathEntry[]
}

export const getAttackPaths = (analysisId: number, params?: { source_id?: number; max_hops?: number }) =>
  api.get<AttackPathsResponse>(`/identity-threat/attack-paths/${analysisId}`, { params })

// ── Risk Propagation ─────────────────────────────────────────────

export const getRiskProfile = (assetId: number) =>
  api.get(`/risk/profile/${assetId}`)

export const getRiskOverview = (params?: { limit?: number; offset?: number; min_score?: number }) =>
  api.get('/risk/overview', { params })

export const getRiskHotspots = (params?: { threshold?: number }) =>
  api.get('/risk/hotspots', { params })

export const triggerRiskPropagation = () =>
  api.post('/risk/propagate')

// ── Compliance ──────────────────────────────────────────────────────

export const getComplianceDashboard = () =>
  api.get('/compliance/dashboard')

export const getComplianceRuns = (params?: { limit?: number; offset?: number; framework_slug?: string }) =>
  api.get('/compliance/runs', { params })

export const runComplianceFramework = (slug: string) =>
  api.post(`/compliance/frameworks/${slug}/run`)

export const runAllComplianceFrameworks = () =>
  api.post('/compliance/run-all')

// ── Identity Fusion ────────────────────────────────────────────

export const listIdentities = (params?: { search?: string; limit?: number; offset?: number }) =>
  api.get('/identities', { params })

export const getIdentity = (id: number) =>
  api.get(`/identities/${id}`)

export const getIdentitySuggestions = (q: string) =>
  api.get('/identities/suggestions', { params: { q } })

export const linkIdentityAccount = (data: { identity_id: number; snapshot_id: number; match_type?: string; match_confidence?: number }) =>
  api.post('/identities/link', data)

export const unlinkIdentityAccount = (identityId: number, linkId: number) =>
  api.delete(`/identities/${identityId}/unlink/${linkId}`)

export const rematchIdentities = () =>
  api.post('/identities/re-match')

// ── Account Lifecycle ───────────────────────────────────────────

export const getLifecycleDashboard = () =>
  api.get('/lifecycle/dashboard')

export const listLifecycleStatuses = (params?: {
  status?: string; asset_id?: number; search?: string; limit?: number; offset?: number
}) =>
  api.get('/lifecycle/statuses', { params })

export const triggerLifecycleCompute = () =>
  api.post('/lifecycle/compute')

export const getLifecycleConfig = (category = 'global') =>
  api.get('/lifecycle/config', { params: { category } })

export const updateLifecycleConfig = (data: {
  active_days?: number; dormant_days?: number; auto_alert?: boolean
}, category = 'global') =>
  api.put('/lifecycle/config', data, { params: { category } })

// ── Account Risk Score ─────────────────────────────────────────

export const getAccountRisk = (snapshotId: number) =>
  api.get(`/risk/account/${snapshotId}`)

export const listAccountRisks = (params?: { limit?: number; offset?: number; min_score?: number }) =>
  api.get('/risk/accounts', { params })

export const recomputeAccountRisks = () =>
  api.post('/risk/accounts/recompute')

// ── Snapshot Owner ────────────────────────────────────────────────

export interface SnapshotOwner {
  snapshot_id: number
  username: string
  asset_id: number
  owner_identity_id?: number
  owner_email?: string
  owner_name?: string
}

export const getSnapshotOwner = (snapshotId: number) =>
  api.get<SnapshotOwner>(`/snapshots/${snapshotId}/owner`)

export const setSnapshotOwner = (snapshotId: number, data: { owner_email?: string; owner_name?: string }) =>
  api.patch<SnapshotOwner>(`/snapshots/${snapshotId}/owner`, data)

export const listOwnerlessSnapshots = (params?: { is_admin?: boolean }) =>
  api.get<SnapshotOwner[]>('/snapshots/ownerless', { params })

export const bulkSetSnapshotOwner = (data: { snapshot_ids: number[]; owner_email: string; owner_name?: string }) =>
  api.post('/snapshots/bulk-set-owner', data)

// ── Export ───────────────────────────────────────────────────────

export const exportReviewReport = (reportId: number) =>
  api.get(`/export/review-report/${reportId}`, { responseType: 'blob' })

export const exportComplianceRun = (runId: number) =>
  api.get(`/export/compliance-run/${runId}`, { responseType: 'blob' })

// ── Security Policies ─────────────────────────────────────────────────────────

export const listPolicies = (params?: { category?: string; enabled?: boolean }) =>
  api.get('/policies', { params })

export const getPolicy = (id: number) =>
  api.get(`/policies/${id}`)

export const createPolicy = (data: {
  name: string; description?: string; category?: string;
  severity?: string; rego_code: string; enabled?: boolean
}) => api.post('/policies', data)

export const updatePolicy = (id: number, data: {
  name?: string; description?: string; category?: string;
  severity?: string; rego_code?: string; enabled?: boolean
}) => api.put(`/policies/${id}`, data)

export const deletePolicy = (id: number) =>
  api.delete(`/policies/${id}`)

export const evaluatePolicy = (policyId: number, snapshotId: number) =>
  api.post(`/policies/${policyId}/evaluate/${snapshotId}`)

export const evaluateAllPolicies = (snapshotId: number) =>
  api.post('/policies/evaluate-all', null, { params: { snapshot_id: snapshotId } })

export const getPolicyResults = (params?: { days?: number; policy_id?: number; passed?: boolean; limit?: number; offset?: number }) =>
  api.get('/policies/policy-results', { params })

export const listRecentSnapshots = (limit = 50) =>
  api.get('/snapshots/recent', { params: { limit } })

// ── UEBA ──────────────────────────────────────────────────────────────────────

export const getUEBASummary = () =>
  api.get('/ueba/summary')

export const triggerUEBADetection = () =>
  api.post('/ueba/detect')

export const listUEBAEvents = (params?: { days?: number; severity?: string; event_type?: string; limit?: number; offset?: number }) =>
  api.get('/ueba/events', { params })

// ── Review Reminders ───────────────────────────────────────────

export const listReviewSchedules = () =>
  api.get('/review/schedules')

export const createReviewSchedule = (data: {
  name: string; period: string; day_of_month?: number;
  alert_channels?: { email?: string[]; webhook?: string }; enabled?: boolean
}) => api.post('/review/schedules', data)

export const updateReviewSchedule = (id: number, data: {
  name?: string; period?: string; day_of_month?: number;
  alert_channels?: { email?: string[]; webhook?: string }; enabled?: boolean
}) => api.put(`/review/schedules/${id}`, data)

export const deleteReviewSchedule = (id: number) =>
  api.delete(`/review/schedules/${id}`)

export const listReviewReports = (params?: {
  status?: string; limit?: number; offset?: number
}) => api.get('/review/reports', { params })

export const getReviewReport = (id: number) =>
  api.get(`/review/reports/${id}`)

export const triggerReviewGenerate = (scheduleId: number) =>
  api.post('/review/generate', null, { params: { schedule_id: scheduleId } })

export const approveReviewReport = (id: number, notes?: string) =>
  api.post(`/review/reports/${id}/approve`, null, { params: { notes } })

export const dismissReviewReport = (id: number, notes?: string) =>
  api.post(`/review/reports/${id}/dismiss`, null, { params: { notes } })

// ── PAM Integration ───────────────────────────────────────────

export const listPAMIntegrations = () =>
  api.get('/pam/integrations')

export const createPAMIntegration = (data: { name: string; provider: string; config?: Record<string, string> }) =>
  api.post('/pam/integrations', data)

export const updatePAMIntegration = (id: number, data: { name?: string; config?: Record<string, string>; status?: string }) =>
  api.put(`/pam/integrations/${id}`, data)

export const deletePAMIntegration = (id: number) =>
  api.delete(`/pam/integrations/${id}`)

export const syncPAMIntegration = (id: number) =>
  api.post(`/pam/integrations/${id}/sync`)

export const listPAMAccounts = (integrationId: number) =>
  api.get(`/pam/integrations/${integrationId}/accounts`)

export const getPAMComparison = (integrationId?: number) =>
  api.get('/pam/comparison', { params: integrationId ? { integration_id: integrationId } : {} })

// ── Knowledge Base ──────────────────────────────────────────────────────────────

const getLang = (): string => {
  // Read from localStorage (set by i18next LanguageDetector)
  const stored = localStorage.getItem('language')
  if (stored === 'en-US') return 'en'
  if (stored === 'zh-CN') return 'zh'
  // Fallback to i18n instance
  const lang = i18n.resolvedLanguage || i18n.language || 'zh'
  if (lang.startsWith('en')) return 'en'
  return 'zh'
}

export const searchKnowledgeBase = (q: string, limit = 10) =>
  api.get('/kb/search', { params: { query: q, limit, lang: getLang() } })

export const askKnowledgeBase = (question: string, snapshotId?: number) =>
  api.post('/kb/question', { question, snapshot_id: snapshotId }, { params: { lang: getLang() } })

export const getKnowledgeBaseStats = () =>
  api.get('/kb/stats', { params: { lang: getLang() } })

export const listKBTactics = () =>
  api.get('/kb/tactics', { params: { lang: getLang() } })

export const listKBCVEs = () =>
  api.get('/kb/cves', { params: { lang: getLang() } })

export const listKBPractices = () =>
  api.get('/kb/practices', { params: { lang: getLang() } })

// ── KB Admin CRUD ────────────────────────────────────────────────────────────

export interface KBEntryData {
  entry_type: string
  title: string
  title_en?: string
  description?: string
  description_en?: string
  extra_data: Record<string, unknown>
}

export const listKBEntries = (params?: { type?: string; limit?: number; offset?: number }) =>
  api.get('/kb/entries', { params })

export const getKBEntry = (id: number) =>
  api.get(`/kb/entries/${id}`)

export const createKBEntry = (data: KBEntryData) =>
  api.post('/kb/entries', data)

export const updateKBEntry = (id: number, data: Partial<KBEntryData> & { enabled?: boolean }) =>
  api.put(`/kb/entries/${id}`, data)

export const deleteKBEntry = (id: number) =>
  api.delete(`/kb/entries/${id}`)

// ── NHI Module ─────────────────────────────────────────────────────────────────

export const getNHIDashboard = () =>
  api.get('/nhi/dashboard')

export const listNHIInventory = (params?: {
  nhi_type?: string
  level?: string
  no_owner?: boolean
  limit?: number
  offset?: number
}) => api.get('/nhi/inventory', { params })

export const getNHI = (id: number) =>
  api.get(`/nhi/${id}`)

export const assignNhiOwner = (id: number, ownerEmail: string, ownerName?: string) =>
  api.patch(`/nhi/${id}/owner`, null, { params: { owner_email: ownerEmail, owner_name: ownerName } })

export const toggleNhiMonitoring = (id: number, enabled: boolean) =>
  api.patch(`/nhi/${id}/monitor`, null, { params: { enabled } })

export const syncNHI = () =>
  api.post('/nhi/sync')

export const listNHIAlerts = (params?: {
  level?: string
  status?: string
  limit?: number
  offset?: number
}) => api.get('/nhi/alerts', { params })

export const acknowledgeNHIAlert = (id: number) =>
  api.patch(`/nhi/alerts/${id}/acknowledge`)

export const resolveNHIAlert = (id: number) =>
  api.patch(`/nhi/alerts/${id}/resolve`)

export const listNHIPolicies = () =>
  api.get('/nhi/policies')

export const createNHIPolicy = (data: {
  name: string
  description?: string
  nhi_type?: string
  severity_filter?: string
  rotation_days?: number
  alert_threshold_days?: number
  require_owner?: boolean
  require_monitoring?: boolean
}) => api.post('/nhi/policies', data)

// ── Alert Actions ─────────────────────────────────────────────────────────────

export const acknowledgeAlert = (id: number) =>
  api.post(`/alerts/${id}/acknowledge`)

export const dismissAlert = (id: number) =>
  api.post(`/alerts/${id}/dismiss`)

export const respondToAlert = (id: number) =>
  api.post(`/alerts/${id}/respond`)

// ── Playbooks ─────────────────────────────────────────────────────────────────

export interface PlaybookStep {
  action: string
  target: string
  params?: Record<string, unknown>
}

export interface Playbook {
  id: number
  name: string
  description?: string
  name_key?: string | null
  description_key?: string | null
  trigger_type: string
  trigger_filter: Record<string, unknown>
  steps: PlaybookStep[]
  approval_required: boolean
  enabled: boolean
  created_at: string
}

export interface PlaybookExecution {
  id: number
  playbook_id: number
  snapshot_id: number
  status: string
  steps_status: { step_index: number; status: string; detail: string }[]
  result?: string
  triggered_by?: number
  approved_by?: number
  created_at: string
}

export const listPlaybooks = () =>
  api.get<Playbook[]>('/playbooks')

export const getPlaybook = (id: number) =>
  api.get<Playbook>(`/playbooks/${id}`)

export const createPlaybook = (data: {
  name: string
  description?: string
  trigger_type?: string
  trigger_filter?: Record<string, unknown>
  steps: PlaybookStep[]
  approval_required?: boolean
  enabled?: boolean
}) => api.post<Playbook>('/playbooks', data)

export const updatePlaybook = (id: number, data: Partial<{
  name: string
  description: string
  trigger_type: string
  trigger_filter: Record<string, unknown>
  steps: PlaybookStep[]
  approval_required: boolean
  enabled: boolean
}>) => api.put<Playbook>(`/playbooks/${id}`, data)

export const deletePlaybook = (id: number) =>
  api.delete(`/playbooks/${id}`)

export const executePlaybook = (playbookId: number, snapshotId: number) =>
  api.post<PlaybookExecution>('/playbooks/execute', { playbook_id: playbookId, snapshot_id: snapshotId })

export const dryRunPlaybook = (playbookId: number, snapshotId: number) =>
  api.post<{ steps: { action: string; target: string; dry_result: string }[] }>(
    '/playbooks/dry-run', { playbook_id: playbookId, snapshot_id: snapshotId }
  )

export const listPlaybookExecutions = (params?: { limit?: number; playbook_id?: number; status?: string }) =>
  api.get<PlaybookExecution[]>('/playbook-executions', { params })

export const approvePlaybookExecution = (id: number) =>
  api.post<PlaybookExecution>(`/playbook-executions/${id}/approve`)

export const rejectPlaybookExecution = (id: number) =>
  api.post<PlaybookExecution>(`/playbook-executions/${id}/reject`)
