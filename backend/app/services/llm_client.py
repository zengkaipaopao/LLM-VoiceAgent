from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, *, prompt: str, session_id: str) -> str:
        raise NotImplementedError


class DummyLLMClient(LLMClient):
    async def generate(self, *, prompt: str, session_id: str) -> str:
        return f"[session={session_id}] Echo: {prompt[:50]}"


llm_client: LLMClient = DummyLLMClient()
