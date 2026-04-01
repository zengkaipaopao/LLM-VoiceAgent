import { useMemo } from 'react';
import { Dropdown } from '@carbon/react';

import { PromptTemplate } from '../../../types/shared';
import styles from './AppointmentsPromptSelector.module.scss';

type PromptDropdownItem = {
  id: string;
  text: string;
};

interface AppointmentsPromptSelectorProps {
  availablePrompts: PromptTemplate[];
  selectedPromptId: string;
  onPromptChange: (promptId: string) => void;
  titleText: string;
  label: string;
}

export function AppointmentsPromptSelector({
  availablePrompts,
  selectedPromptId,
  onPromptChange,
  titleText,
  label,
}: AppointmentsPromptSelectorProps) {
  const promptDropdownItems = useMemo<PromptDropdownItem[]>(
    () => availablePrompts.map((prompt) => ({ id: prompt.id, text: prompt.name })),
    [availablePrompts]
  );

  const selectedItem = promptDropdownItems.find((item) => item.id === selectedPromptId) || null;

  return (
    <div className={styles.container}>
      <Dropdown
        id="prompt-switcher"
        titleText={titleText}
        label={label}
        items={promptDropdownItems}
        itemToString={(item) => (item ? item.text : '')}
        selectedItem={selectedItem}
        onChange={({ selectedItem: nextSelectedItem }) => {
          if (!nextSelectedItem) {
            return;
          }
          onPromptChange(nextSelectedItem.id);
        }}
      />
    </div>
  );
}
