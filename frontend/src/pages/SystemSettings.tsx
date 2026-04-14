/**
 * System Settings — extensible tabbed settings page.
 *
 * Architecture:
 *   Each settings category is a Tab with its own Card.
 *   To add a new category: add an entry to SETTINGS_TABS and a
 *   corresponding render function below.
 *
 * Future tabs (already planned):
 *   - System Info / About
 */
import { useState } from 'react'
import {
  Card, Tabs, Form, Select, Input, Button,
  Divider, message, Descriptions, Tag, Space,
  Typography, Modal,
} from 'antd'
import {
  SettingOutlined, KeyOutlined, SafetyOutlined,
  NotificationOutlined, InfoCircleOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { getLLMConfig, updateLLMConfig } from '../api/client'

const { Title } = Typography

// ─── Types ──────────────────────────────────────────────────────────────────────

interface LLMConfig {
  id: number
  provider: string
  api_key_set: boolean
  base_url: string | null
  model: string
  enabled: boolean
}

interface LicenseInfo {
  status: 'active' | 'trial' | 'expired' | 'unlicensed'
  seats_used: number
  seats_total: number
  expires_at: string | null
}

// ─── AI Model Config Tab ────────────────────────────────────────────────────────

function AIConfigTab() {
  const { t } = useTranslation()
  const [modalOpen, setModalOpen] = useState(false)
  const [cfg, setCfg] = useState<LLMConfig | null>(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [fetching, setFetching] = useState(false)

  const openModal = async () => {
    setFetching(true)
    try {
      const r = await getLLMConfig()
      setCfg(r.data as LLMConfig)
      form.setFieldsValue({
        base_url: r.data.base_url || '',
        model: r.data.model || 'MiniMax-M2.5',
        enabled: r.data.enabled,
        api_key: '',
      })
      setModalOpen(true)
    } catch {
      message.error(t('msg.error'))
    } finally {
      setFetching(false) // always clear — fixes stuck-loading bug
    }
  }

  const handleSave = async (values: Record<string, unknown>) => {
    setSaving(true)
    try {
      const payload: Record<string, unknown> = {
        base_url: values.base_url || 'https://api.minimaxi.com/v1',
        model: values.model,
        enabled: values.enabled,
      }
      if (values.api_key) {
        payload.api_key = values.api_key
      }
      await updateLLMConfig(payload as Parameters<typeof updateLLMConfig>[0])
      message.success(t('msg.success'))
      setModalOpen(false)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.error'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <Card
        title={
          <Space>
            <KeyOutlined />
            <span>{t('systemSettings.aiModelConfig')}</span>
          </Space>
        }
        extra={
          <Button type="primary" icon={<SettingOutlined />} onClick={openModal} loading={fetching}>
            {t('systemSettings.configure')}
          </Button>
        }
      >
        {cfg ? (
          <Descriptions size="small" column={2}>
            <Descriptions.Item label={t('llm.provider')}>MiniMax</Descriptions.Item>
            <Descriptions.Item label={t('llm.model')}>{cfg.model}</Descriptions.Item>
            <Descriptions.Item label={t('llm.baseUrl')}>{cfg.base_url || 'https://api.minimaxi.com/v1'}</Descriptions.Item>
            <Descriptions.Item label={t('llm.apiKey')}>
              {cfg.api_key_set
                ? <Tag color="green">{t('systemSettings.configured')}</Tag>
                : <Tag color="red">{t('systemSettings.notConfigured')}</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label={t('systemSettings.status')}>
              {cfg.enabled
                ? <Tag color="green">{t('systemSettings.enabled')}</Tag>
                : <Tag>{t('systemSettings.disabled')}</Tag>}
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <span style={{ color: 'rgba(0,0,0,0.25)' }}>{t('msg.loading')}</span>
        )}
      </Card>

      {/* AI Config Modal */}
      <Modal
        title={<Space><SettingOutlined />{t('llm.configTitle')}</Space>}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={480}
      >
        <Form form={form} layout="vertical" onFinish={handleSave} style={{ marginTop: 16 }}>
          <Form.Item
            name="api_key"
            label={t('llm.apiKey')}
            extra={
              cfg?.api_key_set
                ? <span style={{ color: 'rgba(0,0,0,0.45)' }}>{t('llm.configHintFilled')}</span>
                : <span style={{ color: '#ff4d4f' }}>{t('llm.apiKeyRequired')}</span>
            }
          >
            <Input.Password placeholder="eyJh..." />
          </Form.Item>

          <Form.Item
            name="base_url"
            label={t('llm.baseUrl')}
            extra={<span style={{ color: 'rgba(0,0,0,0.45)' }}>{t('llm.baseUrlHint')}</span>}
          >
            <Input placeholder={t('llm.baseUrlPlaceholder')} />
          </Form.Item>

          <Form.Item name="model" label={t('llm.model')} rules={[{ required: true }]}>
            <Select showSearch>
              <Select.Option value="MiniMax-M2.7">MiniMax-M2.7</Select.Option>
              <Select.Option value="MiniMax-M2.7-highspeed">MiniMax-M2.7-highspeed</Select.Option>
              <Select.Option value="MiniMax-M2.5">MiniMax-M2.5</Select.Option>
              <Select.Option value="MiniMax-M2.5-highspeed">MiniMax-M2.5-highspeed</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item name="enabled" label={t('llm.enableAI')} valuePropName="checked" initialValue={false}>
            <Input type="checkbox" />
          </Form.Item>

          <Divider style={{ margin: '12px 0' }} />

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button onClick={() => setModalOpen(false)}>{t('btn.cancel')}</Button>
            <Button type="primary" htmlType="submit" loading={saving}>{t('btn.save')}</Button>
          </div>
        </Form>
      </Modal>
    </>
  )
}

// ─── License Management Tab (placeholder for future) ───────────────────────────

function LicenseTab() {
  const { t } = useTranslation()
  const [info] = useState<LicenseInfo>({
    status: 'unlicensed',
    seats_used: 0,
    seats_total: 0,
    expires_at: null,
  })

  const statusMeta: Record<LicenseInfo['status'], { color: string; labelKey: string }> = {
    active: { color: 'green', labelKey: 'license.statusActive' },
    trial: { color: 'blue', labelKey: 'license.statusTrial' },
    expired: { color: 'red', labelKey: 'license.statusExpired' },
    unlicensed: { color: 'default', labelKey: 'license.statusUnlicensed' },
  }
  const meta = statusMeta[info.status]

  return (
    <Card
      title={
        <Space>
          <SafetyOutlined />
          <span>{t('systemSettings.tabs.license')}</span>
        </Space>
      }
      extra={
        <Button type="primary" icon={<SafetyOutlined />}>
          {t('license.activate')}
        </Button>
      }
    >
      <Descriptions size="small" column={2}>
        <Descriptions.Item label={t('license.status')}>
          <Tag color={meta.color}>{t(meta.labelKey)}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label={t('license.seats')}>
          {info.seats_used} / {info.seats_total}
        </Descriptions.Item>
        <Descriptions.Item label={t('license.expiresAt')}>
          {info.expires_at ?? '—'}
        </Descriptions.Item>
      </Descriptions>

      {info.status === 'unlicensed' && (
        <div style={{ marginTop: 16, padding: '12px 16px', background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6 }}>
          <Space>
            <InfoCircleOutlined style={{ color: '#52c41a' }} />
            <span style={{ color: '#389e0d', fontSize: 13 }}>{t('license.unlicensedHint')}</span>
          </Space>
        </div>
      )}
    </Card>
  )
}

// ─── Notification Settings Tab (placeholder for future) ─────────────────────────

function NotificationTab() {
  const { t } = useTranslation()
  return (
    <Card
      title={
        <Space>
          <NotificationOutlined />
          <span>{t('systemSettings.tabs.notification')}</span>
        </Space>
      }
    >
      <div style={{ color: 'rgba(0,0,0,0.25)', padding: '24px 0', textAlign: 'center' }}>
        {t('systemSettings.comingSoon')}
      </div>
    </Card>
  )
}

// ─── Tab registry ───────────────────────────────────────────────────────────────
// To add a new settings category:
//   1. Create a new function component (e.g. SecurityTab)
//   2. Add an entry below with key, i18n label key, icon, and component
//   3. Add the i18n keys to zh-CN.json and en-US.json

interface TabEntry {
  key: string
  labelKey: string
  icon: React.ReactNode
  Content: () => React.JSX.Element
}

const SETTINGS_TABS: TabEntry[] = [
  { key: 'ai',       labelKey: 'systemSettings.tabs.aiConfig',       icon: <KeyOutlined />,          Content: AIConfigTab },
  { key: 'license',  labelKey: 'systemSettings.tabs.license',        icon: <SafetyOutlined />,        Content: LicenseTab },
  { key: 'notify',   labelKey: 'systemSettings.tabs.notification',   icon: <NotificationOutlined />, Content: NotificationTab },
]

// ─── Root component ─────────────────────────────────────────────────────────────

export default function SystemSettings() {
  const { t } = useTranslation()

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <SettingOutlined style={{ marginRight: 8 }} />
          {t('systemSettings.title')}
        </Title>
      </div>

      <Tabs
        defaultActiveKey="ai"
        items={SETTINGS_TABS.map(tab => ({
          key: tab.key,
          label: (
            <Space>
              {tab.icon}
              {t(tab.labelKey)}
            </Space>
          ),
          children: <tab.Content />,
        }))}
      />
    </div>
  )
}
