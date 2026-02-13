import { useTranslation } from 'react-i18next';
import { Dropdown } from '@carbon/react';

interface LanguageOption {
  id: string;
  label: string;
  flag: string;
}

const languages: LanguageOption[] = [
  { id: 'zh-CN', label: '中文', flag: '🇨🇳' },
  { id: 'en-US', label: 'English', flag: '🇺🇸' },
  { id: 'ja-JP', label: '日本語', flag: '🇯🇵' },
];

/**
 * LanguageSwitcher - 语言切换组件
 * 
 * 紧凑的语言切换下拉菜单,适合放在HeaderGlobalBar中
 * 语言偏好会自动保存到localStorage
 */
export function LanguageSwitcher() {
  const { i18n } = useTranslation();

  const currentLanguage = languages.find((lang) => lang.id === i18n.language) || languages[0];

  const handleLanguageChange = ({ selectedItem }: { selectedItem: LanguageOption | null }) => {
    if (selectedItem) {
      i18n.changeLanguage(selectedItem.id);
    }
  };

  return (
    <div style={{ 
      minWidth: '120px', 
      maxWidth: '120px',
      marginRight: '0.5rem',
      display: 'flex',
      alignItems: 'center'
    }}>
      <Dropdown
        id="language-switcher"
        titleText=""
        label={`${currentLanguage.flag} ${currentLanguage.label}`}
        items={languages}
        itemToString={(item) => (item ? `${item.flag} ${item.label}` : '')}
        selectedItem={currentLanguage}
        onChange={handleLanguageChange}
        size="sm"
        hideLabel
      />
    </div>
  );
}
