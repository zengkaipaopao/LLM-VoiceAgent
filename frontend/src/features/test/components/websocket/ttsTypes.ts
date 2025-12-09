export type TtsProviderOption = {
  id: string;
  label: string;
};

export type TtsModelOption = {
  id: string;
  label: string;
};

export type GoogleVoiceOption = {
  id: string;
  label: string;
};

export type GoogleLanguageOption = {
  code: string;
  label: string;
  voices: GoogleVoiceOption[];
};
