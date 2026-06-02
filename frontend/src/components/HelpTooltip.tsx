import { Tooltip, Typography } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'
import { ReactNode } from 'react'

const { Text } = Typography

interface HelpTooltipProps {
  children: ReactNode
  title: string
}

export function HelpTooltip({ children, title }: HelpTooltipProps) {
  return (
    <Tooltip
      title={<Text style={{ color: '#fff', fontSize: 12 }}>{title}</Text>}
      placement="top"
    >
      <span style={{ marginLeft: 4, color: '#999', cursor: 'help', fontSize: 12 }}>
        <QuestionCircleOutlined />
      </span>
    </Tooltip>
  )
}

export default HelpTooltip
