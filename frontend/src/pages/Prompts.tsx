import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PageTemplate } from '../components/templates/PageTemplate';
import { PromptList } from '../features/prompts/components/PromptList';
import { PromptEditor } from '../features/prompts/components/PromptEditor';
import { PromptTemplate as PromptModel } from '../types/shared';

/**
 * PromptsPage - Agent Management Page
 */
export function Prompts() {
  const { t } = useTranslation(['pages', 'common']);
  const [editorOpen, setEditorOpen] = useState(false);
  const [currentPrompt, setCurrentPrompt] = useState<PromptModel | undefined>(undefined);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleCreate = () => {
    setCurrentPrompt(undefined);
    setEditorOpen(true);
  };

  const handleEdit = (prompt: PromptModel) => {
    setCurrentPrompt(prompt);
    setEditorOpen(true);
  };

  const handleClose = () => {
    setEditorOpen(false);
    setCurrentPrompt(undefined);
  };

  const handleSave = () => {
    setRefreshKey((prev) => prev + 1);
  };

  return (
    <PageTemplate
      title="Agent Management" // t('pages:prompts.title')
      subtitle="Configure your AI agents (Prompts, Models, Voice)" // t('pages:prompts.subtitle')
    >
      <PromptList 
        key={refreshKey}
        onCreate={handleCreate}
        onEdit={handleEdit}
      />
      
      <PromptEditor 
        open={editorOpen}
        prompt={currentPrompt}
        onClose={handleClose}
        onSave={handleSave}
      />
    </PageTemplate>
  );
}
