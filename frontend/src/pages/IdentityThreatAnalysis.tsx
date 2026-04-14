import { useState, useEffect, useRef, lazy, Suspense, type ReactNode } from 'react'
import {
  Card, Tabs, Typography, Spin, Button, Space, Tag, Table, Badge,
  Row, Col, Statistic, Alert, Drawer, List, message, Tooltip, Divider,
  Select, Switch,
} from 'antd'
import {
  RadarChartOutlined, ThunderboltOutlined, CrownOutlined,
  EyeOutlined, TeamOutlined, FileTextOutlined,
  HistoryOutlined, PlayCircleOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import {
  triggerIdentityThreatAnalysis,
  listIdentityThreatAnalyses,
  getIdentityThreatAnalysis,
  getLayerSignals,
  getAccountThreatSignals,
  AnalysisResponse,
  AnalysisDetail,
  ThreatAccountSignal,
  ThreatLayerSignal,
} from '../api/client'

// Lazy-loaded heavy tab components (loaded only when tab is opened)
const WhatIfSimulator = lazy(() => import('./WhatIfSimulator'))
const GraphVizTab = lazy(() => import('./GraphVizTab'))
const AttackPathsTab = lazy(() => import('./AttackPathsTab'))

const { Title, Text, Paragraph } = Typography


// ─── Severity badge ───────────────────────────────────────────────────────────────

const LEVEL_COLORS: Record<string, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'gold',
  low: 'green',
  info: 'default',
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'gold',
  low: 'cyan',
  info: 'default',
}

function LevelTag({ level }: { level: string }) {
  const { t } = useTranslation()
  return (
    <Tag color={LEVEL_COLORS[level] || 'default'}>
      {t(`threat.level${level.charAt(0).toUpperCase() + level.slice(1)}` as any) || level}
    </Tag>
  )
}

function SeverityBadge({ severity }: { severity: string }) {
  const { t } = useTranslation()
  return (
    <Badge
      status={SEVERITY_COLORS[severity] as any || 'default'}
      text={<Text type="secondary" style={{ fontSize: 12 }}>{t(`threat.${severity}`)}</Text>}
    />
  )
}


// ─── Score card for a layer ───────────────────────────────────────────────────────

function ScoreCard({
  label,
  score,
  icon,
  color,
}: {
  label: string
  score: number
  icon: React.ReactNode
  color: string
}) {
  const level = score >= 80 ? 'critical' : score >= 60 ? 'high' : score >= 40 ? 'medium' : 'low'
  return (
    <Card size="small" style={{ textAlign: 'center', borderTop: `3px solid ${color}` }}>
      <div style={{ color, fontSize: 24, marginBottom: 4 }}>{icon}</div>
      <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>
        {score}
        <span style={{ fontSize: 12, fontWeight: 400 }}>/100</span>
      </div>
      <LevelTag level={level} />
    </Card>
  )
}


// ─── Signal list component ────────────────────────────────────────────────────────

function SignalList({
  signals,
  emptyText,
  total,
  onLoadAll,
}: {
  signals: ThreatLayerSignal[]
  emptyText: string
  total?: number
  onLoadAll?: () => void
}) {
  const { t } = useTranslation()
  if (!signals || signals.length === 0) {
    return <Text type="secondary">{emptyText}</Text>
  }
  const visible = signals.slice(0, 20)
  const hasMore = total !== undefined && total > 20
  return (
    <>
      <List
        size="small"
        dataSource={visible}
        renderItem={(s) => (
          <List.Item style={{ padding: '6px 0' }}>
            <Space direction="vertical" size={0} style={{ width: '100%' }}>
              <Space>
                <SeverityBadge severity={s.severity} />
                <Text strong style={{ fontSize: 13 }}>{s.detail}</Text>
              </Space>
              {s.evidence && (
                <Text type="secondary" style={{ fontSize: 12, marginLeft: 28 }}>
                  {s.evidence}
                </Text>
              )}
            </Space>
          </List.Item>
        )}
      />
      {hasMore && (
        <div style={{ textAlign: 'center', marginTop: 8 }}>
          <Button size="small" onClick={onLoadAll} loading={!total}>
            {total !== undefined ? t('threat.loadAll', { n: total }) : t('threat.loading')}
          </Button>
        </div>
      )}
    </>
  )
}


// ─── Account rankings ─────────────────────────────────────────────────────────────

