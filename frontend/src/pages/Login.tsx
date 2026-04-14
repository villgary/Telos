import { Form, Input, Button, Card, message, Typography } from 'antd'
import { LockOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import api from '../api/client'
import LanguageSwitcher from '../LanguageSwitcher'

const { Title } = Typography

export default function Login() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [form] = Form.useForm()

  const handleLogin = async (values: { username: string; password: string }) => {
    try {
      const params = new URLSearchParams({
        username: values.username,
        password: values.password,
      })
      const res = await api.post('/auth/login', params.toString(), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      localStorage.setItem('token', res.data.access_token)
      message.success(t('msg.success'))
      navigate('/', { replace: true })
    } catch {
      message.error(t('login.loginError'))
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #001529 0%, #1677ff 100%)',
    }}>
      <Card style={{ width: 400, boxShadow: '0 8px 32px rgba(0,0,0,0.2)', position: 'relative' }}>
        <div style={{ position: 'absolute', top: 12, right: 12 }}>
          <LanguageSwitcher />
        </div>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <img src="/logo.svg" alt="Telos" style={{ width: 56, height: 56, marginBottom: 8 }} />
          <Title level={3} style={{ margin: '0 0 4px' }}>{t('login.title')}</Title>
          <p style={{ color: '#888', margin: 0 }}>{t('login.subtitle')}</p>
        </div>
        <Form form={form} layout="vertical" onFinish={handleLogin}>
          <Form.Item
            name="username"
            label={t('login.username')}
            rules={[{ required: true, message: t('placeholder.username') }]}
          >
            <Input placeholder={t('placeholder.username')} size="large" />
          </Form.Item>
          <Form.Item
            name="password"
            label={t('login.password')}
            rules={[{ required: true, message: t('placeholder.password') }]}
          >
            <Input.Password placeholder={t('placeholder.password')} size="large" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" size="large" block>
              {t('login.loginBtn')}
            </Button>
          </Form.Item>
        </Form>
        <div style={{ marginTop: 16, fontSize: 12, color: '#999', textAlign: 'center' }}>
          {t('placeholder.input')}: admin / Admin123!
        </div>
      </Card>
    </div>
  )
}
