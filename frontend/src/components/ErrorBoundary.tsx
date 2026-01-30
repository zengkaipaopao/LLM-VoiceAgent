import { Component, ErrorInfo, ReactNode } from 'react';
import { Button, Tile, Theme } from '@carbon/react';
import { WarningAltFilled } from '@carbon/icons-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <Theme theme="g10">
          <div
            style={{
              height: '100vh',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#f4f4f4',
              padding: '1rem',
            }}
          >
            <Tile style={{ maxWidth: '500px', width: '100%' }}>
              <div style={{ marginBottom: '1.5rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
                <WarningAltFilled size={32} fill="#da1e28" />
                <h3 style={{ margin: 0 }}>出错了</h3>
              </div>
              <p style={{ marginBottom: '2rem' }}>
                应用程序遇到意外错误。请尝试刷新页面。如果问题持续存在，请联系管理员。
              </p>
              {this.state.error && (
                <div style={{ 
                  background: '#f4f4f4', 
                  padding: '1rem', 
                  borderRadius: '0.5rem', 
                  fontSize: '0.875rem', 
                  marginBottom: '2rem',
                  overflowX: 'auto'
                }}>
                  <code>{this.state.error.message}</code>
                </div>
              )}
              <Button onClick={this.handleReload}>
                刷新页面
              </Button>
            </Tile>
          </div>
        </Theme>
      );
    }

    return this.props.children;
  }
}
