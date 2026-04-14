import { useState } from 'react'
import { Card, Input, Button, Space, Spin, Typography, Tag, List, Avatar, message } from 'antd'
import { SearchOutlined, RobotOutlined, AimOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { naturalLanguageSearch } from '../api/client'

const { Text, Paragraph } = Typography

interface SearchAccount {
  id: number
  username: string
  is_admin: boolean
  account_status: string | null
  last_login: string | null
}

interface SearchAsset {
  id: number
  asset_code: string
  ip: string
  hostname: string | null
  asset_category: string
  status: string
  account_count: number
  admin_count: number
  latest_accounts: SearchAccount[]
}

interface SearchResult {
  query: string
  filter_explanation: string[]
  llm_powered: boolean
  total_found: number
  assets: SearchAsset[]
}

const STATUS_COLOR: Record<string, string> = {
  online: 'green',
  offline: 'red',
  auth_failed: 'orange',
  untested: 'default',
}

const CATEGORY_ICON: Record<string, string> = {
  server: '🖥',
  database: '🗄',
  network: '🌐',
  iot: '📡',
}

function AssetCard({ asset, onClick }: { asset: SearchAsset; onClick: () => void }) {
  const { t } = useTranslation()
  const lang = document.documentElement.lang || 'zh-CN'

  return (
    <Card
      size="small"
      hoverable
      onClick={onClick}
      style={{ cursor: 'pointer' }}
      title={
        <Space>
          <span style={{ fontSize: 18 }}>{CATEGORY_ICON[asset.asset_category] || '📦'}</span>
          <Text strong>{asset.ip}</Text>
          {asset.hostname && <Text type="secondary">{asset.hostname}</Text>}
          <Tag color={STATUS_COLOR[asset.status] || 'default'}>
            {t(`status.${asset.status}`, asset.status)}
          </Tag>
        </Space>
      }
      extra={
        <Space>
          <Tag color="blue">{t('dashboard.totalAccounts')}: {asset.account_count}</Tag>
          {asset.admin_count > 0 && <Tag color="red">{t('status.privileged')}: {asset.admin_count}</Tag>}
        </Space>
      }
    >
      {asset.latest_accounts.length > 0 ? (
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>{t('ai.recentAccounts')}: </Text>
          {asset.latest_accounts.slice(0, 5).map((acc) => (
            <Tag
              key={acc.id}
              color={acc.is_admin ? 'red' : 'default'}
              style={{ marginBottom: 2 }}
            >
              {acc.username}
              {acc.is_admin && ' ★'}
              {acc.last_login && ` · ${new Date(acc.last_login).toLocaleDateString(lang)}`}
            </Tag>
          ))}
        </div>
      ) : (
        <Text type="secondary" style={{ fontSize: 12 }}>{t('asset.noAccounts')}</Text>
      )}
    </Card>
  )
}

export default function NaturalLanguageSearch() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const r = await naturalLanguageSearch(query.trim())
      setResult(r.data)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setError(err.response?.data?.detail || t('msg.error'))
      message.error(t('msg.error'))
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
  }

  const EXAMPLE_QUERIES = [
    t('ai.searchExample1'),
    t('ai.searchExample2'),
    t('ai.searchExample3'),
    t('ai.searchExample4'),
  ]

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
              <RobotOutlined style={{ marginRight: 6 }} />
              {t('ai.searchTip')}
            </Text>
            <Input.Search
              size="large"
              placeholder={t('ai.searchPlaceholder')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onSearch={handleSearch}
              onKeyDown={handleKeyDown}
              loading={loading}
              enterButton={
                <Button type="primary" icon={<SearchOutlined />}>
                  {t('btn.search')}
                </Button>
              }
            />
          </div>

          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>{t('ai.tryExamples')}: </Text>
            {EXAMPLE_QUERIES.map((q, i) => (
              <Tag
                key={i}
                style={{ cursor: 'pointer', marginBottom: 4 }}
                onClick={() => { setQuery(q); setResult(null); setError(null) }}
              >
                {q}
              </Tag>
            ))}
          </div>
        </Space>
      </Card>

      {loading && (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <Spin size="large" />
          <div style={{ marginTop: 12 }}>
            <Text type="secondary">{t('ai.searching')}</Text>
          </div>
        </div>
      )}

      {error && (
        <Card>
          <Text type="danger">{error}</Text>
        </Card>
      )}

      {result && !loading && (
        <div>
          <Card style={{ marginBottom: 16 }}>
            <Space style={{ width: '100%', justifyContent: 'space-between', flexWrap: 'wrap' }}>
              <div>
                <Text strong style={{ fontSize: 15 }}>
                  {t('ai.found')} {result.total_found} {t('nav.assets')}
                </Text>
                {result.filter_explanation.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    {result.filter_explanation.map((exp, i) => (
                      <Text key={i} type="secondary" style={{ fontSize: 13, display: 'block' }}>
                        • {exp}
                      </Text>
                    ))}
                  </div>
                )}
              </div>
              <Space>
                {result.llm_powered && (
                  <Tag icon={<RobotOutlined />} color="purple">{t('ai.llmPowered')}</Tag>
                )}
              </Space>
            </Space>
          </Card>

          <List
            grid={{ gutter: 12, xs: 1, sm: 1, md: 2, lg: 2, xl: 2 }}
            dataSource={result.assets}
            locale={{ emptyText: t('msg.noData') }}
            renderItem={(asset: SearchAsset) => (
              <List.Item>
                <AssetCard
                  asset={asset}
                  onClick={() => navigate(`/assets?highlight=${asset.id}`)}
                />
              </List.Item>
            )}
          />
        </div>
      )}
    </div>
  )
}
