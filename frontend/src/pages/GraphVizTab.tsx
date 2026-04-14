import { useState, useEffect, useRef, Component, type ReactNode } from 'react'
import {
  Button, Space, Tag, Col, Row, Card, Typography,
  Slider, Switch, Spin, Alert, message,
} from 'antd'
const { Text } = Typography
import { NodeExpandOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { getThreatGraph, getMitreLayer, ThreatNode, ThreatEdge } from '../api/client'

// ─── useWindowSize hook ─────────────────────────────────────────────────────────
function useWindowSize() {
  const [size, setSize] = useState({ w: window.innerWidth - 280, h: window.innerHeight - 240 })
  useEffect(() => {
    const onResize = () => setSize({ w: window.innerWidth - 280, h: window.innerHeight - 240 })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return size
}

// ─── Error boundary ──────────────────────────────────────────────────────────────
class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  constructor(props: any) { super(props); this.state = { hasError: false } }
  static getDerivedStateFromError() { return { hasError: true } }
  render() {
    if (this.state.hasError) {
      return <div style={{ textAlign: 'center', padding: 40, color: '#ff4d4f' }}>
        {i18n.t('threat.graphRenderError')}
      </div>
    }
    return this.props.children
  }
}

// ─── Types ──────────────────────────────────────────────────────────────────────
interface GraphNode extends ThreatNode {
  x?: number; y?: number; vx?: number; vy?: number
}
interface GraphLink {
  source: string | GraphNode; target: string | GraphNode; edge_type: string; weight: number
}
interface GraphData { nodes: GraphNode[]; links: GraphLink[] }

// ─── Component ───────────────────────────────────────────────────────────────────
interface GraphVizTabProps { analysisId: number }

export default function GraphVizTab({ analysisId }: GraphVizTabProps) {
  const { t } = useTranslation()
  const tRef = useRef(t)
  tRef.current = t

  // ── Refs for imperative state (no re-renders) ──────────────────────────────
  const graphInstanceRef = useRef<any>(null)
  const forceGraphLibRef = useRef<any>(null)
  const graphDataRef = useRef<GraphData>({ nodes: [], links: [] })
  const nodeSizeScaleRef = useRef(2)
  const showAllEdgesRef = useRef(false)
  const selectedNodeRef = useRef<string | null>(null)
  const hoveredNodeRef = useRef<GraphNode | null>(null)
  const dimensionsRef = useRef({ width: 800, height: 540 })

  // ── React state ────────────────────────────────────────────────────────────
  const [graphError, setGraphError] = useState<string | null>(null)
  const [libReady, setLibReady] = useState(false)        // true when force-graph loaded
  const [rawData, setRawData] = useState<GraphData>({ nodes: [], links: [] })
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] })
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [showAllEdges, setShowAllEdges] = useState(false)
  const [nodeSizeScale, setNodeSizeScale] = useState(2)
  const [severityFilter, setSeverityFilter] = useState<string>('dangerous')
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null)
  const [mitreLayer, setMitreLayer] = useState<Record<string, unknown> | null>(null)

  // Keep refs in sync with state
  useEffect(() => { nodeSizeScaleRef.current = nodeSizeScale }, [nodeSizeScale])
  useEffect(() => { showAllEdgesRef.current = showAllEdges }, [showAllEdges])
  useEffect(() => { selectedNodeRef.current = selectedNode }, [selectedNode])
  useEffect(() => { hoveredNodeRef.current = hoveredNode }, [hoveredNode])
  useEffect(() => { graphDataRef.current = graphData }, [graphData])

  // ── Load force-graph once on mount ─────────────────────────────────────────
  useEffect(() => {
    import('force-graph').then(m => {
      forceGraphLibRef.current = m.default || m
      setLibReady(true)
    }).catch(() => {
      setGraphError(tRef.current('threat.graphLibLoadFailed'))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Load graph data ────────────────────────────────────────────────────────
  useEffect(() => {
    getThreatGraph(analysisId)
      .then(r => {
        const raw = r.data
        const allNodes: GraphNode[] = (raw.nodes || []).map((n: ThreatNode) => ({ ...n }))
        const nodeIds = new Set(allNodes.map(n => n.id))
        const allLinks: GraphLink[] = (raw.edges || [])
          .filter((e: ThreatEdge) => nodeIds.has(e.source as any) && nodeIds.has(e.target as any))
          .map((e: ThreatEdge) => ({ source: e.source, target: e.target, edge_type: e.edge_type, weight: e.weight }))
        setRawData({ nodes: allNodes, links: allLinks })
      })
      .catch(() => setRawData({ nodes: [], links: [] }))
      .finally(() => setLoading(false))
  }, [analysisId])

  useEffect(() => {
    getMitreLayer(analysisId)
      .then(r => setMitreLayer(r.data))
      .catch(() => setMitreLayer(null))
  }, [analysisId])

  // ── Apply severity filter ─────────────────────────────────────────────────
  useEffect(() => {
    if (!rawData.nodes.length) { setGraphData({ nodes: [], links: [] }); return }
    const filteredNodes = severityFilter === 'dangerous'
      ? rawData.nodes.filter(n => n.account_level === 'critical' || n.account_level === 'high')
      : severityFilter === 'all' ? rawData.nodes
      : rawData.nodes.filter(n => n.account_level === severityFilter)
    const filteredIds = new Set(filteredNodes.map(n => n.id))
    const filteredLinks = rawData.links.filter(l => {
      const src = typeof l.source === 'string' ? l.source : (l.source as any).id
      const tgt = typeof l.target === 'string' ? l.target : (l.target as any).id
      return filteredIds.has(src) && filteredIds.has(tgt)
    })
    setGraphData({ nodes: filteredNodes, links: filteredLinks })
  }, [rawData, severityFilter])

  // ── Init / update graph imperatively (no re-render) ──────────────────────
  useEffect(() => {
    const FG = forceGraphLibRef.current
    if (!FG || !graphData.nodes.length) return

    const el = document.getElementById('fg-mount')
    if (!el) return

    let graph = graphInstanceRef.current
    const rect = el.getBoundingClientRect()
    const dims = dimensionsRef.current

    if (!graph) {
      graph = new FG(el)
      graph.width(rect.width || 800).height(rect.height || 540)
      graph.backgroundColor('#f8f9fa')

      graph.nodeCanvasObject((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
        try {
          const level = node.account_level || 'low'
          const nhiType = node.nhi_type || 'human'
          const isNHI = nhiType !== 'human'
          const scale = nodeSizeScaleRef.current
          const levelSizes: Record<string, number> = { critical: 12, high: 10, medium: 6, low: 4, info: 3 }
          const size = Math.max(2, Math.min((levelSizes[level] || 4) * scale * 0.5, 14))
          const nodeColor: Record<string, string> = {
            critical: '#dc2626', high: '#ea580c', medium: '#ca8a04', low: '#16a34a', info: '#6b7280',
          }
          const nhiColor: Record<string, string> = {
            system: '#6b7280', service: '#0ea5e9', cloud: '#8b5cf6',
            cicd: '#f59e0b', workload: '#10b981', application: '#ec4899',
            apikey: '#f97316', ai_agent: '#a855f7', unknown: '#9ca3af',
          }
          const x = node.x ?? 0, y = node.y ?? 0
          const fillColor = isNHI ? (nhiColor[nhiType] || '#9ca3af') : (nodeColor[level] || '#3b82f6')
          if (level === 'critical' || level === 'high') {
            ctx.shadowColor = nodeColor[level]; ctx.shadowBlur = 8
          }
          if (selectedNodeRef.current === node.id) {
            ctx.beginPath()
            if (isNHI) {
              ctx.moveTo(x, y - size - 4); ctx.lineTo(x + size + 4, y)
              ctx.lineTo(x, y + size + 4); ctx.lineTo(x - size - 4, y); ctx.closePath()
            } else {
              ctx.arc(x, y, size + 3, 0, 2 * Math.PI)
            }
            ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke()
          }
          if (isNHI) {
            ctx.beginPath()
            ctx.moveTo(x, y - size); ctx.lineTo(x + size, y)
            ctx.lineTo(x, y + size); ctx.lineTo(x - size, y); ctx.closePath()
            ctx.fillStyle = fillColor; ctx.fill()
            ctx.strokeStyle = 'rgba(255,255,255,0.4)'; ctx.lineWidth = 1; ctx.stroke()
          } else {
            ctx.beginPath(); ctx.arc(x, y, size, 0, 2 * Math.PI)
            ctx.fillStyle = fillColor; ctx.fill()
            ctx.shadowBlur = 0
            if (node.is_admin) {
              ctx.beginPath(); ctx.arc(x, y, size + 2, 0, 2 * Math.PI)
              ctx.strokeStyle = '#7c3aed'; ctx.lineWidth = 1.5; ctx.stroke()
            }
          }
          const showLabel = selectedNodeRef.current === node.id || globalScale > 1.5
          if (showLabel && globalScale > 0.6) {
            const fontSize = (level === 'critical' || level === 'high')
              ? Math.max(9, 11 / globalScale) : Math.max(7, 8 / globalScale)
            ctx.font = `bold ${fontSize}px Arial, sans-serif`
            ctx.fillStyle = 'rgba(0,0,0,0.8)'; ctx.textAlign = 'center'; ctx.textBaseline = 'top'
            ctx.fillText(node.username ?? '', x, y + size + 2)
            if (isNHI) {
              ctx.font = `${Math.max(6, fontSize - 2)}px Arial, sans-serif`
              ctx.fillStyle = nhiColor[nhiType] || '#9ca3af'
              ctx.fillText(nhiType, x, y + size + 2 + fontSize + 1)
            }
          }
        } catch {}
      })
      graph.nodeCanvasObjectMode?.(() => 'replace')

      graph.linkColor((link: any) => {
        const et = link.edge_type || ''
        const DANGEROUS = ['ssh_key_reuse', 'auth_chain', 'owns']
        if (!showAllEdgesRef.current && !DANGEROUS.includes(et)) return 'transparent'
        const LINK_COL: Record<string, string> = {
          ssh_key_reuse: '#dc2626', auth_chain: '#f97316', owns: '#7c3aed',
          permission_propagation: 'rgba(180,180,180,0.3)', behavior_similar: 'rgba(180,180,180,0.2)',
          same_identity: 'rgba(180,180,180,0.2)',
        }
        return LINK_COL[et] || 'rgba(180,180,180,0.25)'
      })
      graph.linkWidth((link: any) => {
        const et = link.edge_type || ''
        const DANGEROUS = ['ssh_key_reuse', 'auth_chain', 'owns']
        if (!showAllEdgesRef.current && !DANGEROUS.includes(et)) return 0
        return DANGEROUS.includes(et) ? 1.5 : 0.4
      })
      graph.linkDirectionalArrowLength(4)
      graph.linkDirectionalArrowRelPos(0.85)
      graph.onNodeHover((node: any) => {
        if (node) {
          const found = graphDataRef.current.nodes.find(n => n.id === node.id)
          setHoveredNode(found || null)
        } else { setHoveredNode(null) }
      })
      graph.onNodeClick((node: any) => setSelectedNode(selectedNodeRef.current === node.id ? null : node.id))
      graph.onBackgroundClick(() => setSelectedNode(null))
      graph.enableNodeDrag(true)
      graph.enableZoomInteraction(true)
      graph.cooldownTicks(300)
      graph.d3VelocityDecay(0.4)
      graphInstanceRef.current = graph
    } else {
      graph.width(rect.width || 800).height(rect.height || 540)
    }
    graph.graphData(graphDataRef.current)
    setTimeout(() => { try { graph.zoomToFit(400, 50) } catch {} }, 600)
  }, [graphData]) // intentionally: re-run when data changes; lib is guarded by !FG check

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (graphInstanceRef.current) {
        try { graphInstanceRef.current._destructor?.() } catch {}
        graphInstanceRef.current = null
      }
    }
  }, [])

  // ── ResizeObserver ────────────────────────────────────────────────────────
  useEffect(() => {
    const el = document.getElementById('fg-mount')
    if (!el) return
    const obs = new ResizeObserver(entries => {
      const entry = entries[0]
      if (entry) {
        const w = entry.contentRect.width
        const h = entry.contentRect.height
        dimensionsRef.current = { width: w, height: h }
        const graph = graphInstanceRef.current
        if (graph) { graph.width(w); graph.height(h) }
      }
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const getNodeColor = (node: GraphNode) => {
    const level = node.account_level || 'low'
    return ({ critical: '#93281b', high: '#e83e3e', medium: '#f5c518', low: '#52c41a', info: '#8c8c8c' })[level] || '#1890ff'
  }

  const downloadMitreLayer = () => {
    if (!mitreLayer) return
    const blob = new Blob([JSON.stringify(mitreLayer, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `attack-layer-${analysisId}.json`; a.click()
    URL.revokeObjectURL(url)
    message.success(t('threat.mitreLayerDownloaded'))
  }

  if (graphError) return <Alert type="error" message={graphError} />
  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>

  const nodeCount = graphData.nodes.length
  const edgeCount = graphData.links.length
  const filteredOut = rawData.nodes.length - nodeCount

  const severityBtns = [
    { key: 'dangerous', label: t('threat.filterDangerous'), color: '#dc2626' },
    { key: 'all', label: t('filter.all'), color: '#6b7280' },
    { key: 'critical', label: t('risk.critical'), color: '#dc2626' },
    { key: 'high', label: t('risk.high'), color: '#ea580c' },
    { key: 'medium', label: t('risk.medium'), color: '#ca8a04' },
    { key: 'low', label: t('risk.low'), color: '#16a34a' },
  ]

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        {severityBtns.map(btn => (
          <Button
            key={btn.key} size="small" type={severityFilter === btn.key ? 'primary' : 'default'}
            onClick={() => setSeverityFilter(btn.key)}
            style={severityFilter === btn.key ? { background: btn.color, borderColor: btn.color } : {}}
          >
            {btn.label}
          </Button>
        ))}
        <div style={{ flex: 1 }} />
        <Tag>{nodeCount} / {edgeCount} {t('threat.graphEdges')}{filteredOut > 0 ? ` (${t('threat.filteredOut', { n: filteredOut })})` : ''}</Tag>
        <Space>
          <span style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>{t('threat.nodeSize')}</span>
          <Slider min={1} max={8} value={nodeSizeScale} onChange={setNodeSizeScale} style={{ width: 80 }} />
        </Space>
        <Switch checked={showAllEdges} onChange={setShowAllEdges} checkedChildren={t('threat.allEdges')} unCheckedChildren={t('threat.dangerousEdges')} />
        {mitreLayer && (
          <Button size="small" icon={<NodeExpandOutlined />} onClick={downloadMitreLayer}>MITRE</Button>
        )}
      </div>

      <div style={{ position: 'relative', width: '100%', height: Math.max(dimensionsRef.current.height, 450), minHeight: 450, background: '#f8f9fa', borderRadius: 6, overflow: 'hidden', border: '1px solid #e5e7eb' }}>
        {nodeCount === 0 ? (
          <div style={{ textAlign: 'center', paddingTop: 80, color: '#9ca3af' }}>
            <NodeExpandOutlined style={{ fontSize: 48 }} />
            <div style={{ marginTop: 12 }}>{t('threat.noGraphData')}</div>
          </div>
        ) : (
          <ErrorBoundary>
            <div id="fg-mount" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }} />
          </ErrorBoundary>
        )}
        {hoveredNode && (
          <div style={{
            position: 'absolute', top: 12, right: 12, zIndex: 20,
            background: '#fff', border: '1px solid #e5e7eb', borderRadius: 6,
            padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            minWidth: 180, pointerEvents: 'none',
          }}>
            <Space>
              <Tag color={
                hoveredNode.account_level === 'critical' ? 'red' :
                hoveredNode.account_level === 'high' ? 'orange' :
                hoveredNode.account_level === 'medium' ? 'gold' : 'green'
              }>{hoveredNode.username}</Tag>
              {hoveredNode.is_admin && <Tag color="purple">{t('threat.admin')}</Tag>}
            </Space>
            <div style={{ marginTop: 6, fontSize: 12, color: '#6b7280' }}>
              {hoveredNode.hostname || hoveredNode.ip || `${t('threat.assetId')}${hoveredNode.asset_id}`}
            </div>
            <div style={{ marginTop: 4, fontSize: 11, color: '#374151' }}>
              {t('threat.threatScore')}<strong style={{ color: hoveredNode.account_score && hoveredNode.account_score >= 60 ? '#dc2626' : '#374151' }}>{hoveredNode.account_score || 0}</strong>
            </div>
            {hoveredNode.nhi_type && hoveredNode.nhi_type !== 'human' && (
              <div style={{ marginTop: 2, fontSize: 11 }}>
                <Tag color="blue" style={{ fontSize: 10 }}>NHI: {hoveredNode.nhi_type}</Tag>
              </div>
            )}
          </div>
        )}
      </div>

      {selectedNode && (() => {
        const node = graphData.nodes.find(n => n.id === selectedNode)
        if (!node) return null
        const raw = (node.raw_info || {}) as Record<string, any>
        const sshAudit: Array<{ fingerprint?: string; comment?: string; type?: string }> = (raw.ssh_key_audit?.keys || []) as Array<{ fingerprint?: string; comment?: string; type?: string }>
        const credFindings: Array<{ file?: string; risk?: string; description?: string }> = (raw.credential_findings || []) as Array<{ file?: string; risk?: string; description?: string }>
        return (
          <Card size="small" style={{ marginTop: 12 }} title={
            <Space>
              <Tag color={getNodeColor(node)}>{node.username}</Tag>
              <Text type="secondary">{node.hostname || node.ip || `asset:${node.asset_id}`}</Text>
            </Space>
          }>
            <Row gutter={[8, 8]}>
              <Col span={8}><Text type="secondary">{t('threat.accountLevel')}: </Text><Tag color={getNodeColor(node)}>{t(`threat.level${(node.account_level || 'low').charAt(0).toUpperCase() + (node.account_level || 'low').slice(1)}`)}</Tag></Col>
              <Col span={8}><Text type="secondary">{t('threat.accountScore')}: </Text><Text strong>{node.account_score}</Text></Col>
              <Col span={8}><Text type="secondary">{t('threat.lifecycle')}: </Text><Text>{node.lifecycle}</Text></Col>
              <Col span={8}><Text type="secondary">{t('threat.isAdmin')}: </Text><Text>{node.is_admin ? t('threat.yes') : t('threat.no')}</Text></Col>
              <Col span={8}><Text type="secondary">UID: </Text><Text code>{node.uid_sid}</Text></Col>
              <Col span={8}><Text type="secondary">{t('threat.shell')}: </Text><Text code>{node.shell || '—'}</Text></Col>
              {node.groups && node.groups.length > 0 && (
                <Col span={24}>
                  <Text type="secondary">{t('threat.groups')}: </Text>
                  {node.groups.slice(0, 10).map(g => <Tag key={g} style={{ fontSize: 11 }}>{g}</Tag>)}
                  {node.groups.length > 10 && <Text type="secondary"> +{node.groups.length - 10}</Text>}
                </Col>
              )}
              {node.account_status && <Col span={8}><Text type="secondary">{t('threat.accountStatus')}: </Text><Text>{node.account_status}</Text></Col>}
              {node.identity_id && <Col span={8}><Text type="secondary">{t('threat.identityId')}: </Text><Text>{node.identity_id}</Text></Col>}
              {node.nhi_type && node.nhi_type !== 'human' && (
                <Col span={8}>
                  <Text type="secondary">NHI Type: </Text>
                  <Tag color="blue">{node.nhi_type}</Tag>
                </Col>
              )}
            </Row>
            {sshAudit.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Row gutter={[8, 8]}>
                  <Col span={24}><Text type="secondary" style={{ fontSize: 12 }}>{t('threat.sshKeys')} ({sshAudit.length})</Text></Col>
                  {sshAudit.slice(0, 5).map((k, i) => (
                    <Col key={i} span={8}>
                      <Tag style={{ fontSize: 10 }} title={k.fingerprint}>
                        {k.type || 'RSA'}: {k.comment || k.fingerprint?.slice(0, 16) + '…'}
                      </Tag>
                    </Col>
                  ))}
                </Row>
              </div>
            )}
            {credFindings.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>{t('threat.credentialFindings')}</Text>
                <div style={{ marginTop: 4 }}>
                  {credFindings.slice(0, 5).map((f, i) => (
                    <div key={i} style={{ marginBottom: 4 }}>
                      <Tag color={f.risk === 'critical' ? 'red' : f.risk === 'high' ? 'orange' : 'default'} style={{ fontSize: 10 }}>
                        {f.risk}
                      </Tag>
                      <Text type="secondary" style={{ fontSize: 11 }}>{f.description || f.file}</Text>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )
      })()}
    </div>
  )
}
