import React from 'react';
import {
  Modal,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
} from '@carbon/react';
import { useTranslation } from 'react-i18next';

import { PromptTemplate } from '../../../types/shared';
import { usePromptEditorForm } from '../hooks/usePromptEditorForm';
import { PromptEditorGeneralTab } from './prompt-editor/PromptEditorGeneralTab';
import { PromptEditorModelTab } from './prompt-editor/PromptEditorModelTab';
import { PromptEditorPromptTab } from './prompt-editor/PromptEditorPromptTab';
import { PromptEditorVoiceTab } from './prompt-editor/PromptEditorVoiceTab';

interface PromptEditorProps {
  open: boolean;
  prompt?: PromptTemplate;
  onClose: () => void;
  onSave: () => void;
}

export const PromptEditor: React.FC<PromptEditorProps> = ({
  open,
  prompt,
  onClose,
  onSave,
}) => {
  const { t } = useTranslation('pages');
  const {
    form,
    saving,
    models,
    loadingModels,
    modelLoadError,
    geminiVoices,
    loadingGeminiVoices,
    geminiVoiceLoadError,
    isEditMode,
    handleChange,
    handleSave,
  } = usePromptEditorForm({
    open,
    prompt,
    onClose,
    onSave,
  });

  return (
    <Modal
      open={open}
      modalHeading={isEditMode ? t('prompts.editor.title.edit') : t('prompts.editor.title.create')}
      primaryButtonText={saving ? t('prompts.editor.actions.saving') : t('prompts.editor.actions.save')}
      secondaryButtonText={t('prompts.editor.actions.cancel')}
      onRequestClose={onClose}
      onRequestSubmit={() => {
        void handleSave();
      }}
      primaryButtonDisabled={saving}
      size="lg"
    >
      <Tabs>
        <TabList aria-label="Agent Configuration">
          <Tab>{t('prompts.editor.tabs.general')}</Tab>
          <Tab>{t('prompts.editor.tabs.model')}</Tab>
          <Tab>{t('prompts.editor.tabs.prompt')}</Tab>
          <Tab>{t('prompts.editor.tabs.voice')}</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            <PromptEditorGeneralTab
              form={form}
              isEditMode={isEditMode}
              onChange={handleChange}
              t={t}
            />
          </TabPanel>
          <TabPanel>
            <PromptEditorModelTab
              form={form}
              models={models}
              loadingModels={loadingModels}
              modelLoadError={modelLoadError}
              onChange={handleChange}
              t={t}
            />
          </TabPanel>
          <TabPanel>
            <PromptEditorPromptTab form={form} onChange={handleChange} t={t} />
          </TabPanel>
          <TabPanel>
            <PromptEditorVoiceTab
              form={form}
              geminiVoices={geminiVoices}
              loadingGeminiVoices={loadingGeminiVoices}
              geminiVoiceLoadError={geminiVoiceLoadError}
              onChange={handleChange}
              t={t}
            />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Modal>
  );
};
