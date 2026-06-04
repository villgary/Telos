/**
 * AI Agent Detail Page — basic info, capabilities, credentials, risk signals.
 */
import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Typography, Spin, Button, Space, Empty,
  Row, Col, message, Result,
} from 'antd'
import { RobotOutlined, KeyOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { getAIAgent, claimAIAgent } from '../api/client'

const { Title, Text, Paragraph } = Typography

const LEVEL_COLORS: Record<string, string> = {
  critical: 'red', high: 'orange', medium: 'gold', low: 'green',
}

interface RiskSignal {
  signal: string
  weight: string
  evidence?: string
}

interface AIAgent {
  agent_name: string
  framework: string
  risk_level: string
  status: string
  owner_user?: string | null
  owner_team?: string | null
  model?: string | null
  last_seen_at: string
  discovered_at: string
  capabilities?: {
    filesystem?: boolean
    network?: boolean
    code_exec?: boolean
    tool_count?: number
  }
  api_key_fingerprint?: string | null
  api_key_location?: string | null
  risk_signals?: RiskSignal[]
  asset_id?: number | null
  nhi_identity_id?: number | null
}

export default function AIAgentDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [agent, setAgent] = useState<AIAgent | null>(null)
  const [loading, setLoading] = useState(true)
  const [claiming, setClaiming] = useState(false)

  const load = async () => {
    if (!id) return
    setLoading(true)
    try {
      const r = await getAIAgent(Number(id))
      setAgent(r.data)
    } catch {
      message.error(t('aiAgent.detail.notFound'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const onClaim = async () => {
    setClaiming(true)
    try {
      const r = await claimAIAgent(Number(id))
      setAgent(r.data)
      message.success(t('aiAgent.detail.owned', { user: r.data.owner_user }))
    } catch {
      message.error(t('aiAgent.detail.claimFailed'))
    } finally {
      setClaiming(false)
    }
  }

  if (loading) return <Spin style={{ width: '100%', marginTop: 80 }} />
  if (!agent) return <Result status="404" title={t('aiAgent.detail.notFound')} />

  const caps = agent.capabilities || {}
  const signals = agent.risk_signals || []

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row align="middle" gutter={16}>
          <Col flex="auto">
            <Space size="middle">
              <Title level={3} style={{ margin: 0 }}>
                <RobotOutlined /> {agent.agent_name}
              </Title>
              <Tag color="blue">{t(`aiAgent.framework.${agent.framework}`, { defaultValue: agent.framework })}</Tag>
              <Tag color={LEVEL_COLORS[agent.risk_level]}>{agent.risk_level.toUpperCase()}</Tag>
              <Tag>{agent.status}</Tag>
            </Space>
          </Col>
          <Col>
            {!agent.owner_user && (
              <Button type="primary" icon={<KeyOutlined />} loading={claiming} onClick={onClaim}>
                {t('aiAgent.detail.claimOwner')}
              </Button>
            )}
            {agent.owner_user && (
              <Text type="secondary">{t('aiAgent.detail.owned', { user: agent.owner_user })}</Text>
            )}
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        <Col span={12}>
          <Card title={t('aiAgent.detail.basicInfo')} size="small">
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label={t('aiAgent.detail.model')}>
                {agent.model || '—'}
              </Descriptions.Item>
              <Descriptions.Item label={t('aiAgent.detail.ownerTeam')}>
                {agent.owner_team || '—'}
              </Descriptions.Item>
              <Descriptions.Item label={t('aiAgent.detail.ownerUser')}>
                {agent.owner_user || '—'}
              </Descriptions.Item>
              <Descriptions.Item label={t('aiAgent.detail.lastSeen')}>
                {agent.last_seen_at}
              </Descriptions.Item>
              <Descriptions.Item label={t('aiAgent.detail.discovered')}>
                {agent.discovered_at}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col span={12}>
          <Card title={t('aiAgent.detail.capabilities')} size="small">
            <Space wrap>
              {caps.filesystem && <Tag color="purple">{t('aiAgent.capability.filesystem')}</Tag>}
              {caps.network && <Tag color="cyan">{t('aiAgent.capability.network')}</Tag>}
              {caps.code_exec && <Tag color="red">{t('aiAgent.capability.codeExec')}</Tag>}
              <Tag>{t('aiAgent.capability.toolCount', { count: caps.tool_count || 0 })}</Tag>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title={t('aiAgent.detail.credentials')} size="small" style={{ marginTop: 16 }}>
        <Space direction="vertical">
          <div>
            <Text type="secondary">{t('aiAgent.detail.fingerprint')}: </Text>
            <Text code>{agent.api_key_fingerprint || t('aiAgent.detail.noKey')}</Text>
          </div>
          {agent.api_key_location && (
            <div>
              <Text type="secondary">{t('aiAgent.detail.location')}: </Text>
              <Text>{agent.api_key_location}</Text>
            </div>
          )}
        </Space>
      </Card>

      <Card title={t('aiAgent.detail.riskSignals')} size="small" style={{ marginTop: 16 }}>
        {signals.length === 0 ? (
          <Empty description={t('aiAgent.detail.noRiskSignals')} />
        ) : (
          <Space direction="vertical" style={{ width: '100%' }}>
            {signals.map((s, i) => (
              <div key={i}>
                <Tag color={LEVEL_COLORS['high']}>{s.weight}</Tag>
                <Text strong>{s.signal}</Text>
                {s.evidence && <Paragraph type="secondary" style={{ margin: 0, marginLeft: 8 }}>{s.evidence}</Paragraph>}
              </div>
            ))}
          </Space>
        )}
      </Card>

      <Card title={t('aiAgent.detail.related')} size="small" style={{ marginTop: 16 }}>
        <Space direction="vertical">
          {agent.asset_id && (
            <div>
              <Text>{t('aiAgent.detail.relatedAsset')}: </Text>
              <Link to={`/assets/${agent.asset_id}`}>#{agent.asset_id}</Link>
            </div>
          )}
          {agent.nhi_identity_id && (
            <div>
              <Text>{t('aiAgent.detail.relatedNHI')}: </Text>
              <Link to={`/nhi/${agent.nhi_identity_id}`}>#{agent.nhi_identity_id}</Link>
            </div>
          )}
          {!agent.asset_id && !agent.nhi_identity_id && <Text type="secondary">—</Text>}
        </Space>
      </Card>

      <div style={{ marginTop: 16 }}>
        <Button onClick={() => navigate('/ai-agents')}>← {t('aiAgent.detail.back')}</Button>
      </div>
    </div>
  )
}