function AccountRankings({ analysisId, lang }: { analysisId: number; lang: string }) {
  const { t } = useTranslation()
  const [signals, setSignals] = useState<ThreatAccountSignal[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!analysisId) return
    getAccountThreatSignals(analysisId, { lang, min_score: 25, limit: 50 })
      .then(r => setSignals(r.data))
      .finally(() => setLoading(false))
  }, [analysisId, lang])

  if (loading) return <Spin />

  const columns = [
    {
      title: t('threat.account'),
      key: 'account',
      render: (_: unknown, r: ThreatAccountSignal) => (
        <Space direction="vertical" size={0}>
          <Text strong>{r.username}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{r.asset_code || `asset #${r.asset_id}`}</Text>
        </Space>
      ),
    },
    {
      title: t('threat.score'),
      key: 'score',
      width: 80,
      render: (_: unknown, r: ThreatAccountSignal) => (
        <Text strong style={{ color: r.account_score >= 80 ? '#cf1322' : r.account_score >= 60 ? '#d46b08' : r.account_score >= 40 ? '#d4b106' : '#389e0d' }}>
          {r.account_score}
        </Text>
      ),
    },
    {
      title: t('threat.level'),
      key: 'level',
      width: 80,
      render: (_: unknown, r: ThreatAccountSignal) => <LevelTag level={r.account_level} />,
    },
    {
      title: t('threat.signal'),
      key: 'signals',
      render: (_: unknown, r: ThreatAccountSignal) => {
        const all = [...r.semiotic_flags, ...r.causal_flags, ...r.ontological_flags, ...r.cognitive_flags, ...r.anthropological_flags]
        const top = all.sort((a, b) => {
          const w: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1, info: 0 }
          return (w[b.severity] || 0) - (w[a.severity] || 0)
        }).slice(0, 2)
        return (
          <Space direction="vertical" size={2}>
            {top.map((s, i) => (
              <Space key={i} size={4}>
                <SeverityBadge severity={s.severity} />
                <Text style={{ fontSize: 12 }}>{s.detail}</Text>
              </Space>
            ))}
            {all.length > 2 && <Text type="secondary" style={{ fontSize: 11 }}>+{all.length - 2} more</Text>}
          </Space>
        )
      },
    },
  ]

  return (
    <Table
      dataSource={signals}
      columns={columns}
      rowKey="id"
      size="small"
      pagination={{ pageSize: 10 }}
      title={() => <Text strong>{t('threat.rankings')} ({signals.length})</Text>}
      locale={{ emptyText: <Text type="secondary">{t('threat.noData')}</Text> }}
    />
  )
}


// ─── Tab contents ────────────────────────────────────────────────────────────────

function SummaryTab({ analysis, lang }: { analysis: AnalysisDetail; lang: string }) {
  const { t } = useTranslation()
  const [llmReport, setLlmReport] = useState<string | null>(analysis.llm_report ?? null)
  const [reportLoading, setReportLoading] = useState(false)
  const [showRankings, setShowRankings] = useState(false)

  const loadReport = () => {
    if (llmReport) { setLlmReport(null); return } // toggle: hide
    setReportLoading(true)
    if (!analysis.llm_report) {
      // No stored report — generate on demand
      import('../api/client').then(m => m.regenerateThreatReport(analysis.id, lang))
        .then(() => getIdentityThreatAnalysis(analysis.id, lang, false, 0, true))
        .then(r => setLlmReport(r.data.llm_report ?? null))
        .catch(() => message.error(t('threat.reportGenFailed')))
        .finally(() => setReportLoading(false))
    } else {
      // Has stored report — just load
      getIdentityThreatAnalysis(analysis.id, lang, false, 0, true)
        .then(r => setLlmReport(r.data.llm_report ?? null))
        .catch(() => setLlmReport(null))
        .finally(() => setReportLoading(false))
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Alert
        message={<Space><Text strong>{t('threat.analysisSummary')}</Text>
          <Button size="small" loading={reportLoading} onClick={loadReport}>
            {llmReport ? t('threat.hideReport') : analysis.llm_report ? t('threat.loadReport') : t('threat.generateReport')}
          </Button>
        </Space>}
        description={
          llmReport ? (
            <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.8 }}>
              {llmReport}
            </Paragraph>
          ) : (
            <Text type="secondary">{t('threat.clickToLoadReport')}</Text>
          )
        }
        type="info"
        showIcon
      />
      {!showRankings ? (
        <Button onClick={() => setShowRankings(true)}>{t('threat.loadRankings')}</Button>
      ) : (
        <AccountRankings analysisId={analysis.id} lang={lang} />
      )}
    </Space>
  )
}

