import { useState, useEffect } from 'react'
import {
  Card, Row, Col, Space, Button, Select, Slider,
  Statistic, Alert, Tag, Table, Typography,
} from 'antd'
const { Text } = Typography
import {
  ThunderboltOutlined, CrownOutlined, TeamOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  getThreatGraph, whatifSimulate,
  ThreatNode, WhatIfSimulationResult, WhatIfReachableNode,
} from '../api/client'

interface WhatIfSimulatorProps { analysisId: number }

export default function WhatIfSimulator({ analysisId }: WhatIfSimulatorProps) {
  const { t } = useTranslation()
  const [graphNodes, setGraphNodes] = useState<ThreatNode[]>([])
  const [selectedNode, setSelectedNode] = useState<string>('')
  const [maxHops, setMaxHops] = useState(5)
  const [simResult, setSimResult] = useState<WhatIfSimulationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingGraph, setLoadingGraph] = useState(false)

  useEffect(() => {
    setLoadingGraph(true)
    getThreatGraph(analysisId)
      .then(r => setGraphNodes(r.data.nodes || []))
      .catch(() => setGraphNodes([]))
      .finally(() => setLoadingGraph(false))
  }, [analysisId])

  const runSimulation = async () => {
    if (!selectedNode) return
    setLoading(true)
    try {
      const r = await whatifSimulate(analysisId, selectedNode, maxHops)
      setSimResult(r.data)
    } catch {
      setSimResult(null)
    } finally {
      setLoading(false)
    }
  }

  const levelColors: Record<string, string> = {
    critical: '#93281b', high: '#e83e3e', medium: '#f5c518',
    low: '#52c41a', minimal: '#8c8c8c',
  }

  const EDGE_TYPE_LABELS: Record<string, string> = {
    ssh_key_reuse: t('threat.edgeSshKeyReuse'),
    auth_chain: t('threat.edgeAuthChain'),
    permission_propagation: t('threat.edgePermissionPropagation'),
  }

  const nodeOptions = graphNodes
    .filter(n => !n.id.startsWith('identity_'))
    .map(n => ({
      value: n.id,
      label: `${n.username} @ ${n.hostname || n.ip || `asset:${n.asset_id}`} ${n.is_admin ? '★' : ''}`,
    }))

  const src = simResult?.source_node as Record<string, unknown> | undefined

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={10}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text strong>{t('threat.selectPatientZero')}</Text>
            {loadingGraph ? (
              <Text type="secondary">{t('threat.analyzing')}</Text>
            ) : (
              <Select
                showSearch
                placeholder={t('threat.selectNodePlaceholder')}
                value={selectedNode || undefined}
                onChange={v => setSelectedNode(v)}
                options={nodeOptions}
                style={{ width: '100%' }}
                filterOption={(input, option) =>
                  (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                }
              />
            )}
          </Space>
        </Col>
        <Col span={4}>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>{t('threat.maxHops')}: {maxHops}</Text>
          <Slider min={1} max={10} value={maxHops} onChange={v => setMaxHops(v)} />
        </Col>
        <Col span={4}>
          <Button
            type="primary"
            danger
            icon={<ThunderboltOutlined />}
            onClick={runSimulation}
            loading={loading}
            disabled={!selectedNode}
            style={{ marginTop: 24 }}
          >
            {t('threat.runSimulation')}
          </Button>
        </Col>
        <Col span={6}>
          {simResult && (
            <Card size="small" style={{ background: levelColors[simResult.blast_radius_level] || '#f5f5f5', border: 'none' }}>
              <Statistic
                title={<Text style={{ color: '#fff' }}>{t('threat.blastRadiusScore')}</Text>}
                value={simResult.blast_radius_score}
                suffix={<Text style={{ color: '#fff', fontSize: 12 }}>/ {simResult.blast_radius_level.toUpperCase()}</Text>}
                valueStyle={{ color: '#fff' }}
              />
            </Card>
          )}
        </Col>
      </Row>

      {simResult && (
        <>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            {[
              { label: t('threat.totalReachable'), value: simResult.total_reachable, color: '#1890ff' },
              { label: t('threat.humanReachable'), value: simResult.human_reachable, color: '#52c41a' },
              { label: t('threat.adminReachable'), value: simResult.admin_reachable, color: '#f5222d' },
              { label: t('threat.privilegedReachable'), value: simResult.privileged_reachable, color: '#fa8c16' },
              { label: t('threat.assetCount'), value: simResult.asset_count, color: '#722ed1' },
            ].map(m => (
              <Col key={m.label} span={4}>
                <Card size="small" style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 22, fontWeight: 700, color: m.color }}>{m.value}</div>
                  <Text type="secondary" style={{ fontSize: 11 }}>{m.label}</Text>
                </Card>
              </Col>
            ))}
          </Row>

          <Row gutter={[16, 16]}>
            <Col span={8}>
              <Card size="small" title={<Space><CrownOutlined />{t('threat.applicableTechniques')}</Space>}>
                {simResult.mitre_techniques.length === 0 ? (
                  <Text type="secondary">{t('threat.noTechniques')}</Text>
                ) : (
                  <Space direction="vertical" style={{ width: '100%' }} size="small">
                    {simResult.mitre_techniques.map(tech => (
                      <Alert
                        key={tech.technique_id}
                        type={tech.severity === 'critical' ? 'error' : tech.severity === 'high' ? 'warning' : 'info'}
                        message={
                          <Space direction="vertical" size={2}>
                            <Space>
                              <Tag color={tech.severity === 'critical' ? 'red' : tech.severity === 'high' ? 'orange' : 'blue'}>
                                {tech.technique_id}
                              </Tag>
                              <Text strong>{tech.name}</Text>
                            </Space>
                            <Text type="secondary" style={{ fontSize: 11 }}>{tech.rationale}</Text>
                          </Space>
                        }
                      />
                    ))}
                  </Space>
                )}
              </Card>
            </Col>

            <Col span={16}>
              <Card size="small" title={<Space><TeamOutlined />{t('threat.reachableAccounts')} ({simResult.total_reachable})</Space>}>
                <Table
                  dataSource={simResult.reachable_nodes}
                  rowKey="snapshot_id"
                  size="small"
                  pagination={{ pageSize: 10, size: 'small' }}
                  columns={[
                    {
                      title: t('threat.username'),
                      key: 'username',
                      render: (_: any, row: WhatIfReachableNode) => (
                        <Space>
                          <Tag color={row.is_admin ? 'red' : 'green'}>{row.username}</Tag>
                          {row.is_admin && <Text type="danger" style={{ fontSize: 11 }}>★ admin</Text>}
                        </Space>
                      ),
                    },
                    {
                      title: t('threat.hostname'),
                      key: 'hostname',
                      render: (_: any, row: WhatIfReachableNode) =>
                        row.hostname || row.ip || `asset:${row.asset_id}`,
                    },
                    {
                      title: t('threat.hops'),
                      key: 'hops',
                      width: 60,
                      render: (_: any, row: WhatIfReachableNode) => (
                        <Tag color={row.hops === 1 ? 'red' : row.hops === 2 ? 'orange' : 'blue'}>
                          {row.hops} hop{row.hops > 1 ? 's' : ''}
                        </Tag>
                      ),
                    },
                    {
                      title: t('threat.entryEdge'),
                      key: 'entry_edge_type',
                      render: (_: any, row: WhatIfReachableNode) => (
                        <Tag color={row.entry_edge_type === 'ssh_key_reuse' ? 'red' : row.entry_edge_type === 'permission_propagation' ? 'blue' : 'orange'}>
                          {EDGE_TYPE_LABELS[row.entry_edge_type] || row.entry_edge_type}
                        </Tag>
                      ),
                    },
                    {
                      title: t('threat.accountLevel'),
                      key: 'account_level',
                      width: 80,
                      render: (_: any, row: WhatIfReachableNode) => {
                        const score = row.is_admin ? 75 : 25
                        return <Text type={score >= 75 ? 'danger' : 'secondary'}>{score}</Text>
                      },
                    },
                  ]}
                />
              </Card>
            </Col>
          </Row>

          {src && (
            <Card size="small" style={{ marginTop: 16 }} title={t('threat.patientZeroSummary')}>
              <Row gutter={[8, 8]}>
                <Col span={4}>
                  <Tag color="red" style={{ fontSize: 13, padding: '4px 12px' }}>
                    {(src.username as string) || '?'} ⚠️ PATIENT ZERO
                  </Tag>
                </Col>
                <Col span={4}>
                  <Text type="secondary">{t('threat.hostname')}: </Text>
                  <Text>{(src.hostname as string) || (src.ip as string) || `asset:${src.asset_id}`}</Text>
                </Col>
                <Col span={4}>
                  <Text type="secondary">{t('threat.lifecycle')}: </Text>
                  <Text>{(src.lifecycle as string)}</Text>
                </Col>
                <Col span={4}>
                  <Text type="secondary">{t('threat.isAdmin')}: </Text>
                  <Text>{src.is_admin ? t('threat.yes') : t('threat.no')}</Text>
                </Col>
                <Col span={4}>
                  <Text type="secondary">{t('threat.accountStatus')}: </Text>
                  <Text>{(src.account_status as string)}</Text>
                </Col>
                <Col span={4}>
                  <Text type="secondary">{t('threat.blastRadiusScore')}: </Text>
                  <Text strong style={{ color: levelColors[simResult.blast_radius_level] }}>
                    {simResult.blast_radius_score} ({simResult.blast_radius_level})
                  </Text>
                </Col>
              </Row>
            </Card>
          )}
        </>
      )}

      {!simResult && selectedNode && !loading && (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#ccc' }}>
          <ThunderboltOutlined style={{ fontSize: 48 }} />
          <div style={{ marginTop: 12 }}>{t('threat.clickSimulate')}</div>
        </div>
      )}
    </div>
  )
}
