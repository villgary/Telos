import { useEffect, useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Card, Table, Tag, Select, Typography, Space, Button,
  Progress, Tooltip, Statistic, Row, Col, Empty, Alert,
  Badge, List, Tabs,
} from 'antd'
import {
  DownloadOutlined, WarningOutlined, CheckCircleOutlined,
  AimOutlined, BarChartOutlined, UnorderedListOutlined,
  SafetyOutlined, ExclamationCircleOutlined, InfoCircleOutlined,
} from '@ant-design/icons'
import api from '../api/client'

const { Title, Text, Paragraph } = Typography

// ATT&CK tactic metadata
const TACTIC_META: Record<string, { label: string; labelEn: string; color: string }> = {
  'TA0001': { label: '初始访问', labelEn: 'Initial Access', color: '#d4380d' },
  'TA0002': { label: '执行', labelEn: 'Execution', color: '#d46b08' },
  'TA0003': { label: '持久化', labelEn: 'Persistence', color: '#d48806' },
  'TA0004': { label: '权限提升', labelEn: 'Privilege Escalation', color: '#d4b106' },
  'TA0005': { label: '防御规避', labelEn: 'Defense Evasion', color: '#7cb305' },
  'TA0006': { label: '凭据访问', labelEn: 'Credential Access', color: '#389e0d' },
  'TA0007': { label: '发现', labelEn: 'Discovery', color: '#08979c' },
  'TA0008': { label: '横向移动', labelEn: 'Lateral Movement', color: '#096dd9' },
  'TA0009': { label: '收集', labelEn: 'Collection', color: '#1d39c4' },
  'TA0010': { label: '命令与控制', labelEn: 'Command and Control', color: '#531dab' },
  'TA0011': { label: '数据窃取', labelEn: 'Exfiltration', color: '#8b2332' },
  'TA0040': { label: '影响', labelEn: 'Impact', color: '#d4380d' },
}

// ATT&CK technique names
const TECHNIQUE_NAMES: Record<string, { name: string; nameEn: string }> = {
  'T1078':         { name: '有效账号',           nameEn: 'Valid Accounts' },
  'T1078.003':     { name: '本地账号',            nameEn: 'Local Accounts' },
  'T1078.004':     { name: '域账号',              nameEn: 'Domain Accounts' },
  'T1021':         { name: '远程服务',            nameEn: 'Remote Services' },
  'T1021.004':     { name: 'SSH远程访问',          nameEn: 'SSH Remote Services' },
  'T1548':         { name: '滥用sudo',             nameEn: 'Sudo Caching' },
  'T1548.003':     { name: 'sudo和su',            nameEn: 'Sudo and SudoCaching' },
  'T1098':         { name: '账号操作',             nameEn: 'Account Manipulation' },
  'T1068':         { name: '内核漏洞利用',         nameEn: 'Exploitation for Privilege Escalation' },
  'T1562':         { name: '防御规避',             nameEn: 'Impair Defenses' },
  'T1556':         { name: '认证攻击',             nameEn: 'Modify Authentication Process' },
  'T1059':         { name: '命令和脚本解释器',     nameEn: 'Command and Scripting Interpreter' },
  'T1059.004':     { name: 'Unix Shell',            nameEn: 'Unix Shell' },
  'T1059.003':     { name: 'Windows命令外壳',      nameEn: 'Windows Command Shell' },
  'T1053':         { name: '计划任务/作业',         nameEn: 'Scheduled Task/Job' },
  'T1053.005':     { name: '计划任务',              nameEn: 'Scheduled Task' },
  'T1047':         { name: 'Windows管理工具',      nameEn: 'Windows Management Instrumentation' },
  'T1036':         { name: '伪装',                  nameEn: 'Masquerading' },
  'T1036.005':     { name: '匹配合法名称',          nameEn: 'Match Legitimate Name' },
  'T1005':         { name: '本地系统数据',           nameEn: 'Data from Local System' },
  'T1087':         { name: '账号发现',               nameEn: 'Account Discovery' },
  'T1087.001':     { name: '本地账号',               nameEn: 'Local Account' },
  'T1087.002':     { name: '域账号',                nameEn: 'Domain Account' },
  'T1070':         { name: '持久化痕迹清除',         nameEn: 'Indicator Removal' },
  'T1070.004':     { name: '文件删除',               nameEn: 'File Deletion' },
  'T1552':         { name: '凭据未经授权搜索',        nameEn: 'Unsecured Credentials' },
  'T1552.001':     { name: '凭据文件',               nameEn: 'Credentials in Files' },
  'T1552.004':     { name: '私钥',                   nameEn: 'Private Keys' },
  'T1558':         { name: 'Kerberos攻击',            nameEn: 'Steal Application Access Token' },
  'T1558.003':     { name: 'Kerberoasting',           nameEn: 'Kerberoasting' },
  'T1071':         { name: '应用层协议',              nameEn: 'Application Layer Protocol' },
  'T1570':         { name: '横向工具转移',            nameEn: 'Lateral Tool Transfer' },
  'T1048':         { name: '窃取替代协议',            nameEn: 'Exfiltration Over Alternative Protocol' },
  'T1003.004':     { name: 'SSH密钥凭据访问',          nameEn: 'SSH Key Credential Access' },
  'T1550.003':     { name: 'Unix远程Shell',           nameEn: 'Unix Remote Shell' },
}

