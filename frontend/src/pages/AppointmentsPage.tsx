import { Fragment, useMemo, useState } from 'react';
import {
  Button,
  ComposedModal,
  DataTableSkeleton,
  ModalBody,
  ModalFooter,
  ModalHeader,
  SkeletonText,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
  Tag,
  Tile,
} from '@carbon/react';

import { ReservationRecord } from '../types';
import { useAppointmentsQuery } from '../api/hooks';
import styles from './AppointmentsPage.module.css';

const operationLabel: Record<ReservationRecord['operation'], string> = {
  create: '新規',
  update: '変更',
  delete: '取消',
};

const operationTagType: Record<ReservationRecord['operation'], string> = {
  create: 'teal',
  update: 'blue',
  delete: 'magenta',
};

const headers = [
  { key: 'timestamp', header: '受付時間' },
  { key: 'callerName', header: '連絡者' },
  { key: 'company', header: '会社名' },
  { key: 'appointment', header: '希望日時' },
  { key: 'category', header: '品目' },
  { key: 'amount', header: '分量' },
  { key: 'address', header: '住所' },
  { key: 'summary', header: '要約' },
  { key: 'extraRequest', header: '追加要望' },
  { key: 'rawMessages', header: '原文ログ' },
  { key: 'operation', header: '操作' },
];

const detailLabels: Record<keyof ReservationRecord, string> = {
  id: 'ID',
  timestamp: '受付時間',
  callerName: '連絡者',
  company: '会社名',
  appointment: '希望日時',
  category: '品目',
  amount: '分量',
  address: '住所',
  summary: '要約',
  extraRequest: '追加要望',
  rawMessages: '原文ログ',
  operation: '操作タイプ',
};

export function AppointmentsPage() {
  const { data: reservations = [], isLoading } = useAppointmentsQuery();
  const [search, setSearch] = useState('');
  const [selectedRecord, setSelectedRecord] = useState<ReservationRecord | null>(null);

  const metrics = useMemo(() => {
    const totals = reservations.reduce(
      (acc, record) => {
        acc.total += 1;
        acc[record.operation] += 1;
        return acc;
      },
      {
        total: 0,
        create: 0,
        update: 0,
        delete: 0,
      },
    );
    return totals;
  }, [reservations]);

  const filteredRecords = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return reservations;
    return reservations.filter((record) =>
      (Object.values(record) as string[]).some((value) => value?.toLowerCase().includes(keyword)),
    );
  }, [reservations, search]);

  return (
    <section className="page-section">
      <h1 className="page-title">预约记录</h1>
      <p className="page-subtitle">查看自动接单助手归档的预约信息，点击任意行以查看详细内容。</p>
      <div className={styles.metricsRow}>
        {isLoading ? (
          Array.from({ length: 4 }).map((_, index) => (
            <Tile key={`metric-skeleton-${index}`} className={styles.metricTile}>
              <SkeletonText width="50%" />
              <SkeletonText heading width="30%" />
              <SkeletonText width="70%" />
            </Tile>
          ))
        ) : (
          <>
            <Tile className={styles.metricTile}>
              <p className={styles.metricLabel}>总预约数</p>
              <p className={styles.metricValue}>{metrics.total}</p>
              <p className={styles.metricDesc}>全部历史记录</p>
            </Tile>
            <Tile className={styles.metricTile}>
              <p className={styles.metricLabel}>新预约</p>
              <p className={styles.metricValue}>{metrics.create}</p>
              <p className={styles.metricDesc}>operation = create</p>
            </Tile>
            <Tile className={styles.metricTile}>
              <p className={styles.metricLabel}>预约变更</p>
              <p className={styles.metricValue}>{metrics.update}</p>
              <p className={styles.metricDesc}>operation = update</p>
            </Tile>
            <Tile className={styles.metricTile}>
              <p className={styles.metricLabel}>预约取消</p>
              <p className={styles.metricValue}>{metrics.delete}</p>
              <p className={styles.metricDesc}>operation = delete</p>
            </Tile>
          </>
        )}
      </div>
      <TableContainer title="予約一覧">
        <TableToolbar>
          <TableToolbarContent>
            <TableToolbarSearch
              persistent
              size="lg"
              placeholder="例：会社名 / 住所 / 連絡者"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </TableToolbarContent>
        </TableToolbar>
        {isLoading ? (
          <DataTableSkeleton columnCount={headers.length} rowCount={6} />
        ) : (
          <Table aria-label="予約記録">
            <TableHead>
              <TableRow>
                {headers.map((header) => (
                  <TableHeader key={header.key}>{header.header}</TableHeader>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredRecords.map((record) => (
                <TableRow
                  key={record.id}
                  className={styles.rowClickable}
                  tabIndex={0}
                  onClick={() => setSelectedRecord(record)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelectedRecord(record);
                    }
                  }}
                >
                  <TableCell>{record.timestamp}</TableCell>
                  <TableCell>{record.callerName}</TableCell>
                  <TableCell>
                    <span className={styles.tableCell} title={record.company}>
                      {record.company}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={styles.tableCell} title={record.appointment}>
                      {record.appointment}
                    </span>
                  </TableCell>
                  <TableCell>{record.category}</TableCell>
                  <TableCell>{record.amount}</TableCell>
                  <TableCell>
                    <span className={styles.tableCell} title={record.address}>
                      {record.address}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={styles.tableCell} title={record.summary}>
                      {record.summary}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={styles.tableCell} title={record.extraRequest}>
                      {record.extraRequest || '（なし）'}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={`${styles.tableCell} ${styles.rawCell}`} title={record.rawMessages}>
                      {record.rawMessages}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Tag size="sm" type={operationTagType[record.operation]}>
                      {operationLabel[record.operation]}
                    </Tag>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </TableContainer>

      {selectedRecord && (
        <ComposedModal open onClose={() => setSelectedRecord(null)} size="lg">
          <ModalHeader title="予約詳細" closeButtonLabelText="閉じる" />
          <ModalBody>
            <dl className={styles.detailsList}>
              {(Object.keys(detailLabels) as Array<keyof ReservationRecord>).map((key) => (
                <Fragment key={key}>
                  <dt>{detailLabels[key]}</dt>
                  <dd>
                    {key === 'operation' ? (
                      <Tag size="sm" type={operationTagType[selectedRecord.operation]}>
                        {operationLabel[selectedRecord.operation]}
                      </Tag>
                    ) : (
                      selectedRecord[key]
                    )}
                  </dd>
                </Fragment>
              ))}
            </dl>
          </ModalBody>
          <ModalFooter>
            <Button kind="secondary" onClick={() => setSelectedRecord(null)}>
              閉じる
            </Button>
          </ModalFooter>
        </ComposedModal>
      )}
    </section>
  );
}
