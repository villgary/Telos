import { useEffect, useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Tree, Card, Typography, Tag, Space, Spin, Empty,
  Popconfirm, Button, message, Popover, Tabs, Badge,
} from 'antd'
import { BranchesOutlined, ReloadOutlined, AppstoreOutlined,
  SafetyCertificateOutlined, UserOutlined, ThunderboltOutlined,
  WarningOutlined, AimOutlined } from '@ant-design/icons'
import api, { getRiskOverview, getRiskHotspots } from '../api/client'
import type { DataNode } from 'antd/es/tree'

const { Title, Text } = Typography

interface AccountItem {
  id: number
  username: string
  is_admin: boolean
  account_status: string | null
  last_login: string | null
}

interface AssetSummary {
  id: number
  asset_code: string
  ip: string
  hostname?: string
  asset_category: string
  account_count: number
  admin_count: number
  latest_accounts: AccountItem[]
}

interface HierarchyNode {
  asset: AssetSummary
  relation_type?: string
  children: HierarchyNode[]
}

interface FlatRel {
  id: number
  parent_id: number
  child_id: number
  relation_type: string
  description?: string
  parent: { id: number; asset_code: string; ip: string }
  child: { id: number; asset_code: string; ip: string }
}

const REL_COLOR: Record<string, string> = {
  hosts_vm: 'blue',
  hosts_container: 'cyan',
  runs_service: 'green',
  network_peer: 'purple',
  belongs_to: 'orange',
}

const CAT_COLOR: Record<string, string> = {
  server: '#1677ff',
  database: '#fa8c16',
  network: '#52c41a',
  iot: '#eb2f96',
}

const RISK_COLOR: Record<string, string> = {
  critical: '#ff4d4f',
  high: '#fa8c16',
  medium: '#faad14',
  low: '#52c41a',
}

interface RiskOverviewItem {
  asset_id: number
  asset_code: string
  ip: string
  hostname?: string
  risk_score: number
  risk_level: string
  affected_children_count: number
}

interface PropagationNode {
  asset_code: string
  ip: string
  hostname?: string
  risk_score: number
  relation?: string
  is_entry_point: boolean
}

interface RiskHotspot {
  entry_asset: { asset_code: string; ip: string; hostname?: string; risk_score: number }
  root_asset: { asset_code: string; ip: string }
  max_risk_score: number
  path: string[]
  risk_description: string
  chain_length: number
  nodes: PropagationNode[]
}

// ── Attack Path SVG Visualization ───────────────────────────────────────────

const NODE_R = 28
const H_GAP = 90
const V_GAP = 80
const V_OFFSET = 60