function getTacticLabel(id: string, lang: string): string {
  const meta = TACTIC_META[id]
  if (!meta) return id
  return lang === 'zh' ? meta.label : meta.labelEn
}

function getTechniqueName(id: string, lang: string): string {
  const tech = TECHNIQUE_NAMES[id]
  if (!tech) return id
  return lang === 'zh' ? tech.name : tech.nameEn
}

function scoreColor(score: number): string {
  if (score >= 80) return '#cf1322'
  if (score >= 60) return '#fa8c16'
  if (score >= 40) return '#faad14'
  return '#52c41a'
}

function confidenceColor(conf: number): string {
  if (conf >= 80) return '#cf1322'
  if (conf >= 60) return '#fa8c16'
  return '#389e0d'
}

function getSignalLabel(sigType: string, tFunc: (k: string) => string): string {
  const key = `attck.sig.${sigType}`
  const translated = tFunc(key)
  return translated !== key ? translated : sigType.replace(/_/g, ' ')
}

function severityConfig(sev: string): { color: string; icon: React.ReactNode; labelKey: string } {
  switch (sev) {
    case 'critical':
      return { color: '#cf1322', icon: <ExclamationCircleOutlined />, labelKey: 'attck.sevCritical' }
    case 'high':
      return { color: '#fa8c16', icon: <WarningOutlined />, labelKey: 'attck.sevHigh' }
    case 'medium':
      return { color: '#faad14', icon: <ExclamationCircleOutlined />, labelKey: 'attck.sevMedium' }
    case 'low':
      return { color: '#52c41a', icon: <InfoCircleOutlined />, labelKey: 'attck.sevLow' }
    default:
      return { color: '#8c8c8c', icon: <InfoCircleOutlined />, labelKey: 'attck.sevInfo' }
  }
}

