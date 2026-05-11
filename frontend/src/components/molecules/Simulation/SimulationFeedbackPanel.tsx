import { CodeSnippet, InlineNotification, Loading, Stack, Tile } from '@carbon/react';

type SimulationResult = Record<string, unknown> | null;

interface SimulationFeedbackPanelProps {
  loading: boolean;
  loadingDescription: string;
  error: string | null;
  errorTitle: string;
  onDismissError: () => void;
  result: SimulationResult;
  successTitle: string;
  successFallbackMessage: string;
  onDismissResult: () => void;
  responseTitle: string;
  copyFeedback: string;
}

function getResultMessage(result: SimulationResult, fallback: string): string {
  if (!result) return fallback;
  const message = result._message;
  if (typeof message === 'string' && message.trim() !== '') {
    return message;
  }
  return fallback;
}

export function SimulationFeedbackPanel({
  loading,
  loadingDescription,
  error,
  errorTitle,
  onDismissError,
  result,
  successTitle,
  successFallbackMessage,
  onDismissResult,
  responseTitle,
  copyFeedback,
}: SimulationFeedbackPanelProps) {
  return (
    <>
      {loading && <Loading description={loadingDescription} withOverlay={false} />}

      {error && (
        <InlineNotification
          kind="error"
          title={errorTitle}
          subtitle={error}
          onCloseButtonClick={onDismissError}
          lowContrast
        />
      )}

      {result && !error && (
        <InlineNotification
          kind="success"
          title={successTitle}
          subtitle={getResultMessage(result, successFallbackMessage)}
          onCloseButtonClick={onDismissResult}
          lowContrast
        />
      )}

      {result && (
        <Tile>
          <Stack gap={4}>
            <h4 className="cds--label">{responseTitle}</h4>
            <CodeSnippet type="multi" feedback={copyFeedback} wrapText>
              {JSON.stringify(result, null, 2)}
            </CodeSnippet>
          </Stack>
        </Tile>
      )}
    </>
  );
}
