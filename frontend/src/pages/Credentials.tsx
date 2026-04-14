import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Table, Button, Typography, Drawer, Form, Input, Select,
  message, Popconfirm, Tag, Space,
} from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons'
import api from '../api/client'

const { Title } = Typography
const { Option } = Select

interface Credential {
  id: number
  name: string
  auth_type: string
  username: string
  has_password: boolean
  has_private_key: boolean
  created_at: string
}

export default function Credentials() {
  const { t } = useTranslation()
  const [credentials, setCredentials] = useState<Credential[]>([])
  const [loading, setLoading] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editCred, setEditCred] = useState<Credential | null>(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const fetchCredentials = () => {
    setLoading(true)
    api.get('/credentials')
      .then(r => setCredentials(r.data))
      .catch(() => message.error(t('msg.loadFailedAdmin')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchCredentials() }, [])

  const openAdd = () => {
    setEditCred(null)
    form.resetFields()
    setDrawerOpen(true)
  }

  const openEdit = (cred: Credential) => {
    setEditCred(cred)
    form.setFieldsValue({
      name: cred.name,
      auth_type: cred.auth_type,
      username: cred.username,
      // Password/key fields left blank — user must fill to change
    })
    setDrawerOpen(true)
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      if (editCred) {
        // PUT — only send fields that have values (don't require password/key if not changing)
        const payload: Record<string, string> = { name: values.name, username: values.username }
        if (values.password) payload.password = values.password
        if (values.private_key) payload.private_key = values.private_key
        if (values.passphrase !== undefined) payload.passphrase = values.passphrase ?? ''
        await api.put(`/credentials/${editCred.id}`, payload)
        message.success(t('credential.updated'))
      } else {
        await api.post('/credentials', values)
        message.success(t('credential.created'))
      }
      setDrawerOpen(false)
      form.resetFields()
      fetchCredentials()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/credentials/${id}`)
      message.success(t('msg.deleted'))
      fetchCredentials()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.deleteFailed'))
    }
  }

  const columns = [
    { title: t('credential.name'), dataIndex: 'name', key: 'name', width: 200 },
    {
      title: t('credential.authType'),
      dataIndex: 'auth_type',
      key: 'auth_type',
      width: 130,
      render: (v: string) => (
        <Tag color={v === 'password' ? 'blue' : 'purple'}>
          {v === 'password' ? t('credential.userPass') : t('credential.sshKey')}
        </Tag>
      ),
    },
    { title: t('credential.username'), dataIndex: 'username', key: 'username', width: 150 },
    {
      title: t('credential.secretStatus'),
      key: 'has_secret',
      render: (_: unknown, r: Credential) => (
        <>
          {r.has_password && <Tag color="green">{t('credential.passwordEncrypted')}</Tag>}
          {r.has_private_key && <Tag color="green">{t('credential.keyEncrypted')}</Tag>}
          {!r.has_password && !r.has_private_key && <Tag color="default">—</Tag>}
        </>
      ),
    },
    {
      title: t('credential.createdAt'),
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: t('table.actions'),
      key: 'actions',
      width: 150,
      render: (_: unknown, r: Credential) => (
        <Space size={4}>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>
            {t('btn.edit')}
          </Button>
          <Popconfirm
            title={t('credential.confirmDelete')}
            onConfirm={() => handleDelete(r.id)}
            okText={t('btn.delete')}
            okButtonProps={{ danger: true }}
            cancelText={t('btn.cancel')}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              {t('btn.delete')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t('credential.title')}</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          {t('btn.addCredential')}
        </Button>
      </div>

      <Table
        dataSource={credentials}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      <Drawer
        title={editCred ? t('credential.editTitle') : t('credential.addTitle')}
        onClose={() => { setDrawerOpen(false); form.resetFields() }}
        open={drawerOpen}
        width={440}
        footer={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            {editCred && (
              <Popconfirm
                title={t('credential.confirmDelete')}
                onConfirm={() => {
                  setDrawerOpen(false)
                  handleDelete(editCred.id)
                }}
                okText={t('btn.delete')}
                okButtonProps={{ danger: true }}
                cancelText={t('btn.cancel')}
              >
                <Button danger size="small">{t('btn.deleteCredential')}</Button>
              </Popconfirm>
            )}
            <div style={{ marginLeft: 'auto' }}>
              <Button onClick={() => { setDrawerOpen(false); form.resetFields() }} style={{ marginRight: 8 }}>{t('btn.cancel')}</Button>
              <Button type="primary" onClick={handleSave} loading={saving}>
                {t('btn.save')}
              </Button>
            </div>
          </div>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label={t('credential.credName')} rules={[{ required: true, message: t('credential.enterName') }]}>
            <Input placeholder={t('credential.namePlaceholder')} />
          </Form.Item>
          <Form.Item name="auth_type" label={t('credential.authMethod')} rules={[{ required: true }]}>
            <Select
              onChange={() => form.resetFields(['password', 'private_key', 'passphrase'])}
              placeholder={t('credential.selectAuthMethod')}
            >
              <Option value="password">{t('credential.userPass')}</Option>
              <Option value="ssh_key">{t('credential.sshKey')}</Option>
            </Select>
          </Form.Item>
          <Form.Item name="username" label={t('credential.loginUsername')} rules={[{ required: true, message: t('credential.enterUsername') }]}>
            <Input placeholder="root" />
          </Form.Item>

          {/* Password hint when editing */}
          {editCred && editCred.has_password && (
            <div style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>
              {t('credential.passwordHint')}
            </div>
          )}

          <Form.Item noStyle shouldUpdate={(prev, curr) => prev.auth_type !== curr.auth_type}>
            {() => {
              const authType = form.getFieldValue('auth_type')
              if (!authType) return null

              if (authType === 'password') {
                return (
                  <Form.Item
                    name="password"
                    label={editCred?.has_password ? t('credential.newPassword') : t('credential.password')}
                    rules={editCred ? [] : [{ required: true, message: t('credential.enterPassword') }]}
                  >
                    <Input.Password placeholder={editCred?.has_password ? t('credential.newPasswordPlaceholder') : t('credential.passwordPlaceholder')} />
                  </Form.Item>
                )
              }

              // SSH key
              return (
                <>
                  <div style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>
                    {editCred?.has_private_key ? t('credential.keyHintKeep') : t('credential.keyHint')}
                  </div>
                  <Form.Item
                    name="private_key"
                    label={t('credential.sshPrivateKey')}
                    rules={editCred ? [] : [{ required: true, message: t('credential.pasteKey') }]}
                  >
                    <Input.TextArea
                      rows={6}
                      placeholder="-----BEGIN RSA PRIVATE KEY-----"
                    />
                  </Form.Item>
                  <Form.Item name="passphrase" label={t('credential.passphraseOptional')}>
                    <Input.Password placeholder={t('credential.passphrasePlaceholder')} />
                  </Form.Item>
                </>
              )
            }}
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  )
}
