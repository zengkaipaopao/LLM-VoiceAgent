import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Tile, 
  Stack, 
  NumberInput, 
  Button, 
  ButtonSet 
} from '@carbon/react';
import { Renew, TrashCan } from '@carbon/icons-react';
import styles from './simulation.module.css';

interface BatchTestControlProps {
  // Actions
  onGenerate: (count: number) => void;
  onClear: () => void;
  
  // State
  loading?: boolean;
  
  // Customization
  title?: string;
  description?: React.ReactNode;
  countLabel?: string;
  generateButtonText?: string;
  clearButtonText?: string;
  quickOptions?: number[];
  min?: number;
  max?: number;
}

export const BatchTestControl: React.FC<BatchTestControlProps> = ({
  onGenerate,
  onClear,
  loading = false,
  title,
  description,
  countLabel,
  generateButtonText,
  clearButtonText,
  quickOptions = [10, 50, 100],
  min = 1,
  max = 1000
}) => {
  const { t } = useTranslation(['pages']);
  const [batchCount, setBatchCount] = useState(quickOptions[0] || 10);

  // Defaults fallback to translation logic if not provided
  const _title = title || t('pages:test.simulation.batch.title');
  const _countLabel = countLabel || t('pages:test.simulation.batch.countLabel', '生成数量');
  const _generateBtnText = generateButtonText || t('pages:test.simulation.batch.generate', '生成测试数据');
  const _clearBtnText = clearButtonText || t('pages:test.simulation.batch.clear');

  return (
    <Tile className={styles.toolTile}>
      <Stack gap={6}>
        <div>
          <h4 className="cds--heading-compact-02">{_title}</h4>
          {description && (
            <p className="cds--body-compact-01 cds--text--secondary">
              {description}
            </p>
          )}
        </div>
        
        {/* 主要操作区 */}
        <div className={styles.batchControls}>
          <NumberInput
            id="batch-count"
            label={_countLabel}
            min={min}
            max={max}
            value={batchCount}
            onChange={(e: any) => setBatchCount(Number(e.imaginaryTarget.value))}
            invalidText={t('pages:test.simulation.batch.invalidCount', `请输入${min}-${max}之间的数字`)}
            disabled={loading}
          />
          <Button
            kind="primary"
            onClick={() => onGenerate(batchCount)}
            disabled={loading}
            renderIcon={Renew}
            className={styles.generateButton}
          >
            {_generateBtnText}
          </Button>
        </div>

        {/* 快捷选项 */}
        {quickOptions.length > 0 && (
          <div className={styles.quickActions}>
            <span className="cds--label">{t('pages:test.simulation.batch.quickOptions', '快捷选项:')}</span>
            <ButtonSet>
              {quickOptions.map(option => (
                <Button 
                  key={option}
                  size="sm" 
                  kind="ghost" 
                  onClick={() => setBatchCount(option)}
                  disabled={loading}
                >
                  {option}
                </Button>
              ))}
            </ButtonSet>
          </div>
        )}

        {/* 危险操作 */}
        <Button
          kind="danger--tertiary"
          onClick={onClear}
          disabled={loading}
          renderIcon={TrashCan}
        >
          {_clearBtnText}
        </Button>
      </Stack>
    </Tile>
  );
};
