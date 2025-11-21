from abc import ABC, abstractmethod


class TelephonyAdapter(ABC):
    @abstractmethod
    async def place_call(self, *, to: str, metadata: dict | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    async def handle_webhook(self, payload: dict) -> None:
        raise NotImplementedError


class DummyTelephonyAdapter(TelephonyAdapter):
    async def place_call(self, *, to: str, metadata: dict | None = None) -> str:
        return f"mock-call-to-{to}"

    async def handle_webhook(self, payload: dict) -> None:
        # TODO: connect to actual webhook data when provider is available.
        _ = payload


telephony_adapter: TelephonyAdapter = DummyTelephonyAdapter()