function AttackPathSVG({ hotspots }: { hotspots: RiskHotspot[] }) {
  const { t } = useTranslation()
  const svgRef = useRef<SVGSVGElement>(null)

  if (hotspots.length === 0) {
    return (
      <Empty
        description={t('topology.noAttackPaths')}
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    )
  }

  // Calculate SVG dimensions
  const maxNodes = Math.max(...hotspots.map(h => h.nodes?.length || 0))
  const width = Math.max(600, maxNodes * (NODE_R * 2 + H_GAP) + H_GAP * 2)
  const height = hotspots.length * V_GAP + V_OFFSET * 2

  return (
    <div style={{ overflowX: 'auto', padding: '8px 0' }}>
      <svg
        ref={svgRef}
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        style={{ minWidth: 600, background: '#fafafa', borderRadius: 8 }}
      >
        <defs>
          <marker
            id="arrow-red"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="4"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M0,0 L0,8 L8,4 z" fill="#ff4d4f" />
          </marker>
          <marker
            id="arrow-blue"
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M0,0 L0,6 L6,3 z" fill="#1677ff" />
          </marker>
          <filter id="glow-red">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {hotspots.map((hotspot, rowIdx) => {
          const level = hotspot.max_risk_score >= 70 ? 'critical' : 'high'
          const rowY = V_OFFSET + rowIdx * V_GAP
          const nodes = hotspot.nodes || []
          if (nodes.length === 0) return null

          const totalWidth = nodes.length * (NODE_R * 2 + H_GAP) - H_GAP
          const startX = (width - totalWidth) / 2 + NODE_R

          return (
            <g key={rowIdx}>
              {/* Path lines */}
              {nodes.slice(1).map((_, ni) => {
                const x1 = startX + ni * (NODE_R * 2 + H_GAP) - NODE_R
                const x2 = startX + (ni + 1) * (NODE_R * 2 + H_GAP) - NODE_R
                const isEntry = nodes[ni + 1]?.is_entry_point
                return (
                  <line
                    key={ni}
                    x1={x1}
                    y1={rowY}
                    x2={x2}
                    y2={rowY}
                    stroke={isEntry ? '#ff4d4f' : '#1677ff'}
                    strokeWidth={isEntry ? 2.5 : 1.5}
                    strokeDasharray={isEntry ? '6,3' : '4,2'}
                    markerEnd={isEntry ? 'url(#arrow-red)' : 'url(#arrow-blue)'}
                  />
                )
              })}

              {/* Nodes */}
              {nodes.map((node, ni) => {
                const cx = startX + ni * (NODE_R * 2 + H_GAP) - NODE_R
                const isEntry = node.is_entry_point
                const isFirst = ni === 0
                const isLast = ni === nodes.length - 1

                return (
                  <g key={ni}>
                    {/* Glow ring for entry nodes */}
                    {isEntry && (
                      <circle
                        cx={cx}
                        cy={rowY}
                        r={NODE_R + 6}
                        fill="none"
                        stroke="#ff4d4f"
                        strokeWidth={2}
                        opacity={0.4}
                        filter="url(#glow-red)"
                      />
                    )}
                    {/* Node circle */}
                    <circle
                      cx={cx}
                      cy={rowY}
                      r={NODE_R}
                      fill={isEntry ? '#fff1f0' : '#f0f5ff'}
                      stroke={isEntry ? '#ff4d4f' : '#1677ff'}
                      strokeWidth={isEntry ? 2.5 : 1.5}
                      style={{ cursor: 'pointer' }}
                    />
                    {/* Node label */}
                    <text
                      x={cx}
                      y={rowY + 4}
                      textAnchor="middle"
                      fontSize={10}
                      fontWeight={isEntry ? 'bold' : 'normal'}
                      fill={isEntry ? '#cf1322' : '#0958d9'}
                    >
                      {node.asset_code?.slice(0, 8) || `N${ni}`}
                    </text>
                    {/* Risk score badge */}
                    {isEntry && (
                      <g>
                        <circle
                          cx={cx + NODE_R - 4}
                          cy={rowY - NODE_R + 4}
                          r={10}
                          fill="#ff4d4f"
                        />
                        <text
                          x={cx + NODE_R - 4}
                          y={rowY - NODE_R + 7}
                          textAnchor="middle"
                          fontSize={9}
                          fontWeight="bold"
                          fill="white"
                        >
                          {node.risk_score || hotspot.max_risk_score}
                        </text>
                      </g>
                    )}
                  </g>
                )
              })}

              {/* Description row */}
              <text
                x={width / 2}
                y={rowY + NODE_R + 16}
                textAnchor="middle"
                fontSize={11}
                fill="#666"
              >
                {hotspot.risk_description?.slice(0, 60) || `${hotspot.nodes.length} {t('topology.nodes')}`}
              </text>
            </g>
          )
        })}

        {/* Legend */}
        <g transform={`translate(${width - 180}, 10)`}>
          <circle cx="10" cy="10" r="8" fill="#fff1f0" stroke="#ff4d4f" strokeWidth="2" />
          <text x="24" y="14" fontSize="11" fill="#666">{t('topology.entryPoint')}</text>
          <circle cx="10" cy="32" r="8" fill="#f0f5ff" stroke="#1677ff" />
          <text x="24" y="36" fontSize="11" fill="#666">{t('topology.intermediate')}</text>
          <line x1="2" y1="54" x2="18" y2="54" stroke="#ff4d4f" strokeWidth="2" strokeDasharray="4,2" />
          <text x="24" y="58" fontSize="11" fill="#666">{t('topology.attackPath')}</text>
        </g>
      </svg>

      {/* Hotspot list below SVG */}
      <div style={{ marginTop: 12 }}>
        {hotspots.map((h, i) => {
          const level = h.max_risk_score >= 70 ? 'critical' : 'high'
          return (
            <Card key={i} size="small" bodyStyle={{ padding: '8px 12px' }} style={{ marginBottom: 6, borderLeft: `3px solid ${RISK_COLOR[level]}` }}>
              <Space size={8}>
                <Tag color={RISK_COLOR[level]}>{h.max_risk_score} pts</Tag>
                <Text style={{ fontSize: 12 }}>
                  {h.nodes?.map((n, ni) => (
                    <span key={ni}>
                      {ni > 0 && <Text type="secondary"> ← </Text>}
                      <Tag color={n.is_entry_point ? RISK_COLOR[level] : 'blue'} style={{ fontSize: 11 }}>
                        {n.asset_code}
                      </Tag>
                    </span>
                  ))}
                </Text>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {h.risk_description?.slice(0, 50)}
                </Text>
              </Space>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

export default function AssetTopology() {
  const { t } = useTranslation()
  const [assets, setAssets] = useState<{ id: number; asset_code: string; ip: string; hostname?: string; asset_category: string }[]>([])
  const [relationships, setRelationships] = useState<FlatRel[]>([])
  const [treeNodes, setTreeNodes] = useState<DataNode[]>([])
  const [loading, setLoading] = useState(true)
  const [riskMap, setRiskMap] = useState<Record<number, RiskOverviewItem>>({})
  const [hotspots, setHotspots] = useState<RiskHotspot[]>([])
  const [rightTab, setRightTab] = useState<string>('relations')

  const REL_LABEL: Record<string, string> = {
    hosts_vm: t('topology.vm'),
    hosts_container: t('topology.container'),
    runs_service: t('topology.service'),
    network_peer: t('topology.networkPeer'),
    belongs_to: t('topology.belongsTo'),
  }

  const RISK_LABEL: Record<string, string> = {
    critical: t('risk.critical'),
    high: t('risk.high'),
    medium: t('risk.medium'),
    low: t('risk.low'),
  }

  // Build a custom tree node with expand trigger
  const nodeToDataNode = (
    node: HierarchyNode,
    riskMap?: Record<number, { risk_score: number; risk_level: string; affected_children_count: number }>,
  ): DataNode => {
    const { asset, children, relation_type } = node
    const risk = riskMap?.[asset.id]
    const riskColor = risk ? RISK_COLOR[risk.risk_level] || '#999' : '#999'
    const relTag = relation_type ? (
      <Tag color={REL_COLOR[relation_type]} style={{ fontSize: 11, marginLeft: 4 }}>
        {REL_LABEL[relation_type] || relation_type}
      </Tag>
    ) : null

    return {
      key: String(asset.id),
      title: (
        <Space size={4} wrap>
          {risk && (
            <div
              title={t('topology.riskScoreTitle', { score: risk.risk_score, level: RISK_LABEL[risk.risk_level] })}
              style={{
                width: 6, height: 6, borderRadius: '50%',
                background: riskColor,
                marginRight: 2,
                flexShrink: 0,
              }}
            />
          )}
          <AppstoreOutlined style={{ color: CAT_COLOR[asset.asset_category] || '#999' }} />
          {relTag}
          <Text strong style={{ fontSize: 13 }}>{asset.asset_code}</Text>
          <Text style={{ fontSize: 13 }}>{asset.ip}</Text>
          {asset.hostname && <Text type="secondary" style={{ fontSize: 12 }}>({asset.hostname})</Text>}
          {risk && (
            <Tag color={riskColor} style={{ fontSize: 11 }}>
              {risk.risk_score}{t('topology.points')}
            </Tag>
          )}
          {asset.account_count > 0 && (
            <Popover
              title={<Space size={4}><UserOutlined />{t('topology.accountList')}</Space>}
              content={
                <div style={{ minWidth: 260, maxHeight: 320, overflowY: 'auto' }}>
                  {asset.latest_accounts.length === 0 ? (
                    <Text type="secondary">{t('topology.noData')}</Text>
                  ) : asset.latest_accounts.map((a) => {
                    const lastLoginStr = a.last_login
                      ? new Date(a.last_login).toLocaleString('zh-CN')
                      : t('topology.neverLoggedIn')
                    return (
                      <div key={a.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
                        <Tag color={a.is_admin ? 'red' : 'default'} style={{ minWidth: 44, textAlign: 'center' }}>
                          {a.is_admin ? t('user.admin') : t('user.user')}
                        </Tag>
                        <Text style={{ fontSize: 13, flex: 1, wordBreak: 'break-all' }}>{a.username}</Text>
                        <Tag color={a.account_status === 'enabled' ? 'green' : 'orange'} style={{ fontSize: 11 }}>
                          {a.account_status === 'enabled' ? t('user.enabled') : a.account_status === 'disabled' ? t('user.disabled') : a.account_status || '—'}
                        </Tag>
                        <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{lastLoginStr}</Text>
                      </div>
                    )
                  })}
                  {asset.account_count > 10 && (
                    <Text type="secondary" style={{ fontSize: 12, marginTop: 6 }}>{t('topology.moreAccounts', { count: asset.account_count - 10 })}</Text>
                  )}
                </div>
              }
              placement="right"
              trigger="hover"
            >
              <Tag
                icon={asset.admin_count > 0 ? <SafetyCertificateOutlined /> : <UserOutlined />}
                color={asset.admin_count > 0 ? 'red' : 'default'}
                style={{ fontSize: 11, cursor: 'pointer' }}
              >
                {asset.account_count}
                {asset.admin_count > 0 ? ` (${asset.admin_count} admin)` : ''}
              </Tag>
            </Popover>
          )}
        </Space>
      ),
      children: children.map(child => nodeToDataNode(child, riskMap)),
    }
  }

  const fetchData = () => {
    setLoading(true)
    Promise.all([
      api.get('/assets'),
      api.get('/asset-relationships'),
      getRiskOverview({ limit: 100 }),
      getRiskHotspots({ threshold: 40 }),
    ])
      .then(([assetsRes, relsRes, riskRes, hotspotsRes]) => {
        setAssets(assetsRes.data)
        setRelationships(relsRes.data)

        // Build risk map
        const rm: Record<number, RiskOverviewItem> = {}
        for (const item of riskRes.data.results as RiskOverviewItem[]) {
          rm[item.asset_id] = item
        }
        setRiskMap(rm)
        setHotspots((hotspotsRes.data.hotspots || []) as RiskHotspot[])

        const allIds: Set<number> = new Set(assetsRes.data.map((a: { id: number }) => a.id))
        const childIds: Set<number> = new Set(relsRes.data.map((r: FlatRel) => r.child_id))
        const rootIds: number[] = [...allIds].filter(id => !childIds.has(id))

        const fetchHierarchy = (assetId: number) =>
          api.get(`/assets/${assetId}/hierarchy`)
            .then(r => nodeToDataNode(r.data as HierarchyNode, rm))
            .catch(() => null)

        Promise.all(rootIds.map(fetchHierarchy)).then(results => {
          setTreeNodes(results.filter(Boolean) as DataNode[])
        })
      })
      .catch(() => message.error(t('msg.loadFailed')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchData() }, [])

  const handleDeleteRel = async (relId: number) => {
    try {
      await api.delete(`/asset-relationships/${relId}`)
      message.success(t('topology.relationDeleted'))
      fetchData()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.deleteFailed'))
    }
  }

  if (loading) return <div style={{ textAlign: 'center', marginTop: 60 }}><Spin size="large" /></div>

  // Count total accounts across all assets
  const totalAccounts = relationships.length === 0 && assets.length === 0 ? 0
    : treeNodes.reduce((acc, node) => {
        const countNode = (n: DataNode): number => {
          const hn = n as unknown as HierarchyNode
          return (hn.asset?.account_count || 0) +
            (n.children || []).reduce((c, child) => c + countNode(child), 0)
        }
        return acc + countNode(node)
      }, 0)

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>{t('topology.title')}</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            {t('topology.subtitle')}
          </Text>
        </div>
        <Space>
          <Space size={16}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {relationships.length} {t('topology.relations')}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {assets.length} {t('topology.assets')}
            </Text>
          </Space>
          <Button icon={<ReloadOutlined />} onClick={fetchData}>{t('btn.refresh')}</Button>
        </Space>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16, alignItems: 'start' }}>
        {/* Tree */}
        <Card bodyStyle={{ padding: 12, minHeight: 480 }}>
          {treeNodes.length === 0 ? (
            <Empty description={t('topology.noRelations')}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('topology.addRelationHint')}
              </Text>
            </Empty>
          ) : (
            <Tree
              showLine={{ showLeafIcon: false }}
              defaultExpandAll
              treeData={treeNodes}
              style={{ minHeight: 440 }}
            />
          )}
        </Card>

        {/* Right panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Legend */}
          <Card title={t('topology.relationTypes')} bodyStyle={{ padding: '8px 16px' }} size="small">
            <Space wrap size={[8, 8]}>
              {Object.entries(REL_LABEL).map(([k, v]) => (
                <Tag key={k} color={REL_COLOR[k]} style={{ fontSize: 12 }}>{v}</Tag>
              ))}
              <div style={{ width: '100%', borderTop: '1px solid #f0f0f0', marginTop: 4 }} />
              {Object.entries(RISK_LABEL).map(([k, v]) => (
                <Tag key={k} color={RISK_COLOR[k]} style={{ fontSize: 12 }}>{v}{t('risk.label')}</Tag>
              ))}
            </Space>
          </Card>

          <Tabs
            activeKey={rightTab}
            onChange={setRightTab}
            size="small"
            items={[
              {
                key: 'relations',
                label: <span><BranchesOutlined />{t('topology.relations')}</span>,
                children: (
                  <Card
                    bodyStyle={{ padding: 0, maxHeight: 400, overflowY: 'auto' }}
                    extra={<Text type="secondary" style={{ fontSize: 11 }}>{relationships.length} {t('topology.items')}</Text>}
                  >
                    {relationships.length === 0 ? (
                      <Empty description={t('topology.noRelationsItem')} style={{ margin: '40px 0' }} />
                    ) : (
                      relationships.map(rel => (
                        <div
                          key={rel.id}
                          style={{
                            padding: '8px 12px',
                            borderBottom: '1px solid #f0f0f0',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            fontSize: 12,
                          }}
                        >
                          <Tag color="blue" style={{ fontSize: 11 }}>{rel.parent.asset_code}</Tag>
                          <Text type="secondary">→</Text>
                          <Tag color="blue" style={{ fontSize: 11 }}>{rel.child.asset_code}</Tag>
                          <Tag color={REL_COLOR[rel.relation_type]} style={{ fontSize: 10 }}>
                            {REL_LABEL[rel.relation_type] || rel.relation_type}
                          </Tag>
                          <Popconfirm
                            title={t('topology.confirmDeleteRelation')}
                            onConfirm={() => handleDeleteRel(rel.id)}
                            okText={t('btn.delete')}
                            okButtonProps={{ danger: true }}
                            cancelText={t('btn.cancel')}
                          >
                            <Button
                              type="text"
                              size="small"
                              danger
                              icon={
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <polyline points="3,6 5,6 21,6"/><path d="M19,6l-1,14a2,2,0,0,1-2,2H8a2,2,0,0,1-2-2L5,6"/>
                                  <path d="M10,11v6"/><path d="M14,11v6"/><path d="M9,6V4a1,1,0,0,1,1-1h4a1,1,0,0,1,1,1V6"/>
                                </svg>
                              }
                              style={{ marginLeft: 'auto' }}
                            />
                          </Popconfirm>
                        </div>
                      ))
                    )}
                  </Card>
                ),
              },
              {
                key: 'hotspots',
                label: (
                  <Space size={4}>
                    <WarningOutlined />
                    {t('topology.riskHotspots')}
                    {hotspots.length > 0 && (
                      <Badge count={hotspots.length} size="small" style={{ fontSize: 10 }} />
                    )}
                  </Space>
                ),
                children: (
                  <Card
                    bodyStyle={{ padding: 0, maxHeight: 400, overflowY: 'auto' }}
                    extra={
                      <Space size={4}>
                        <Text type="secondary" style={{ fontSize: 11 }}>{t('topology.threshold')} ≥40</Text>
                      </Space>
                    }
                  >
                    {hotspots.length === 0 ? (
                      <Empty description={t('topology.noRiskPaths')} style={{ margin: '40px 0' }} />
                    ) : (
                      hotspots.map((h, i) => {
                        const level = h.max_risk_score >= 70 ? 'critical' : 'high'
                        const relLabel: Record<string, string> = {
                          hosts_vm: t('topology.vm'),
                          hosts_container: t('topology.container'),
                          runs_service: t('topology.service'),
                          network_peer: t('topology.networkPeer'),
                          belongs_to: t('topology.belongsTo'),
                        }
                        return (
                          <div
                            key={i}
                            style={{
                              padding: '10px 12px',
                              borderBottom: '1px solid #f0f0f0',
                              background: `${RISK_COLOR[level]}08`,
                            }}
                          >
                            <Space style={{ marginBottom: 6 }}>
                              <Tag color={RISK_COLOR[level]} style={{ fontSize: 11 }}>
                                {h.max_risk_score}{t('topology.points')}
                              </Tag>
                              <Text type="secondary" style={{ fontSize: 11 }}>
                                {t('topology.chain')} {h.chain_length} {t('topology.layers')}
                              </Text>
                            </Space>
                            {(h.nodes || []).length > 0 ? (
                              <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
                                {(h.nodes || []).map((node, ni) => (
                                  <span key={ni} style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
                                    {ni > 0 && (
                                      <Text type="secondary" style={{ fontSize: 11 }}>
                                        ← <Tag color="purple" style={{ fontSize: 10, margin: '0 2px' }}>
                                          {relLabel[node.relation || ''] || node.relation || ''}
                                        </Tag>
                                      </Text>
                                    )}
                                    <Tag color="blue" style={{ fontSize: 10 }}>{node.asset_code}</Tag>
                                    {node.is_entry_point && (
                                      <Tag color={RISK_COLOR[level]} style={{ fontSize: 10 }}>
                                        {node.risk_score}{t('topology.points')}
                                      </Tag>
                                    )}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <div style={{ fontSize: 12 }}>
                                <Tag color="blue" style={{ marginRight: 4 }}>{h.entry_asset.asset_code}</Tag>
                                <Text type="secondary" style={{ fontSize: 11 }}>({h.entry_asset.ip})</Text>
                                <Text type="secondary" style={{ margin: '0 4px' }}>→</Text>
                                <Tag color="blue" style={{ marginRight: 4 }}>{h.root_asset.asset_code}</Tag>
                              </div>
                            )}
                            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 2 }}>
                              {h.risk_description}
                            </Text>
                          </div>
                        )
                      })
                    )}
                  </Card>
                ),
              },
              {
                key: 'attack-path',
                label: (
                  <Space size={4}>
                    <AimOutlined />
                    {t('topology.attackPath')}
                    {hotspots.length > 0 && (
                      <Badge count={hotspots.length} size="small" style={{ fontSize: 10 }} />
                    )}
                  </Space>
                ),
                children: (
                  <AttackPathSVG hotspots={hotspots} />
                ),
              },
            ]}
          />
        </div>
      </div>
    </div>
  )
}
