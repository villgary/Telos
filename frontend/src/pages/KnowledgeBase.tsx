import { useState, useEffect } from 'react'
import {
  Card, Typography, Input, List, Tag, Space, Button,
  Drawer, Descriptions, Row, Col, Tabs, message, Spin,
  Empty, Tooltip, Badge
} from 'antd'
import {
  SearchOutlined, QuestionCircleOutlined, BookOutlined,
  WarningOutlined, ThunderboltOutlined, CheckCircleOutlined,
  FilterOutlined
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  searchKnowledgeBase, askKnowledgeBase, getKnowledgeBaseStats,
  listKBTactics, listKBCVEs, listKBPractices
} from '../api/client'
import i18n from '../i18n'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

interface KBSource {
  type: string
  id?: string
  title: string
}

interface KBEntry {
  type: string
  id?: string
  cve?: string
  product?: string
  title?: string
  name?: string
  category?: string
  description?: string
  severity?: string
  remediation?: string
  mitigation?: string
  detection?: string
  principle?: string
  standard?: string
  implementation?: string
  risk_if_missing?: string
  mitre_ref?: string
  mitre?: string
  cvss?: string | number
  platforms?: string[]
  detection_hints?: string[]
  indicators?: string[]
  related_cves?: string[]
  affected_versions?: string
  sub?: string
  exploitation?: string
  [key: string]: unknown
}

