import type { ReactNode } from 'react';
import { Column, Grid, Tag, Tile } from '@carbon/react';

import styles from './TestWorkbenchShell.module.scss';

type TagTone =
  | 'red'
  | 'magenta'
  | 'purple'
  | 'blue'
  | 'cyan'
  | 'teal'
  | 'green'
  | 'gray'
  | 'cool-gray'
  | 'warm-gray'
  | 'high-contrast'
  | 'outline';

export interface TestWorkbenchSummaryItem {
  id: string;
  label: string;
  value: string;
  tone?: TagTone;
  mono?: boolean;
}

interface TestWorkbenchShellProps {
  title: string;
  description: string;
  summaryItems: TestWorkbenchSummaryItem[];
  notice?: ReactNode;
  main: ReactNode;
  side: ReactNode;
}

export function TestWorkbenchShell({
  title,
  description,
  summaryItems,
  notice,
  main,
  side,
}: TestWorkbenchShellProps) {
  return (
    <div className={styles.container}>
      <Grid narrow className={styles.layoutGrid}>
        <Column lg={16} md={8} sm={4} className={styles.summaryColumn}>
          <Tile className={styles.summaryTile}>
            <div className={styles.summaryHeader}>
              <h3 className="cds--heading-03">{title}</h3>
              <p className={styles.summaryDescription}>{description}</p>
            </div>

            {summaryItems.length > 0 && (
              <dl className={styles.summaryList}>
                {summaryItems.map((item) => (
                  <div key={item.id} className={styles.summaryItem}>
                    <dt>{item.label}</dt>
                    <dd className={`${styles.valueText} ${item.mono ? styles.monoValue : ''}`}>
                      {item.tone ? <Tag type={item.tone}>{item.value || '-'}</Tag> : item.value || '-'}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </Tile>
        </Column>

        {notice && (
          <Column lg={16} md={8} sm={4} className={styles.noticeColumn}>
            {notice}
          </Column>
        )}

        <Column lg={11} md={8} sm={4} className={styles.mainColumn}>
          {main}
        </Column>

        <Column lg={5} md={8} sm={4} className={styles.sideColumn}>
          {side}
        </Column>
      </Grid>
    </div>
  );
}
