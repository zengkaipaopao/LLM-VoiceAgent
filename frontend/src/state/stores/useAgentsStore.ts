import { useMemo } from 'react';

import { AgentProfile } from '../../types';

const defaultAgents: AgentProfile[] = [
  {
    id: 'agent_1',
    name: 'Global Sales Bot',
    llmProvider: 'openai',
    voice: 'alloy',
    temperature: 0.3,
  },
  {
    id: 'agent_2',
    name: 'China Care Bot',
    llmProvider: 'azure',
    voice: 'ling',
    temperature: 0.5,
  },
];

export function useAgentsStore() {
  const agents = useMemo(() => defaultAgents, []);
  return { agents };
}
