import React, { useState, useEffect } from 'react';
import {
  Modal,
  TextInput,
  TextArea,
  Select,
  SelectItem,
  NumberInput,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  FormGroup,
  Stack,
} from '@carbon/react';
import { useTranslation } from 'react-i18next';
import { PromptTemplate, PromptFormValues } from '../../../types/shared';
import { fetchModels, createPrompt, updatePrompt } from '../../../api/prompts';


interface PromptEditorProps {
  open: boolean;
  prompt?: PromptTemplate; // If provided, edit mode
  onClose: () => void;
  onSave: () => void;
}

const defaultValues: PromptFormValues = {
  name: '',
  code: '',
  description: '',
  category: 'booking',
  llmProvider: 'gemini',
  llmModel: 'gemini-2.0-flash',
  temperature: 0.7,
  maxTokens: 2048,
  systemPrompt: 'You are a helpful AI assistant.',
  extractionPrompt: '',
  extractionSchema: '',
  responseFormat: 'text',
  outputSchema: '',
  voiceProvider: '',
  voiceId: '',
};

export const PromptEditor: React.FC<PromptEditorProps> = ({
  open,
  prompt,
  onClose,
  onSave,
}) => {
  const { t } = useTranslation('pages');
  const [form, setForm] = useState<PromptFormValues>(defaultValues);
  const [saving, setSaving] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  useEffect(() => {
    if (prompt) {
      setForm({
        name: prompt.name,
        code: prompt.code,
        description: prompt.description,
        category: prompt.category,
        llmProvider: prompt.llmProvider,
        llmModel: prompt.llmModel,
        temperature: prompt.temperature,
        maxTokens: prompt.maxTokens,
        systemPrompt: prompt.systemPrompt,
        extractionPrompt: prompt.extractionPrompt,
        extractionSchema: prompt.extractionSchema ? JSON.stringify(prompt.extractionSchema, null, 2) : '',
        responseFormat: prompt.responseFormat || 'text',
        outputSchema: prompt.outputSchema
          ? JSON.stringify(prompt.outputSchema, null, 2)
          : (prompt.extractionSchema ? JSON.stringify(prompt.extractionSchema, null, 2) : ''),
        voiceProvider: prompt.voiceProvider,
        voiceId: prompt.voiceId,
        // Legacy fields ignored for editing if new ones exist
      });
    } else {
      setForm(defaultValues);
    }
  }, [prompt, open]);

  // Fetch models when provider changes
  useEffect(() => {
    const loadModels = async () => {
      // If provider is empty, don't fetch or clear models?
      // Default to gemini if empty as per defaultValues
      const provider = form.llmProvider || 'gemini'; 
      setLoadingModels(true);
      try {
        const fetchedModels = await fetchModels(provider);
        setModels(fetchedModels);
      } catch (err) {
        console.error('Failed to fetch models', err);
        setModels([]); 
      } finally {
        setLoadingModels(false);
      }
    };
    loadModels();
  }, [form.llmProvider, open]); // Add open to refresh when modal opens

  const handleChange = (field: keyof PromptFormValues, value: any) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    if (form.outputSchema?.trim()) {
      try {
        JSON.parse(form.outputSchema);
      } catch {
        alert('Output JSON Schema is invalid JSON.');
        return;
      }
    }

    if (form.extractionSchema?.trim()) {
      try {
        JSON.parse(form.extractionSchema);
      } catch {
        alert('Extraction JSON Schema is invalid JSON.');
        return;
      }
    }

    setSaving(true);
    try {
      if (prompt) {
        await updatePrompt(prompt.id, form);
      } else {
        await createPrompt(form);
      }
      onSave();
      onClose();
    } catch (err) {
      console.error('Failed to save prompt', err);
      alert('Failed to save prompt. Check console for details.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      modalHeading={prompt ? t('prompts.editor.title.edit') : t('prompts.editor.title.create')}
      primaryButtonText={saving ? t('prompts.editor.actions.saving') : t('prompts.editor.actions.save')}
      secondaryButtonText={t('prompts.editor.actions.cancel')}
      onRequestClose={onClose}
      onRequestSubmit={handleSave}
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
            <Stack gap={6}>
              <TextInput
                id="name"
                labelText={t('prompts.editor.fields.name')}
                value={form.name}
                onChange={(e) => handleChange('name', e.target.value)}
                placeholder={t('prompts.editor.fields.namePlaceholder')}
              />
              <TextInput
                id="code"
                labelText={t('prompts.editor.fields.code')}
                value={form.code}
                onChange={(e) => handleChange('code', e.target.value)}
                placeholder={t('prompts.editor.fields.codePlaceholder')}
                readOnly={!!prompt} // Code is immutable after creation usually
                helperText={prompt ? "Code cannot be changed" : "Unique identifier for this agent"}
              />
              <TextInput
                id="description"
                labelText={t('prompts.editor.fields.description')}
                value={form.description || ''}
                onChange={(e) => handleChange('description', e.target.value)}
              />
              <Select
                id="category"
                labelText="Category"
                value={form.category || 'booking'}
                onChange={(e) => handleChange('category', e.target.value)}
              >
                  <SelectItem value="booking" text="Booking" />
                  <SelectItem value="customer_service" text="Customer Service" />
                  <SelectItem value="support" text="Support" />
                  <SelectItem value="sales" text="Sales" />
                  <SelectItem value="other" text="Other" />
              </Select>
            </Stack>
          </TabPanel>
          <TabPanel>
            <Stack gap={6}>
              <Select
                id="llmProvider"
                labelText={t('prompts.editor.fields.provider')}
                value={form.llmProvider}
                onChange={(e) => handleChange('llmProvider', e.target.value)}
              >
                <SelectItem value="gemini" text="Google Gemini" />
                <SelectItem value="openai" text="OpenAI (Planning)" />
                <SelectItem value="claude" text="Anthropic Claude (Planning)" />
              </Select>
              <Select
                id="llmModel"
                labelText={t('prompts.editor.fields.model')}
                value={form.llmModel}
                onChange={(e) => handleChange('llmModel', e.target.value)}
                helperText="Select a model supported by the provider"
                disabled={loadingModels}
              >
                 {models.map(model => (
                     <SelectItem key={model} value={model} text={model} />
                 ))}
                 {/* If current model is set but not in list (e.g. custom or deprecated), show it */}
                 {!models.includes(form.llmModel) && form.llmModel && (
                     <SelectItem value={form.llmModel} text={`${form.llmModel} (Current)`} />
                 )}
              </Select>
              <div style={{ display: 'flex', gap: '1rem' }}>
                  <div style={{ flex: 1 }}>
                    <NumberInput
                        id="temperature"
                        label={t('prompts.editor.fields.temperature')}
                        min={0}
                        max={2}
                        step={0.1}
                        value={form.temperature}
                        onChange={(e, { value }) => handleChange('temperature', Number(value))}
                        invalidText="0-2"
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <NumberInput
                        id="maxTokens"
                        label={t('prompts.editor.fields.maxTokens')}
                        min={1}
                        max={32000}
                        step={1}
                        value={form.maxTokens}
                        onChange={(e, { value }) => handleChange('maxTokens', Number(value))}
                    />
                  </div>
              </div>
              
              <Select
                id="responseFormat"
                labelText="Response Format"
                value={form.responseFormat || 'text'}
                onChange={(e) => handleChange('responseFormat', e.target.value)}
              >
                  <SelectItem value="text" text="Text (Default)" />
                  <SelectItem value="json_object" text="JSON Object" />
              </Select>
              
              {form.responseFormat === 'json_object' && (
                  <TextArea
                    id="outputSchema"
                    labelText="Output JSON Schema"
                    value={form.outputSchema || ''}
                    onChange={(e) => handleChange('outputSchema', e.target.value)}
                    rows={8}
                    placeholder={'{\n  "type": "object",\n  "properties": {\n    "summary": {"type": "string"}\n  }\n}'}
                    helperText="Define the JSON schema for validation (Optional)"
                    enableCounter
                  />
              )}
            </Stack>
          </TabPanel>
          <TabPanel>
             <Stack gap={6}>
                <TextArea
                    id="systemPrompt"
                    labelText={t('prompts.editor.fields.systemPrompt')}
                    value={form.systemPrompt}
                    onChange={(e) => handleChange('systemPrompt', e.target.value)}
                    rows={15}
                    enableCounter
                />
                <TextArea
                    id="extractionPrompt"
                    labelText={t('prompts.editor.fields.extractionPrompt')}
                    value={form.extractionPrompt || ''}
                    onChange={(e) => handleChange('extractionPrompt', e.target.value)}
                    rows={5}
                    helperText={t('prompts.editor.fields.extractionPromptHelper')}
                />
                <TextArea
                    id="extractionSchema"
                    labelText="Extraction JSON Schema (for table/extraction)"
                    value={form.extractionSchema || ''}
                    onChange={(e) => handleChange('extractionSchema', e.target.value)}
                    rows={8}
                    placeholder={'{\n  "fields": [\n    {"name": "caller_name", "label": "Caller"},\n    {"name": "pickup_address", "label": "Address"}\n  ]\n}'}
                    helperText="Define extraction fields for appointment table columns."
                    enableCounter
                />
             </Stack>
          </TabPanel>
          <TabPanel>
            <Stack gap={6}>
              <Select
                id="voiceProvider"
                labelText={t('prompts.editor.fields.voiceProvider')}
                value={form.voiceProvider || ''}
                onChange={(e) => handleChange('voiceProvider', e.target.value)}
              >
                  <SelectItem value="" text="None (Text only)" />
                  <SelectItem value="elevenlabs" text="ElevenLabs" />
                  <SelectItem value="openai" text="OpenAI TTS" />
                  <SelectItem value="system" text="System TTS" />
              </Select>
              <TextInput
                id="voiceId"
                labelText={t('prompts.editor.fields.voiceId')}
                value={form.voiceId || ''}
                onChange={(e) => handleChange('voiceId', e.target.value)}
                disabled={!form.voiceProvider}
              />
            </Stack>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Modal>
  );
};