function SemioticsTab({ analysis }: { analysis: AnalysisDetail }) {
  const { t } = useTranslation()
  const [signals, setSignals] = useState<ThreatLayerSignal[]>([])
  const [loading, setLoading] = useState(true)
  const total = (analysis as any).total_semiotic ?? 0
  const loadSignals = () => {
    const lang = i18n.language.startsWith('en') ? 'en' : 'zh'
    setLoading(true)
    getLayerSignals(analysis.id, 'semiotic', lang)
      // semiotics returns node-level objects with nested signals arrays — flatten them
      // Go engine returns flat signals: [{type, detail, node_id, ...}] — handle both
      .then(r => setSignals(
        (r.data.signals || []).flatMap((node: any) =>
          node.signals
            ? (node.signals || []).map((s: any) => ({
                ...s,
                node_id: node.node_id,
                username: node.username,
                asset_code: node.asset_code,
                detail: s.detail || s.description || s.type,
              }))
            : [{ ...node, detail: node.detail || node.description || node.type }]
        )
      ))
      .catch(() => message.error(t('threat.loadFailed')))
      .finally(() => setLoading(false))
  }
  useEffect(() => { loadSignals() }, [analysis.id])
  return (
    <Spin spinning={loading}>
      <SignalList
        signals={signals}
        emptyText={t('threat.noAnalysis')}
        total={total}
        onLoadAll={total > signals.length ? loadSignals : undefined}
      />
    </Spin>
  )
}

function CausalTab({ analysis }: { analysis: AnalysisDetail }) {
  const { t } = useTranslation()
  const [signals, setSignals] = useState<ThreatLayerSignal[]>([])
  const [loading, setLoading] = useState(true)
  const total = (analysis as any).total_causal ?? 0
  const loadSignals = () => {
    const lang = i18n.language.startsWith('en') ? 'en' : 'zh'
    setLoading(true)
    getLayerSignals(analysis.id, 'causal', lang)
      .then(r => setSignals((r.data.signals || []).map((s: any) => ({ ...s, detail: s.detail || s.description || s.type }))))
      .catch(() => message.error(t('threat.loadFailed')))
      .finally(() => setLoading(false))
  }
  useEffect(() => { loadSignals() }, [analysis.id])
  return (
    <Spin spinning={loading}>
      <SignalList
        signals={signals}
        emptyText={t('threat.noAnalysis')}
        total={total}
        onLoadAll={total > signals.length ? loadSignals : undefined}
      />
    </Spin>
  )
}

function OntologicalTab({ analysis }: { analysis: AnalysisDetail }) {
  const { t } = useTranslation()
  const [signals, setSignals] = useState<ThreatLayerSignal[]>([])
  const [loading, setLoading] = useState(true)
  const total = (analysis as any).total_ontological ?? 0
  const loadSignals = () => {
    const lang = i18n.language.startsWith('en') ? 'en' : 'zh'
    setLoading(true)
    getLayerSignals(analysis.id, 'ontological', lang)
      .then(r => setSignals((r.data.signals || []).map((s: any) => ({ ...s, detail: s.detail || s.description || s.type }))))
      .catch(() => message.error(t('threat.loadFailed')))
      .finally(() => setLoading(false))
  }
  useEffect(() => { loadSignals() }, [analysis.id])
  return (
    <Spin spinning={loading}>
      <SignalList
        signals={signals}
        emptyText={t('threat.noAnalysis')}
        total={total}
        onLoadAll={total > signals.length ? loadSignals : undefined}
      />
    </Spin>
  )
}

