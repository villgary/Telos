import { useState } from 'react'
import { Card, Tabs, Typography, Spin, Button, Space, Tooltip, message } from 'antd'
import { SafetyCertificateOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { generateAIReport } from '../api/client'
import NaturalLanguageSearch from './NaturalLanguageSearch'

const { Title, Text, Paragraph } = Typography

const _AI_REPORT_KEY = 'ai_report_threat_analysis'

function AIDashboardSummary() {
  const { t } = useTranslation()
  const [summary, setSummary] = useState<string | null>(
    () => localStorage.getItem(_AI_REPORT_KEY + '_' + i18n.language) ?? null
  )
  const [generating, setGenerating] = useState(false)

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const r = await generateAIReport({ report_type: 'threat_analysis', lang: i18n.language })
      if (r.data.success) {
        setSummary(r.data.report)
        localStorage.setItem(_AI_REPORT_KEY + '_' + i18n.language, r.data.report)
        message.success(t('msg.generateSuccess'))
      } else {
        message.error(r.data.error || t('msg.generateFailed'))
      }
    } catch {
      message.error(t('msg.generateFailed'))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <Card
      title={<Space><SafetyCertificateOutlined />{t('ai.dashboardSummary')}</Space>}
      extra={
        <Tooltip title={t('ai.dashboardSummaryTip')}>
          <Button icon={<SafetyCertificateOutlined />} onClick={handleGenerate} loading={generating}>
            {t('btn.generate')}
          </Button>
        </Tooltip>
      }
    >
      {generating ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
          <Text type="secondary" style={{ marginLeft: 12 }}>{t('ai.generating')}</Text>
        </div>
      ) : summary ? (
        <Paragraph
          style={{ fontSize: 14, lineHeight: 1.9, whiteSpace: 'pre-wrap', marginBottom: 0 }}
          ellipsis={{ rows: 30, expandable: true, symbol: t('btn.view') }}
        >
          {summary}
        </Paragraph>
      ) : (
        <div style={{ textAlign: 'center', padding: '32px 0' }}>
          <SafetyCertificateOutlined style={{ fontSize: 40, color: '#ccc', marginBottom: 16 }} />
          <div>
            <Text type="secondary">{t('ai.dashboardSummaryHint')}</Text>
          </div>
        </div>
      )}
    </Card>
  )
}

const _ACCOUNT_RISK_KEY = 'ai_report_account_risk'

function AccountRiskAnalysis() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [analysis, setAnalysis] = useState<string | null>(
    () => localStorage.getItem(_ACCOUNT_RISK_KEY + '_' + i18n.language) ?? null
  )
  const [generating, setGenerating] = useState(false)

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const r = await generateAIReport({ report_type: 'account_risk', lang: i18n.language })
      if (r.data.success) {
        setAnalysis(r.data.report)
        localStorage.setItem(_ACCOUNT_RISK_KEY + '_' + i18n.language, r.data.report)
        message.success(t('msg.generateSuccess'))
      } else {
        message.error(r.data.error || t('msg.generateFailed'))
      }
    } catch {
      message.error(t('msg.generateFailed'))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <Card
      title={<Space><SafetyCertificateOutlined />{t('ai.accountRiskAnalysis')}</Space>}
      extra={
        <Space>
          <Button type="link" size="small" onClick={() => navigate('/account-risk')} style={{ color: '#1677ff' }}>
            {t('btn.viewAll')} →
          </Button>
          <Tooltip title={t('ai.accountRiskAnalysisTip')}>
            <Button icon={<SafetyCertificateOutlined />} onClick={handleGenerate} loading={generating}>
              {t('btn.generate')}
            </Button>
          </Tooltip>
        </Space>
      }
    >
      {generating ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
          <Text type="secondary" style={{ marginLeft: 12 }}>{t('ai.generating')}</Text>
        </div>
      ) : analysis ? (
        <Paragraph
          style={{ fontSize: 14, lineHeight: 1.9, whiteSpace: 'pre-wrap', marginBottom: 0 }}
          ellipsis={{ rows: 30, expandable: true, symbol: t('btn.view') }}
        >
          {analysis}
        </Paragraph>
      ) : (
        <div style={{ textAlign: 'center', padding: '32px 0' }}>
          <SafetyCertificateOutlined style={{ fontSize: 40, color: '#ccc', marginBottom: 16 }} />
          <div>
            <Text type="secondary">{t('ai.accountRiskAnalysisHint')}</Text>
          </div>
        </div>
      )}
    </Card>
  )
}

export default function AISecurityAnalysis() {
  const { t } = useTranslation()

  const tabs = [
    { key: 'summary', label: t('ai.tabSummary'), children: <AIDashboardSummary /> },
    { key: 'search', label: t('ai.tabSearch'), children: <NaturalLanguageSearch /> },
    { key: 'accountRisk', label: t('ai.tabAccountRisk'), children: <AccountRiskAnalysis /> },
  ]

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>{t('nav.aiAnalysis')}</Title>
      <Tabs items={tabs} defaultActiveKey="summary" />
    </div>
  )
}
// TEST_MARKER_1774938120
