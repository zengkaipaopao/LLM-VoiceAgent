import {
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
} from '@carbon/react';
import { useAppState } from '../state/AppStateContext';

export function CallsPage() {
  const { calls } = useAppState();

  const headers = [
    { key: 'id', header: 'ID' },
    { key: 'direction', header: '方向' },
    { key: 'counterpart', header: '对端号码' },
    { key: 'startedAt', header: '开始时间' },
    { key: 'durationSeconds', header: '时长 (秒)' },
    { key: 'status', header: '状态' },
  ];

  const rows = calls.map((call) => ({
    id: call.id,
    direction: call.direction === 'inbound' ? '呼入' : '呼出',
    counterpart: call.counterpart,
    startedAt: new Date(call.startedAt).toLocaleString(),
    durationSeconds: call.durationSeconds.toString(),
    status: call.status,
  }));

  return (
    <section className="page-section">
      <h1 className="page-title">通话记录</h1>
      <p className="page-subtitle">查看每一次呼入或呼出的细节，并准备接入录音、搜索与过滤。</p>
      <TableContainer title="通话列表">
        <TableToolbar>
          <TableToolbarContent>
            <TableToolbarSearch persistent size="lg" placeholder="搜索号码或状态" />
          </TableToolbarContent>
        </TableToolbar>
        <Table aria-label="通话记录">
          <TableHead>
            <TableRow>
              {headers.map((header) => (
                <TableHeader key={header.key}>{header.header}</TableHeader>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.id}</TableCell>
                <TableCell>{row.direction}</TableCell>
                <TableCell>{row.counterpart}</TableCell>
                <TableCell>{row.startedAt}</TableCell>
                <TableCell>{row.durationSeconds}</TableCell>
                <TableCell>{row.status}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </section>
  );
}