function CognitiveTab({ analysis }: { analysis: AnalysisDetail }) {
  const { t } = useTranslation()
  const [signals, setSignals] = useState<ThreatLayerSignal[]>([])
  const [loading, setLoading] = useState(true)
  const total = (analysis as any).total_cognitive ?? 0
  const loadSignals = () => {
    const lang = i18n.language.startsWith('en') ? 'en' : 'zh'
    setLoading(true)
    getLayerSignals(analysis.id, 'cognitive', lang)
      .then(r => setSignals((r.data.signals || []).map((s: any) => ({ ...s, detail: s.detail || s.description || s.type }))))
      .catch(() => message.error(t('threat.loadFailed')))
      .finally(() => setLoading(false))
  }
  useEffect(() => { loadSignals() }, [analysis.id])
  return (
    <Spin spinning={loading}>
      <SignalList
        signals={signals}
        emptyText={t('threat.noAnalysis')}
        total={total}
        onLoadAll={total > signals.length ? loadSignals : undefined}
      />
    </Spin>
  )
}

function AnthroTab({ analysis }: { analysis: AnalysisDetail }) {
  const { t } = useTranslation()
  const [signals, setSignals] = useState<ThreatLayerSignal[]>([])
  const [loading, setLoading] = useState(true)
  const total = (analysis as any).total_anthropological ?? 0
  const loadSignals = () => {
    const lang = i18n.language.startsWith('en') ? 'en' : 'zh'
    setLoading(true)
    getLayerSignals(analysis.id, 'anthropological', lang)
      .then(r => setSignals((r.data.signals || []).map((s: any) => ({ ...s, detail: s.detail || s.description || s.type }))))
      .catch(() => message.error(t('threat.loadFailed')))
      .finally(() => setLoading(false))
  }
  useEffect(() => { loadSignals() }, [analysis.id])
  return (
    <Spin spinning={loading}>
      <SignalList
        signals={signals}
        emptyText={t('threat.noAnalysis')}
        total={total}
        onLoadAll={total > signals.length ? loadSignals : undefined}
      />
    </Spin>
  )
}


// ─── History drawer ──────────────────────────────────────────────────────────────

function HistoryDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const [analyses, setAnalyses] = useState<AnalysisResponse[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (open) {
      setLoading(true)
      listIdentityThreatAnalyses({ limit: 20 })
        .then(r => setAnalyses(r.data))
        .finally(() => setLoading(false))
    }
  }, [open])

  const columns = [
    {
      title: t('threat.overallScore'),
      dataIndex: 'overall_score',
      key: 'overall_score',
      width: 100,
      render: (score: number) => <Text strong>{score}</Text>,
    },
    {
      title: t('threat.level'),
      dataIndex: 'overall_level',
      key: 'level',
      width: 80,
      render: (level: string) => <LevelTag level={level} />,
    },
    {
      title: t('threat.scope'),
      dataIndex: 'scope',
      key: 'scope',
      width: 80,
      render: (s: string) => t(`threat.scope${s.charAt(0).toUpperCase() + s.slice(1)}` as any),
    },
    {
      title: t('threat.analyzedCount'),
      dataIndex: 'analyzed_count',
      key: 'count',
      width: 100,
    },
    {
      title: t('threat.duration'),
      dataIndex: 'duration_ms',
      key: 'duration',
      width: 80,
      render: (ms?: number) => ms ? `${ms}ms` : '-',
    },
    {
      title: t('threat.created_at'),
      dataIndex: 'created_at',
      key: 'created_at',
      render: (d: string) => new Date(d).toLocaleString(),
    },
  ]

  return (
    <Drawer
      title={t('threat.history')}
      open={open}
      onClose={onClose}
      width={680}
      destroyOnClose
    >
      <Table
        dataSource={analyses}
        columns={columns}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={false}
        locale={{ emptyText: <Text type="secondary">{t('threat.noData')}</Text> }}
      />
    </Drawer>
  )
}


// ─── Main page ───────────────────────────────────────────────────────────────────

