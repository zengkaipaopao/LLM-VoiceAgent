import { ReactNode } from 'react';
import { Button } from '@carbon/react';
import { View } from '@carbon/icons-react';

import { CallHandlerCell, CallStatusTag } from '../../molecules/Calls/CallTableCells';
import { CallTableRow } from '../../../hooks/useCallsPage';
import { CallLog } from '../../../types/shared';
import {
  CallHandlerLabels,
  CallStatusLabels,
  formatCallDateTime,
  formatCallDuration,
} from './callsDataTableConfig';

type TranslateFn = (key: string) => string;

interface RenderCallsTableCellOptions {
  cellValue: unknown;
  cellKey: string;
  row: CallTableRow;
  statusLabels: CallStatusLabels;
  handlerLabels: CallHandlerLabels;
  onViewCall: (call: CallLog) => void;
  t: TranslateFn;
}

export function renderCallsTableCell({
  cellValue,
  cellKey,
  row,
  statusLabels,
  handlerLabels,
  onViewCall,
  t,
}: RenderCallsTableCellOptions): ReactNode {
  if (cellKey === 'status') {
    return <CallStatusTag status={String(cellValue ?? '')} labels={statusLabels} />;
  }

  if (cellKey === 'handler') {
    const normalizedHandler =
      typeof cellValue === 'string' && cellValue.trim().length > 0 ? cellValue : undefined;
    return <CallHandlerCell handlerType={normalizedHandler} labels={handlerLabels} />;
  }

  if (cellKey === 'started_at') {
    return formatCallDateTime(String(cellValue ?? ''));
  }

  if (cellKey === 'duration') {
    return formatCallDuration(Number(cellValue ?? 0));
  }

  if (cellKey === 'actions') {
    return (
      <Button
        kind="ghost"
        size="sm"
        hasIconOnly
        renderIcon={View}
        iconDescription={t('calls.table.actions.viewDetails')}
        onClick={() => {
          onViewCall(row.raw);
        }}
      />
    );
  }

  return cellValue as ReactNode;
}
