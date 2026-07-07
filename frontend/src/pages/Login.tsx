import { FormEvent, useState } from 'react';
import { Button, InlineNotification, PasswordInput, TextInput, Theme } from '@carbon/react';
import { Login as LoginIcon, VoiceActivate } from '@carbon/icons-react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../auth/AuthContext';
import { LanguageSwitcher } from '../components/molecules/LanguageSwitcher';
import styles from './Login.module.scss';

export function Login() {
  const { t } = useTranslation('common');
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [hasError, setHasError] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const from = (location.state as { from?: string } | null)?.from || '/';

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setHasError(false);
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch {
      setHasError(true);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Theme theme="g100" className={styles.page}>
      <section className={styles.hero} aria-label="LLM VoiceDesk">
        <div className={styles.heroContent}>
          <div className={styles.mark}><VoiceActivate size={32} /></div>
          <p className={styles.eyebrow}>LLM VoiceDesk</p>
          <h1>{t('login.heroLine1')}<br />{t('login.heroLine2')}</h1>
          <p className={styles.heroCopy}>
            {t('login.heroDescription')}
          </p>
          <div className={styles.signal} aria-hidden="true">
            {[22, 42, 64, 38, 78, 52, 30, 60, 44, 24].map((height, index) => (
              <span key={index} style={{ height }} />
            ))}
          </div>
        </div>
      </section>

      <Theme theme="g10" className={styles.loginTheme}>
        <div className={styles.languageSwitcher}>
          <LanguageSwitcher />
        </div>
        <main className={styles.loginPanel}>
          <div className={styles.formWrap}>
            <p className={styles.product}>LLM <strong>VoiceDesk</strong></p>
            <h2>{t('login.title')}</h2>
            <p className={styles.intro}>{t('login.description')}</p>

            {hasError && (
              <InlineNotification
                kind="error"
                title={t('login.errorTitle')}
                subtitle={t('login.errorMessage')}
                hideCloseButton
                lowContrast
              />
            )}

            <form onSubmit={handleSubmit} className={styles.form}>
              <TextInput
                id="username"
                labelText={t('login.username')}
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
              />
              <PasswordInput
                id="password"
                labelText={t('login.password')}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
              <Button
                type="submit"
                renderIcon={LoginIcon}
                disabled={submitting || !username || !password}
                className={styles.submit}
              >
                {submitting ? t('login.submitting') : t('login.submit')}
              </Button>
            </form>
            <p className={styles.security}>{t('login.security')}</p>
          </div>
        </main>
      </Theme>
    </Theme>
  );
}
