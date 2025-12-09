import { Fragment, useMemo, useState } from 'react';
import {
  Button,
  ComposedModal,
  ModalBody,
  ModalFooter,
  ModalHeader,
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
} from '@carbon/react';

import { ReservationRecord } from '../types';
import { useAppState } from '../state/AppStateContext';
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
  const { reservations, loadingReservations } = useAppState();
  const [search, setSearch] = useState('');
  const [selectedRecord, setSelectedRecord] = useState<ReservationRecord | null>(null);

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
        {loadingReservations ? (
          <p>予約データを取得中...</p>
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
