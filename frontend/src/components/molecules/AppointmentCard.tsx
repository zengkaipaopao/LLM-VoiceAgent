import React from 'react';
import { Tile, Tag, Button } from '@carbon/react';
import { Edit, TrashCan, Calendar, Map, User, Enterprise } from '@carbon/icons-react';
import styles from './AppointmentCard.module.scss';

/**
 * AppointmentCard Props
 */
interface AppointmentCardProps {
  data: {
    caller_name?: string;
    company?: string;
    appointment_time?: string;
    appointment_content?: string;
    category?: string;
    summary?: string;
    confidence?: number;
  };
  onEdit?: () => void;
  onDelete?: () => void;
}

/**
 * AppointmentCard - 预约信息卡片组件
 * 
 * 功能:
 * - 展示提取出的预约通过详细信息
 * - 显示置信度
 * - 提供编辑和删除操作
 */
export const AppointmentCard: React.FC<AppointmentCardProps> = ({ 
  data, 
  onEdit, 
  onDelete 
}) => {
  const formatDate = (dateString?: string) => {
    if (!dateString) return '未指定时间';
    try {
      return new Date(dateString).toLocaleString('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateString;
    }
  };

  const getConfidenceColor = (confidence: number = 0) => {
    if (confidence >= 0.8) return 'green';
    if (confidence >= 0.5) return 'warm-gray';
    return 'red';
  };

  return (
    <Tile className={styles.appointmentCard}>
      <div className={styles.header}>
        <div className={styles.titleInfo}>
          <h4 className={styles.summary}>{data.summary || '新预约'}</h4>
          {data.category && (
            <Tag type="blue" size="sm">
              {data.category}
            </Tag>
          )}
        </div>
        <div className={styles.actions}>
          {onEdit && (
            <Button
              kind="ghost"
              size="sm"
              renderIcon={Edit}
              iconDescription="编辑"
              onClick={onEdit}
              hasIconOnly
            />
          )}
          {onDelete && (
            <Button
              kind="danger--ghost"
              size="sm"
              renderIcon={TrashCan}
              iconDescription="删除"
              onClick={onDelete}
              hasIconOnly
            />
          )}
        </div>
      </div>

      <div className={styles.content}>
        <div className={styles.field}>
          <Calendar size={16} className={styles.icon} />
          <span className={styles.label}>时间:</span>
          <span className={styles.value}>{formatDate(data.appointment_time)}</span>
        </div>

        {data.caller_name && (
          <div className={styles.field}>
            <User size={16} className={styles.icon} />
            <span className={styles.label}>姓名:</span>
            <span className={styles.value}>{data.caller_name}</span>
          </div>
        )}

        {data.company && (
          <div className={styles.field}>
            <Enterprise size={16} className={styles.icon} />
            <span className={styles.label}>公司:</span>
            <span className={styles.value}>{data.company}</span>
          </div>
        )}
        
        {data.appointment_content && (
           <div className={styles.field}>
            <Map size={16} className={styles.icon} />
            <span className={styles.label}>内容:</span>
            <span className={styles.value}>{data.appointment_content}</span>
          </div>
        )}
      </div>
      
      {data.confidence !== undefined && (
        <div className={styles.footer}>
          <span className={styles.confidenceLabel}>AI 置信度:</span>
          <Tag type={getConfidenceColor(data.confidence)} size="sm">
            {(data.confidence * 100).toFixed(0)}%
          </Tag>
        </div>
      )}
    </Tile>
  );
};