export default function IdentityThreatAnalysis() {
  const { t } = useTranslation()
  const [triggering, setTriggering] = useState(false)
  const [currentAnalysis, setCurrentAnalysis] = useState<AnalysisDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('summary')
  const [historyOpen, setHistoryOpen] = useState(false)

  // Load latest analysis on mount (skip threat_graph — GraphVizTab fetches it separately)
  useEffect(() => {
    const curLang = i18n.language.startsWith('en') ? 'en' : 'zh'
    listIdentityThreatAnalyses({ limit: 1 })
      .then(r => {
        if (r.data.length > 0) {
          return getIdentityThreatAnalysis(r.data[0].id, curLang, false, 20)
        }
        return null
      })
      .then(r => { if (r) setCurrentAnalysis(r.data) })
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── SSE real-time: auto-refresh when a new analysis completes ──────────────
  useEffect(() => {
    let es: EventSource | null = null
    let retryTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      const base = window.location.origin
      es = new EventSource(`${base}/api/v1/identity-threat/stream`)

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.event !== 'analysis_complete') return
          // New analysis completed — refresh if it's a newer one than currently shown
          const curLang = i18n.language.startsWith('en') ? 'en' : 'zh'
          if (!currentAnalysis || data.analysis_id > currentAnalysis.id) {
            getIdentityThreatAnalysis(data.analysis_id, curLang, false, 20)
              .then(r => { if (r) setCurrentAnalysis(r.data) })
          }
          message.info({
            content: t('threat.sseNewAnalysis', {
              id: data.analysis_id,
              level: data.overall_level,
              score: data.overall_score,
            }),
            duration: 5,
          })
        } catch {
          // ignore parse errors
        }
      }

      es.onerror = () => {
        es?.close()
        es = null
        retryTimer = setTimeout(connect, 5000)
      }
    }

    connect()

    return () => {
      if (retryTimer) clearTimeout(retryTimer)
      if (es) es.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleTrigger = async () => {
    setTriggering(true)
    const curLang = i18n.language.startsWith('en') ? 'en' : 'zh'
    try {
      const r = await triggerIdentityThreatAnalysis({ scope: 'global', lang: curLang })
      const detail = await getIdentityThreatAnalysis(r.data.id, curLang, false, 20)
      setCurrentAnalysis(detail.data)
      message.success(t('threat.triggerSuccess'))
    } catch {
      message.error(t('threat.triggerFailed'))
    } finally {
      setTriggering(false)
    }
  }

  const handleRegenerate = async () => {
    if (!currentAnalysis) return
    const curLang = i18n.language.startsWith('en') ? 'en' : 'zh'
    message.loading({ content: t('threat.regenerating'), key: 'regen' })
    try {
      await import('../api/client').then(m =>
        m.regenerateThreatReport(currentAnalysis.id, curLang)
      )
      const detail = await getIdentityThreatAnalysis(currentAnalysis.id, curLang, false)
      setCurrentAnalysis(detail.data)
      message.success({ content: t('threat.triggerSuccess'), key: 'regen' })
    } catch {
      message.error({ content: t('threat.triggerFailed'), key: 'regen' })
    }
  }

  const curLang = i18n.language.startsWith('en') ? 'en' : 'zh'

  const LAYER_SCORES = currentAnalysis ? [
    { label: t('threat.layerSemiotics'), score: currentAnalysis.semiotic_score, icon: <RadarChartOutlined />, color: '#1890ff' },
    { label: t('threat.layerCausal'), score: currentAnalysis.causal_score, icon: <ThunderboltOutlined />, color: '#722ed1' },
    { label: t('threat.layerOntological'), score: currentAnalysis.ontological_score, icon: <CrownOutlined />, color: '#fa8c16' },
    { label: t('threat.layerCognitive'), score: currentAnalysis.cognitive_score, icon: <EyeOutlined />, color: '#f5222d' },
    { label: t('threat.layerAnthro'), score: currentAnalysis.anthropological_score, icon: <TeamOutlined />, color: '#52c41a' },
  ] : []

  const LazyTab = ({ children }: { children: ReactNode }) => (
    <Suspense fallback={<div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>}>
      {children}
    </Suspense>
  )

  const tabItems = [
    { key: 'summary', label: t('threat.tabSummary'), children: currentAnalysis ? <SummaryTab analysis={currentAnalysis} lang={curLang} /> : <Text type="secondary">{t('threat.noAnalysis')}</Text> },
    { key: 'semiotics', label: t('threat.tabSemiotics'), children: currentAnalysis ? <SemioticsTab analysis={currentAnalysis} /> : null },
    { key: 'causal', label: t('threat.tabCausal'), children: currentAnalysis ? <CausalTab analysis={currentAnalysis} /> : null },
    { key: 'ontological', label: t('threat.tabOntological'), children: currentAnalysis ? <OntologicalTab analysis={currentAnalysis} /> : null },
    { key: 'cognitive', label: t('threat.tabCognitive'), children: currentAnalysis ? <CognitiveTab analysis={currentAnalysis} /> : null },
    { key: 'anthro', label: t('threat.tabAnthro'), children: currentAnalysis ? <AnthroTab analysis={currentAnalysis} /> : null },
    { key: 'graph', label: t('threat.tabGraph'), children: currentAnalysis ? <LazyTab><GraphVizTab analysisId={currentAnalysis.id} /></LazyTab> : null },
    { key: 'whatif', label: t('threat.tabWhatIf'), children: currentAnalysis ? <LazyTab><WhatIfSimulator analysisId={currentAnalysis.id} /></LazyTab> : null },
    { key: 'attackpaths', label: t('threat.tabAttackPaths'), children: currentAnalysis ? <LazyTab><AttackPathsTab analysisId={currentAnalysis.id} /></LazyTab> : null },
  ]

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text type="secondary">{t('threat.analyzing')}</Text>
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: 0 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <RadarChartOutlined style={{ marginRight: 8 }} />
          {t('threat.title')}
        </Title>
        <Space>
          <Button icon={<HistoryOutlined />} onClick={() => setHistoryOpen(true)}>
            {t('threat.history')}
          </Button>
          {currentAnalysis && (
            <Tooltip title={t('threat.regenerate')}>
              <Button icon={<ReloadOutlined />} onClick={handleRegenerate} />
            </Tooltip>
          )}
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={triggering}
            onClick={handleTrigger}
          >
            {triggering ? t('threat.triggering') : t('threat.trigger')}
          </Button>
        </Space>
      </div>

      {/* Score overview cards */}
      {currentAnalysis ? (
        <>
          {/* Overall stats */}
          <Card size="small" style={{ marginBottom: 16 }}>
            <Row gutter={24}>
              <Col span={4}>
                <Statistic
                  title={<Text type="secondary">{t('threat.overallScore')}</Text>}
                  value={currentAnalysis.overall_score}
                  suffix="/100"
                  valueStyle={{ color: currentAnalysis.overall_score >= 80 ? '#cf1322' : currentAnalysis.overall_score >= 60 ? '#d46b08' : currentAnalysis.overall_score >= 40 ? '#d4b106' : '#389e0d' }}
                />
                <LevelTag level={currentAnalysis.overall_level} />
              </Col>
              <Col span={4}>
                <Statistic title={<Text type="secondary">{t('threat.analyzedCount')}</Text>} value={currentAnalysis.analyzed_count} />
              </Col>
              <Col span={4}>
                <Statistic
                  title={<Text type="secondary">{t('threat.duration')}</Text>}
                  value={currentAnalysis.duration_ms ? `${currentAnalysis.duration_ms}ms` : '-'}
                />
              </Col>
              <Col span={4}>
                <Statistic title={<Text type="secondary">{t('threat.nodes')}</Text>} value={currentAnalysis.total_nodes || 0} />
              </Col>
              <Col span={4}>
                <Statistic title={<Text type="secondary">{t('threat.edges')}</Text>} value={currentAnalysis.total_edges || 0} />
              </Col>
              <Col span={4}>
                <Statistic
                  title={<Text type="secondary">{t('threat.scope')}</Text>}
                  value={t(`threat.scope${currentAnalysis.scope.charAt(0).toUpperCase() + currentAnalysis.scope.slice(1)}` as any) || currentAnalysis.scope}
                />
              </Col>
            </Row>
          </Card>

          {/* Five layer cards */}
          <Row gutter={12} style={{ marginBottom: 16 }}>
            {LAYER_SCORES.map(s => (
              <Col span={4} key={s.label}>
                <ScoreCard {...s} />
              </Col>
            ))}
          </Row>

          {/* Tabs */}
          <Card>
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              items={tabItems}
              size="small"
            />
          </Card>
        </>
      ) : (
        <Card>
          <div style={{ textAlign: 'center', padding: '48px 0' }}>
            <FileTextOutlined style={{ fontSize: 48, color: '#ccc', marginBottom: 16 }} />
            <div>
              <Text type="secondary">{t('threat.noAnalysis')}</Text>
            </div>
            <div style={{ marginTop: 16 }}>
              <Button type="primary" icon={<PlayCircleOutlined />} loading={triggering} onClick={handleTrigger}>
                {t('threat.trigger')}
              </Button>
            </div>
          </div>
        </Card>
      )}

      <HistoryDrawer open={historyOpen} onClose={() => setHistoryOpen(false)} />
    </div>
  )
}
