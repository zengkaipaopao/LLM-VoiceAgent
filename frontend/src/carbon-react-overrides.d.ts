import 'react';

declare module 'react' {
  // Polyfill missing legacy types exported by older react typings that 
  // @carbon/react still incorrectly references, preventing TS2724.
  type HTMLElementType = React.ElementType;
  type ToggleEventHandler<T = Element> = (event: React.SyntheticEvent<T>) => void;
}