export default function ATTCKCoverage() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language === 'zh' ? 'zh' : 'en'

  const [allSignals, setAllSignals] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingPage, setLoadingPage] = useState(true)
  const [selectedAnalysis, setSelectedAnalysis] = useState<any>(null)
  const [techniqueRows, setTechniqueRows] = useState<any[]>([])
  const [unmappedSignals, setUnmappedSignals] = useState<any[]>([])
  const [layerJson, setLayerJson] = useState<any>(null)
  const [loadingLayer, setLoadingLayer] = useState(false)

  // Auto-load latest global analysis on mount
  useEffect(() => {
    setLoadingPage(true)
    api.get('/identity-threat/analyses', { params: { limit: 5, scope: 'global' } })
       .then(r => {
         const raw = Array.isArray(r.data) ? r.data : (r.data.analyses || r.data.items || [])
         // Pick latest global analysis
         const globalOnes = raw.filter((a: any) => a.scope === 'global')
         if (globalOnes.length > 0) {
           setSelectedAnalysis(globalOnes[0])
         }
       })
       .catch(() => {})
       .finally(() => setLoadingPage(false))
  }, [])

  // Load signals when analysis is selected
  useEffect(() => {
    if (!selectedAnalysis) return
    setLoading(true)

    const layers = ['semiotic', 'causal', 'ontological', 'cognitive', 'anthropological']
    const sigs: any[] = []

    Promise.all(
      layers.map(l =>
        api.get(`/identity-threat/analyses/${selectedAnalysis.id}/signals/${l}`, {
          params: { lang, signals_limit: 0 },
        }).then(r => {
          if (l === 'semiotic') {
            const nodes = r.data.signals || []
            for (const node of nodes) {
              for (const sig of node.signals || []) {
                sigs.push({ ...sig, node_id: node.node_id, username: node.username, asset_code: node.asset_code })
              }
            }
          } else {
            for (const sig of r.data.signals || []) {
              sigs.push(sig)
            }
          }
        }).catch(() => {})
      )
    ).finally(() => {
      setLoading(false)
      setAllSignals(sigs)

      // Build technique rows
      const byTech: Record<string, any> = {}
      const unmapped: any[] = []
      for (const sig of sigs) {
        const mitreId = sig.mitre_id || sig.mitre_primary_id
        if (!mitreId) {
          unmapped.push(sig)
          continue
        }
        if (!byTech[mitreId]) {
          byTech[mitreId] = {
            key: mitreId,
            technique_id: mitreId,
            technique_name: getTechniqueName(mitreId, lang),
            tactic_id: sig.mitre_tactic || '',
            tactic_name: getTacticLabel(sig.mitre_tactic || '', lang),
            signals: [],
            confidence: 0,
            severity: 'low',
            evidence: [] as string[],
          }
        }
        byTech[mitreId].signals.push(sig)
        if (sig.mitre_confidence && sig.mitre_confidence > byTech[mitreId].confidence) {
          byTech[mitreId].confidence = sig.mitre_confidence
        }
        if (sig.severity === 'critical' || sig.severity === 'high') {
          byTech[mitreId].severity = sig.severity
        }
        const ev = sig.mitre_rationale || sig.detail || sig.description || ''
        if (ev && !byTech[mitreId].evidence.includes(ev)) {
          byTech[mitreId].evidence.push(ev.slice(0, 120))
        }
      }

      const rows = Object.values(byTech) as any[]
      rows.sort((a, b) => b.signals.length - a.signals.length)
      setTechniqueRows(rows)
      setUnmappedSignals(unmapped)

      setLoadingLayer(true)
      api.get(`/identity-threat/mitre-layer/${selectedAnalysis.id}`)
         .then(r => setLayerJson(r.data))
         .catch(() => setLayerJson(null))
         .finally(() => setLoadingLayer(false))
    })
  }, [selectedAnalysis, lang])

  // Risk summary items grouped by severity
  const riskItems = useMemo(() => {
    const byType: Record<string, any> = {}
    for (const sig of allSignals) {
      const key = sig.type || sig.signal_type
      if (!key) continue
      if (!byType[key]) {
        byType[key] = {
          key,
          signal_type: key,
          signal_label: getSignalLabel(key, t),
          mitre_id: sig.mitre_id || '',
          mitre_label: t('attck.tech.' + sig.mitre_id) !== 'attck.tech.' + sig.mitre_id
            ? t('attck.tech.' + sig.mitre_id)
            : getTechniqueName(sig.mitre_id || '', lang),
          tactic_label: t('attck.tactic.' + sig.mitre_tactic) !== 'attck.tactic.' + sig.mitre_tactic
            ? t('attck.tactic.' + sig.mitre_tactic)
            : getTacticLabel(sig.mitre_tactic || '', lang),
          severity: sig.severity || 'low',
          confidence: sig.mitre_confidence || 0,
          remediation: sig.mitre_remediation || sig.detail || '',
          accounts: [],
          count: 0,
        }
      }
      byType[key].count++
      const acct = [sig.username, sig.asset_code].filter(Boolean).join('@')
      if (acct && !byType[key].accounts.includes(acct)) {
        byType[key].accounts.push(acct)
      }
    }
    return Object.values(byType) as any[]
  }, [allSignals, lang, t])

  const critItems = riskItems.filter(i => i.severity === 'critical' || i.severity === 'high')
  const otherItems = riskItems.filter(i => i.severity !== 'critical' && i.severity !== 'high')

  // Technique table columns
  const techColumns = [
    {
      title: t('attck.technique') || 'Technique',
      key: 'technique',
      width: 280,
      render: (_: any, row: any) => (
        <Space direction="vertical" size={0}>
          <Tag color="blue" style={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {row.technique_id}
          </Tag>
          <Text strong style={{ fontSize: 13 }}>{row.technique_name}</Text>
        </Space>
      ),
    },
    {
      title: t('attck.tactic') || 'Tactic',
      key: 'tactic',
      width: 130,
      render: (_: any, row: any) => {
        const meta = TACTIC_META[row.tactic_id]
        return (
          <Tag color={meta?.color || 'default'}>
            {row.tactic_name || row.tactic_id}
          </Tag>
        )
      },
    },
    {
      title: t('attck.signalCount') || 'Signals',
      key: 'count',
      width: 90,
      sorter: (a: any, b: any) => a.signals.length - b.signals.length,
      render: (_: any, row: any) => (
        <Tag color="orange">{row.signals.length}</Tag>
      ),
    },
    {
      title: t('attck.confidence') || 'Confidence',
      key: 'confidence',
      width: 120,
      sorter: (a: any, b: any) => a.confidence - b.confidence,
      render: (_: any, row: any) => (
        <Space>
          <Progress
            percent={row.confidence || 0}
            size="small"
            strokeColor={confidenceColor(row.confidence || 0)}
            style={{ width: 70 }}
            format={p => `${p}%`}
          />
        </Space>
      ),
    },
    {
      title: t('attck.severity') || 'Severity',
      key: 'severity',
      width: 100,
      render: (_: any, row: any) => {
        const colors: Record<string, string> = { critical: 'red', high: 'orange', medium: 'gold', low: 'green', info: 'default' }
        return <Tag color={colors[row.severity] || 'default'}>{row.severity}</Tag>
      },
    },
    {
      title: t('attck.evidence') || 'Evidence',
      key: 'evidence',
      render: (_: any, row: any) => (
        <Space direction="vertical" size={2}>
          {row.evidence.slice(0, 2).map((ev: string, i: number) => (
            <Text key={i} type="secondary" style={{ fontSize: 11 }}>
              {ev}{ev.length >= 120 ? '…' : ''}
            </Text>
          ))}
          {row.evidence.length > 2 && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              +{t('attck.moreEvidence', { n: row.evidence.length - 2 })}
            </Text>
          )}
        </Space>
      ),
    },
  ]

  const unmappedColumns = [
    {
      title: t('attck.signalType'),
      dataIndex: 'type',
      key: 'type',
      width: 220,
      render: (type: string) => <Tag style={{ fontFamily: 'monospace' }}>{type}</Tag>,
    },
    {
      title: t('attck.severity'),
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (sev: string) => {
        const colors: Record<string, string> = { critical: 'red', high: 'orange', medium: 'gold', low: 'green', info: 'default' }
        return <Tag color={colors[sev] || 'default'}>{sev}</Tag>
      },
    },
    {
      title: t('attck.detail'),
      dataIndex: 'detail',
      key: 'detail',
      render: (detail: string) => <Text style={{ fontSize: 12 }}>{detail || '—'}</Text>,
    },
  ]

  const tacticCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const row of techniqueRows) {
      const tid = row.tactic_id || 'unknown'
      counts[tid] = (counts[tid] || 0) + row.signals.length
    }
    return counts
  }, [techniqueRows])

  const downloadLayer = () => {
    if (!layerJson) return
    const blob = new Blob([JSON.stringify(layerJson, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `attck-layer-analysis-${selectedAnalysis?.id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const renderRiskSummary = () => (
    <div>
      {/* Page-level header */}
      {selectedAnalysis && (
        <Alert
          type="info"
          icon={<SafetyOutlined />}
          style={{ marginBottom: 16 }}
          message={
            <Space>
              <Text>{t('attck.riskSummaryHeader')}：</Text>
              <Tag color="blue">#{selectedAnalysis.id}</Tag>
              <Text>{t('attck.totalScore')} <strong style={{ color: scoreColor(selectedAnalysis.overall_score) }}>{selectedAnalysis.overall_score}</strong>（{t('attck.level.' + selectedAnalysis.overall_level)}）</Text>
              <Text type="secondary">{selectedAnalysis.created_at?.slice(0, 16)}</Text>
            </Space>
          }
        />
      )}

      {/* Critical + High */}
      {critItems.length > 0 && (
        <Card size="small" title={
          <Space>
            <ExclamationCircleOutlined style={{ color: '#fa8c16' }} />
            <Text strong style={{ color: '#fa8c16' }}>{t('attck.highRisk', { n: critItems.length })}</Text>
          </Space>
        } style={{ marginBottom: 16, borderColor: '#fa8c16' }}>
          {critItems.map(item => {
            const cfg = severityConfig(item.severity)
            return (
              <Card
                key={item.key}
                size="small"
                style={{ marginBottom: 10, borderLeft: `3px solid ${cfg.color}` }}
                bodyStyle={{ padding: '10px 14px' }}
              >
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Space>
                      <Tag color={cfg.color} icon={cfg.icon}>{t(cfg.labelKey)}</Tag>
                      <Text strong>{item.signal_label}</Text>
                      {item.mitre_id && (
                        <Tag color="blue" style={{ fontFamily: 'monospace' }}>{item.mitre_id}</Tag>
                      )}
                      {item.tactic_label && <Text type="secondary">[{item.tactic_label}]</Text>}
                    </Space>
                    <Tag>{t('attck.signalCountN', { n: item.count })}</Tag>
                  </Space>

                  {item.accounts.length > 0 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {t('attck.affectedAccounts')}：{item.accounts.slice(0, 5).join('、')}
                      {item.accounts.length > 5 && ` ${t('attck.andMore', { n: item.accounts.length })}`}
                    </Text>
                  )}

                  {item.remediation && (
                    <Paragraph
                      type="secondary"
                      style={{ fontSize: 12, margin: 0 }}
                      ellipsis={{ rows: 2, expandable: true, symbol: t('attck.expand') }}
                    >
                      {t('attck.remediation')}：{item.remediation}
                    </Paragraph>
                  )}
                </Space>
              </Card>
            )
          })}
        </Card>
      )}

      {/* Medium + Low */}
      {otherItems.length > 0 && (
        <Card size="small" title={
          <Space>
            <InfoCircleOutlined style={{ color: '#52c41a' }} />
            <Text strong style={{ color: '#52c41a' }}>{t('attck.mediumLowRisk', { n: otherItems.length })}</Text>
          </Space>
        } style={{ marginBottom: 16, borderColor: '#52c41a' }}>
          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            {otherItems.map(item => {
              const cfg = severityConfig(item.severity)
              return (
                <Space key={item.key} style={{ width: '100%', justifyContent: 'space-between' }}>
                  <Space>
                    <Tag color={cfg.color}>{t(cfg.labelKey)}</Tag>
                    <Text>{item.signal_label}</Text>
                    {item.mitre_id && <Tag color="blue" style={{ fontFamily: 'monospace', fontSize: 11 }}>{item.mitre_id}</Tag>}
                    {item.accounts.length > 0 && (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {item.accounts.slice(0, 3).join('、')}{item.accounts.length > 3 && `…`}
                      </Text>
                    )}
                  </Space>
                  <Space>
                    {item.remediation && (
                      <Tooltip title={item.remediation}>
                        <Tag color="green" style={{ cursor: 'pointer' }}>{t('attck.remediation')}</Tag>
                      </Tooltip>
                    )}
                    <Tag>x{item.count}</Tag>
                  </Space>
                </Space>
              )
            })}
          </Space>
        </Card>
      )}

      {riskItems.length === 0 && !loading && (
        <Empty description={t('attck.noRisks')} />
      )}

      {loading && <Empty description={t('attck.loading')} />}
    </div>
  )

  const renderTechniqueDetail = () => (
    <div>
      {/* Summary stats */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title={t('attck.techniquesDetected') || 'Techniques Detected'}
              value={techniqueRows.length}
              prefix={<CheckCircleOutlined style={{ color: '#389e0d' }} />}
              valueStyle={{ color: '#389e0d' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title={t('attck.tacticsCovered') || 'Tactics Covered'}
              value={Object.keys(tacticCounts).filter(k => k !== 'unknown').length}
              prefix={<BarChartOutlined style={{ color: '#096dd9' }} />}
              valueStyle={{ color: '#096dd9' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title={t('attck.totalSignals') || 'Total Signals'}
              value={techniqueRows.reduce((s, r) => s + r.signals.length, 0)}
              prefix={<UnorderedListOutlined style={{ color: '#d46b08' }} />}
              valueStyle={{ color: '#d46b08' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title={t('attck.unmappedSignals') || 'Unmapped Signals'}
              value={unmappedSignals.length}
              prefix={<WarningOutlined style={{ color: unmappedSignals.length > 0 ? '#cf1322' : '#389e0d' }} />}
              valueStyle={{ color: unmappedSignals.length > 0 ? '#cf1322' : '#389e0d' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Tactic overview bar */}
      {Object.keys(tacticCounts).filter(k => k !== 'unknown').length > 0 && (
        <Card size="small" title={t('attck.tacticCoverage') || 'Tactic Coverage'} style={{ marginBottom: 16 }}>
          <Space wrap>
            {Object.entries(tacticCounts)
              .filter(([k]) => k !== 'unknown')
              .sort((a, b) => b[1] - a[1])
              .map(([tid, count]) => {
                const meta = TACTIC_META[tid]
                return (
                  <Tooltip key={tid} title={`${getTacticLabel(tid, lang)}: ${count} signals`}>
                    <Tag color={meta?.color || 'default'} style={{ padding: '4px 10px', fontSize: 12 }}>
                      {tid} {getTacticLabel(tid, lang)} ({count})
                    </Tag>
                  </Tooltip>
                )
              })}
          </Space>
        </Card>
      )}

      {/* Technique table */}
      <Card
        size="small"
        title={`${t('attck.techniqueTable') || 'Detected Techniques'} (${techniqueRows.length})`}
        loading={loading}
        style={{ marginBottom: 16 }}
      >
        <Table
          dataSource={techniqueRows}
          columns={techColumns}
          pagination={{ pageSize: 15, size: 'small' }}
          size="small"
          rowKey="key"
          scroll={{ x: 900 }}
        />
      </Card>

      {/* Unmapped signals */}
      {unmappedSignals.length > 0 && (
        <Card
          size="small"
          type="inner"
          title={
            <Space>
              <WarningOutlined style={{ color: '#cf1322' }} />
              <span>{t('attck.unmappedSignals') || 'Unmapped Signals'}</span>
              <Tag color="red">{unmappedSignals.length}</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('attck.unmappedHint') || 'Add MITRE ATT&CK mapping in mitre_mapping.py for these signal types'}
              </Text>
            </Space>
          }
        >
          <Table
            dataSource={unmappedSignals.slice(0, 50).map((s, i) => ({ ...s, key: i }))}
            columns={unmappedColumns}
            pagination={{ pageSize: 10, size: 'small' }}
            size="small"
          />
        </Card>
      )}

      {techniqueRows.length === 0 && !loading && (
        <Empty description={t('attck.noCoverage') || 'No MITRE ATT&CK coverage data yet — run an analysis first'} />
      )}
    </div>
  )

  if (loadingPage) {
    return <div style={{ padding: 24 }}><Empty description={t('attck.loading')} /></div>
  }

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Title level={4} style={{ margin: 0 }}>
            <AimOutlined /> {t('attck.title') || 'ATT&CK Coverage Dashboard'}
          </Title>
          <Button
            icon={<DownloadOutlined />}
            onClick={downloadLayer}
            loading={loadingLayer}
            disabled={!layerJson}
          >
            {t('attck.downloadLayer') || 'Download ATT&CK Layer'}
          </Button>
        </Space>

        {!selectedAnalysis && !loadingPage && (
          <Alert
            type="warning"
            message={t('attck.noAnalysis')}
            description={t('attck.runAnalysisFirst')}
          />
        )}

        {selectedAnalysis && (
          <Tabs
            defaultActiveKey="summary"
            items={[
              {
                key: 'summary',
                label: (
                  <Space>
                    <SafetyOutlined />
                    {t('attck.riskSummary')}
                    {critItems.length > 0 && <Badge count={critItems.length} style={{ backgroundColor: '#fa8c16' }} /> }
                  </Space>
                ),
                children: renderRiskSummary(),
              },
              {
                key: 'techniques',
                label: (
                  <Space>
                    <BarChartOutlined />
                    {t('attck.techniqueDetail')}
                    <Tag>{techniqueRows.length}</Tag>
                  </Space>
                ),
                children: renderTechniqueDetail(),
              },
            ]}
          />
        )}
      </Space>
    </div>
  )
}
