import { TextArea, TextInput, Toggle } from '@carbon/react';
import { useTranslation } from 'react-i18next';

interface TwilioTokenConfigFieldsProps {
  useEndpoint: boolean;
  setUseEndpoint: (value: boolean) => void;
  tokenEndpoint: string;
  setTokenEndpoint: (value: string) => void;
  accessToken: string;
  setAccessToken: (value: string) => void;
  tokenEndpointPlaceholder: string;
}

export function TwilioTokenConfigFields({
  useEndpoint,
  setUseEndpoint,
  tokenEndpoint,
  setTokenEndpoint,
  accessToken,
  setAccessToken,
  tokenEndpointPlaceholder,
}: TwilioTokenConfigFieldsProps) {
  const { t } = useTranslation(['pages']);

  return (
    <>
      <Toggle
        id="twilio-use-endpoint"
        labelText={t('pages:test.twilio.form.useEndpoint', '使用 Token Endpoint')}
        labelA={t('pages:test.twilio.form.manual', '手动')}
        labelB={t('pages:test.twilio.form.endpoint', '端点')}
        toggled={useEndpoint}
        onToggle={(value) => setUseEndpoint(value)}
      />

      <TextInput
        id="twilio-token-endpoint"
        labelText={t('pages:test.twilio.form.endpointUrl', 'Token Endpoint URL')}
        value={tokenEndpoint}
        onChange={(event) => setTokenEndpoint(event.target.value)}
        disabled={!useEndpoint}
        placeholder={tokenEndpointPlaceholder}
      />

      <TextArea
        id="twilio-access-token"
        labelText={t('pages:test.twilio.form.token', 'Twilio Access Token')}
        value={accessToken}
        onChange={(event) => setAccessToken(event.target.value)}
        rows={8}
      />
    </>
  );
}
