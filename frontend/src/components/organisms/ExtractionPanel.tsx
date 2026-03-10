import React, { useState } from 'react';
import { Button, Loading, InlineNotification } from '@carbon/react';
import { WatsonHealthTextAnnotationToggle, CheckmarkFilled } from '@carbon/icons-react';
import { AppointmentCard } from '../molecules/AppointmentCard';
import { http } from '../../api/http';
import styles from './ExtractionPanel.module.scss';

/**
 * ExtractionPanel Props
 */
interface ExtractionPanelProps {
  callId: string;
  templateCode?: string;
  onExtractionComplete?: (data: any) => void;
}

/**
 * ExtractionPanel - 预约信息提取面板
 * 
 * 功能:
 * - 触发预约信息提取
 * - 显示提取进度
 * - 展示提取结果 (AppointmentCard)
 * - 错误处理
 */
export const ExtractionPanel: React.FC<ExtractionPanelProps> = ({ 
  callId, 
  templateCode = 'general_appointment',
  onExtractionComplete
}) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExtract = async () => {
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const response = await http.post('/chat/extract', {
        call_id: callId,
        template_code: templateCode
      });

      if (!response.data?.success) {
        throw new Error(response.data?.message || 'Extraction failed');
      }

      const extracted = response.data?.data?.extracted_data ?? {};
      setData(extracted);
      if (onExtractionComplete) {
        onExtractionComplete(extracted);
      }
    } catch (err: any) {
      setError(err.response?.data?.message || err.message || 'Unknown error occurred during extraction');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.extractionPanel}>
      <div className={styles.header}>
        <h4 className={styles.title}>信息提取</h4>
        {!data && !loading && (
          <Button
            kind="tertiary"
            size="sm"
            renderIcon={WatsonHealthTextAnnotationToggle}
            onClick={handleExtract}
            disabled={!callId}
          >
            提取预约信息
          </Button>
        )}
      </div>

      {loading && (
        <div className={styles.loadingContainer}>
          <Loading description="正在分析对话..." withOverlay={false} small />
          <span className={styles.loadingText}>正在分析对话内容提取预约信息...</span>
        </div>
      )}

      {error && (
        <InlineNotification
          kind="error"
          title="提取失败"
          subtitle={error}
          lowContrast
        />
      )}

      {data && (
        <div className={styles.resultContainer}>
          <div className={styles.successHeader}>
             <CheckmarkFilled className={styles.successIcon} />
             <span>提取成功</span>
             <Button 
                kind="ghost" 
                size="sm" 
                onClick={handleExtract}
                className={styles.reExtractBtn}
             >
               重新提取
             </Button>
          </div>
          
          <AppointmentCard 
            data={data}
            onEdit={() => console.log('Edit clicked')} // TODO: Implement edit
            onDelete={() => setData(null)}
          />
        </div>
      )}
    </div>
  );
};