export default function KnowledgeBase() {
  const { t, i18n } = useTranslation()

  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState<KBEntry[]>([])
  const [searching, setSearching] = useState(false)

  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState<KBSource[]>([])
  const [asking, setAsking] = useState(false)
  const [history, setHistory] = useState<Array<{ q: string; a: string; src: KBSource[] }>>([])

  const [stats, setStats] = useState<{ mitre_count: number; cve_count: number; practice_count: number } | null>(null)
  const [tactics, setTactics] = useState<KBEntry[]>([])
  const [cves, setCves] = useState<KBEntry[]>([])
  const [practices, setPractices] = useState<KBEntry[]>([])
  const [activeTab, setActiveTab] = useState('mitre')

  const [detailEntry, setDetailEntry] = useState<KBEntry | null>(null)

  useEffect(() => {
    const lang = i18n.language
    getKnowledgeBaseStats().then(r => setStats(r.data)).catch(() => {})
    listKBTactics().then(r => setTactics(r.data.data || [])).catch(() => {})
    listKBCVEs().then(r => setCves(r.data.data || [])).catch(() => {})
    listKBPractices().then(r => setPractices(r.data.data || [])).catch(() => {})
  }, [i18n.language])

  const handleSearch = async () => {
    if (!searchQ.trim()) return
    setSearching(true)
    try {
      const r = await searchKnowledgeBase(searchQ.trim())
      setSearchResults(r.data.results || [])
    } catch {
      message.error(t('msg.error'))
    } finally {
      setSearching(false)
    }
  }

  const handleAsk = async () => {
    if (!question.trim()) return
    setAsking(true)
    setAnswer('')
    setSources([])
    try {
      const r = await askKnowledgeBase(question.trim())
      setAnswer(r.data.answer)
      setSources(r.data.sources || [])
      setHistory(prev => [{ q: question, a: r.data.answer, src: r.data.sources || [] }, ...prev.slice(0, 9)])
      setQuestion('')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.error'))
    } finally {
      setAsking(false)
    }
  }

  const SEVERITY_COLOR: Record<string, string> = {
    critical: 'red', high: 'orange', medium: 'gold', low: 'green',
  }

  const TYPE_COLOR: Record<string, string> = {
    mitre: 'purple', cve: 'red', practice: 'blue',
  }

  // ── Render a single list entry ──────────────────────────────────────────────
  const renderEntry = (entry: KBEntry) => {
    if (entry.type === 'mitre') {
      return (
        <List.Item
          style={{ cursor: 'pointer', padding: '10px 12px' }}
          onClick={() => setDetailEntry(entry)}
          extra={
            <Space size={4}>
              <Tag color="purple">{entry.id}{entry.sub ? `.${entry.sub}` : ''}</Tag>
              <Tag color="default">{entry.platforms?.slice(0, 2).join(', ')}</Tag>
            </Space>
          }
        >
          <List.Item.Meta
            title={<Text strong style={{ fontSize: 13 }}>{entry.name}</Text>}
            description={
              <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                {entry.description}
              </Text>
            }
          />
        </List.Item>
      )
    }
    if (entry.type === 'cve') {
      return (
        <List.Item
          style={{ cursor: 'pointer', padding: '10px 12px' }}
          onClick={() => setDetailEntry(entry)}
          extra={
            <Space size={4}>
              <Tag color={SEVERITY_COLOR[entry.severity || 'medium']}>{entry.severity?.toUpperCase()}</Tag>
              <Text type="secondary" style={{ fontSize: 11 }}>CVSS {entry.cvss}</Text>
            </Space>
          }
        >
          <List.Item.Meta
            title={<Text strong style={{ fontSize: 13 }}>{entry.cve} — {entry.product}</Text>}
            description={
              <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                {entry.description}
              </Text>
            }
          />
        </List.Item>
      )
    }
    return (
      <List.Item
        style={{ cursor: 'pointer', padding: '10px 12px' }}
        onClick={() => setDetailEntry(entry)}
        extra={<Tag color="blue">{entry.category}</Tag>}
      >
        <List.Item.Meta
          title={<Text strong style={{ fontSize: 13 }}>{entry.title}</Text>}
          description={
            <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
              {entry.principle}
            </Text>
          }
        />
      </List.Item>
    )
  }

  // ── Browse tabs data ─────────────────────────────────────────────────────────
  const noDataText = t('kb.noData')
  const browseTabs: { key: string; label: React.ReactNode; children: React.ReactNode }[] = [
    {
      key: 'mitre',
      label: (
        <Space>
          <ThunderboltOutlined style={{ color: '#722ed1' }} />
          {t('kb.mitreAttck')} <Badge count={tactics.length} style={{ backgroundColor: '#722ed1', fontSize: 10 }} />
        </Space>
      ),
      children: (
        <List
          dataSource={tactics}
          renderItem={renderEntry}
          locale={{ emptyText: noDataText }}
          size="small"
          style={{ maxHeight: 380, overflow: 'auto' }}
        />
      ),
    },
    {
      key: 'cve',
      label: (
        <Space>
          <WarningOutlined style={{ color: '#eb2f96' }} />
          {t('kb.cveVulnStats')} <Badge count={cves.length} style={{ backgroundColor: '#eb2f96', fontSize: 10 }} />
        </Space>
      ),
      children: (
        <List
          dataSource={cves}
          renderItem={renderEntry}
          locale={{ emptyText: noDataText }}
          size="small"
          style={{ maxHeight: 380, overflow: 'auto' }}
        />
      ),
    },
    {
      key: 'practice',
      label: (
        <Space>
          <CheckCircleOutlined style={{ color: '#1890ff' }} />
          {t('kb.practicesLabel')} <Badge count={practices.length} style={{ backgroundColor: '#1890ff', fontSize: 10 }} />
        </Space>
      ),
      children: (
        <List
          dataSource={practices}
          renderItem={renderEntry}
          locale={{ emptyText: noDataText }}
          size="small"
          style={{ maxHeight: 380, overflow: 'auto' }}
        />
      ),
    },
  ]

  // ── Type label helper ────────────────────────────────────────────────────────
  const typeLabel = (type: string) => {
    const map: Record<string, string> = { mitre: t('kb.mitreAttck'), cve: t('kb.cveVulnStats'), practice: t('kb.practicesLabel') }
    return map[type] || type
  }

  return (
    <div style={{ padding: 0 }}>
      {/* Page header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <BookOutlined /> {t('nav.knowledgeBase')}
        </Title>
        <Space>
          <Input.Search
            placeholder={t('kb.searchPlaceholder')}
            value={searchQ}
            onChange={e => setSearchQ(e.target.value)}
            onSearch={handleSearch}
            loading={searching}
            enterButton={<SearchOutlined />}
            style={{ width: 280 }}
            allowClear
          />
        </Space>
      </div>

      {/* ── SECTION 1: Browse (top) ────────────────────────────────────────── */}
      <Card
        title={
          <Space>
            <FilterOutlined />
            {t('kb.browse')}
          </Space>
        }
        size="small"
        bodyStyle={{ padding: 0 }}
        style={{ marginBottom: 16 }}
      >
        <Row>
          {/* Stat cards — left sidebar */}
          <Col span={6} style={{ padding: '12px 16px', borderRight: '1px solid #f0f0f0' }}>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Tooltip title={t('kb.attackTacticsTip')}>
                <Card size="small" bodyStyle={{ padding: '10px 12px' }} style={{ background: '#f9f0ff', cursor: 'default' }}>
                  <Space>
                    <ThunderboltOutlined style={{ color: '#722ed1', fontSize: 20 }} />
                    <div>
                      <Text type="secondary" style={{ fontSize: 11 }}>{t('kb.mitreAttck')}</Text>
                      <div style={{ fontSize: 22, fontWeight: 600, color: '#722ed1', lineHeight: 1.2 }}>
                        {stats?.mitre_count ?? '-'}
                      </div>
                    </div>
                  </Space>
                </Card>
              </Tooltip>
              <Tooltip title={t('kb.cveDatabaseTip')}>
                <Card size="small" bodyStyle={{ padding: '10px 12px' }} style={{ background: '#fff1f0', cursor: 'default' }}>
                  <Space>
                    <WarningOutlined style={{ color: '#eb2f96', fontSize: 20 }} />
                    <div>
                      <Text type="secondary" style={{ fontSize: 11 }}>{t('kb.cveVulnStats')}</Text>
                      <div style={{ fontSize: 22, fontWeight: 600, color: '#eb2f96', lineHeight: 1.2 }}>
                        {stats?.cve_count ?? '-'}
                      </div>
                    </div>
                  </Space>
                </Card>
              </Tooltip>
              <Tooltip title={t('kb.secPracticeTip')}>
                <Card size="small" bodyStyle={{ padding: '10px 12px' }} style={{ background: '#f0f5ff', cursor: 'default' }}>
                  <Space>
                    <CheckCircleOutlined style={{ color: '#1890ff', fontSize: 20 }} />
                    <div>
                      <Text type="secondary" style={{ fontSize: 11 }}>{t('kb.secPracticeStats')}</Text>
                      <div style={{ fontSize: 22, fontWeight: 600, color: '#1890ff', lineHeight: 1.2 }}>
                        {stats?.practice_count ?? '-'}
                      </div>
                    </div>
                  </Space>
                </Card>
              </Tooltip>
              <Text type="secondary" style={{ fontSize: 11, textAlign: 'center', display: 'block' }}>
                {t('kb.browseTip')}
              </Text>
            </Space>
          </Col>

          {/* Browse tabs — right content */}
          <Col span={18} style={{ padding: '0' }}>
            <Tabs
              items={browseTabs}
              activeKey={activeTab}
              onChange={k => setActiveTab(k)}
              size="small"
              style={{ padding: '0 12px' }}
            />
          </Col>
        </Row>
      </Card>

      {/* ── SECTION 2: Q&A (bottom) ────────────────────────────────────────── */}
      <Card
        title={<Space><QuestionCircleOutlined />{t('kb.qa')}</Space>}
        size="small"
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <TextArea
            placeholder={t('kb.questionPlaceholder')}
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onPressEnter={e => { if (!e.shiftKey) { e.preventDefault(); handleAsk() } }}
            rows={2}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleAsk} loading={asking}>
            {t('btn.ask')}
          </Button>

          {/* Loading */}
          {asking && <div style={{ textAlign: 'center', padding: 16 }}><Spin tip={t('kb.thinking')} /></div>}

          {/* Answer */}
          {answer && (
            <Card bodyStyle={{ background: '#f0f7ff', padding: 16 }} style={{ marginTop: 4 }}>
              <Paragraph style={{ marginBottom: 8, whiteSpace: 'pre-wrap' }}>{answer}</Paragraph>
              {sources.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {t('kb.sources')}：
                  </Text>
                  <Space wrap style={{ marginTop: 4 }}>
                    {sources.map((s, i) => (
                      <Tag key={i} color={TYPE_COLOR[s.type] || 'default'}>
                        {s.id ? `${s.id} ` : ''}{s.title}
                      </Tag>
                    ))}
                  </Space>
                </div>
              )}
            </Card>
          )}

          {/* History */}
          {history.length > 0 && !answer && !asking && (
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>{t('kb.recent')}</Text>
              {history.map((h, i) => (
                <Card key={i} size="small" bodyStyle={{ padding: '8px 12px' }} style={{ marginTop: 8 }}>
                  <Text strong style={{ fontSize: 12 }}>Q: {h.q}</Text>
                  <Paragraph type="secondary" style={{ fontSize: 12 }} ellipsis={{ rows: 2 }}>{h.a}</Paragraph>
                </Card>
              ))}
            </div>
          )}
        </Space>
      </Card>

      {/* ── SECTION 3: Search results (below Q&A if any) ───────────────────── */}
      {searchResults.length > 0 && (
        <Card
          title={`${t('kb.searchResults')} (${searchResults.length})`}
          size="small"
          style={{ marginTop: 16 }}
        >
          <List
            dataSource={searchResults}
            renderItem={renderEntry}
            size="small"
            locale={{ emptyText: <Empty description={t('kb.noResults')} image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          />
        </Card>
      )}

      {/* ── Detail Drawer ─────────────────────────────────────────────────── */}
      <Drawer
        title={detailEntry ? `${typeLabel(detailEntry.type)} — ${detailEntry.id || detailEntry.cve || detailEntry.title}` : ''}
        open={!!detailEntry}
        onClose={() => setDetailEntry(null)}
        width={560}
        destroyOnClose
      >
        {detailEntry?.type === 'cve' && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="CVE">{detailEntry.cve}</Descriptions.Item>
            <Descriptions.Item label={t('kb.product')}>{detailEntry.product}</Descriptions.Item>
            <Descriptions.Item label={t('filter.level')}>
              <Space>
                <Tag color={SEVERITY_COLOR[detailEntry.severity || 'medium']}>{detailEntry.severity?.toUpperCase()}</Tag>
                <Text>CVSS {detailEntry.cvss}</Text>
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label={t('kb.exploitability')}>{detailEntry.exploitation || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('kb.description')}>{detailEntry.description}</Descriptions.Item>
            <Descriptions.Item label={t('kb.affected')}>{detailEntry.affected_versions}</Descriptions.Item>
            <Descriptions.Item label={t('kb.remediation')}>
              <Text type="warning" style={{ fontWeight: 500 }}>{detailEntry.remediation}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="MITRE">{detailEntry.mitre}</Descriptions.Item>
            <Descriptions.Item label={t('kb.detectionHints')}>
              <Space direction="vertical" size={4}>
                {(detailEntry.detection_hints || []).map((h: string, i: number) => (
                  <Tag key={i} color="default">{h}</Tag>
                ))}
              </Space>
            </Descriptions.Item>
          </Descriptions>
        )}
        {detailEntry?.type === 'mitre' && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="ID">{detailEntry.id}{detailEntry.sub ? `.${detailEntry.sub}` : ''}</Descriptions.Item>
            <Descriptions.Item label={t('table.name')}>{detailEntry.name}</Descriptions.Item>
            <Descriptions.Item label={t('kb.platforms')}>
              <Space wrap>
                {(detailEntry.platforms || []).map((p: string, i: number) => (
                  <Tag key={i}>{p}</Tag>
                ))}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label={t('kb.description')}>{detailEntry.description}</Descriptions.Item>
            <Descriptions.Item label={t('kb.detection')}>{detailEntry.detection}</Descriptions.Item>
            <Descriptions.Item label={t('kb.mitigation')}>{detailEntry.mitigation}</Descriptions.Item>
            <Descriptions.Item label={t('kb.indicators')}>
              <Space wrap>
                {(detailEntry.indicators || []).map((h: string, i: number) => (
                  <Tag key={i} color="orange">{h}</Tag>
                ))}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="Related CVEs">
              {(detailEntry.related_cves || []).length > 0
                ? <Space wrap>
                    {(detailEntry.related_cves || []).map((c: string, i: number) => (
                      <Tag key={i} color="red">{c}</Tag>
                    ))}
                  </Space>
                : <Text type="secondary">-</Text>
              }
            </Descriptions.Item>
          </Descriptions>
        )}
        {detailEntry?.type === 'practice' && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label={t('kb.category')}>
              <Tag color="blue">{detailEntry.category}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('table.name')}>{detailEntry.title}</Descriptions.Item>
            <Descriptions.Item label={t('kb.principle')}>{detailEntry.principle}</Descriptions.Item>
            <Descriptions.Item label={t('kb.standard')}>
              <Tag>{detailEntry.standard}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('kb.implementation')}>
              <Text code style={{ fontSize: 12 }}>{detailEntry.implementation}</Text>
            </Descriptions.Item>
            <Descriptions.Item label={t('kb.verification')}>
              <Text code style={{ fontSize: 12 }}>{detailEntry.risk_if_missing}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="MITRE Ref">
              {detailEntry.mitre_ref
                ? <Tag color="purple">{detailEntry.mitre_ref}</Tag>
                : <Text type="secondary">-</Text>
              }
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  )
}
