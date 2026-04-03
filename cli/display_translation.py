from __future__ import annotations

import json
import re
import threading
from collections import deque
from copy import deepcopy
from typing import Any

from tradingagents.llm_clients import create_llm_client


class DisplayTranslator:
    TRANSLATABLE_KEYS = {"content", "current_report", "final_report", "error"}
    DECISION_TRANSLATIONS = {
        "BUY": "买入",
        "OVERWEIGHT": "增持",
        "HOLD": "持有",
        "UNDERWEIGHT": "减持",
        "SELL": "卖出",
    }

    def __init__(
        self,
        *,
        output_language: str,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        google_thinking_level: str | None = None,
        openai_reasoning_effort: str | None = None,
        anthropic_effort: str | None = None,
        runtime_enabled: bool = True,
    ) -> None:
        self.output_language = output_language.strip() or "English"
        self.enabled = self.output_language.lower() != "english"
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._cache: dict[str, str] = {}
        self._pending: set[str] = set()
        self._queue: deque[str] = deque()
        self._stop_requested = False
        self._worker: threading.Thread | None = None
        self._llm = None

        if not (runtime_enabled and self.enabled and provider and model):
            return

        llm_kwargs: dict[str, Any] = {}
        provider_lower = provider.lower()
        if provider_lower == "google":
            llm_kwargs["thinking_level"] = google_thinking_level or "minimal"
        elif provider_lower == "openai":
            llm_kwargs["reasoning_effort"] = openai_reasoning_effort or "low"
        elif provider_lower == "anthropic":
            llm_kwargs["effort"] = anthropic_effort or "low"

        try:
            self._llm = create_llm_client(
                provider=provider_lower,
                model=model,
                base_url=base_url,
                **llm_kwargs,
            ).get_llm()
        except Exception:
            self._llm = None
            return

        self._worker = threading.Thread(
            target=self._translation_worker,
            name="dashboard-display-translator",
            daemon=True,
        )
        self._worker.start()

    def close(self) -> None:
        worker = self._worker
        if worker is None:
            return

        with self._condition:
            self._stop_requested = True
            self._condition.notify_all()

        worker.join(timeout=1.0)
        self._worker = None

    def queue_snapshot(self, snapshot: dict[str, Any]) -> None:
        if not (self.enabled and self._llm):
            return

        texts = self._collect_translatable_texts(snapshot)
        if not texts:
            return

        with self._condition:
            for text in texts:
                if text in self._cache or text in self._pending:
                    continue
                self._pending.add(text)
                self._queue.append(text)
            self._condition.notify_all()

    def localize_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return snapshot

        with self._lock:
            cache = dict(self._cache)

        def transform(value: Any, parent_key: str | None = None) -> Any:
            if isinstance(value, dict):
                return {
                    key: transform(item, key)
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [transform(item, parent_key) for item in value]
            if isinstance(value, str):
                if parent_key == "decision":
                    return self._localize_decision(value)
                if parent_key in self.TRANSLATABLE_KEYS and value.strip():
                    return cache.get(value, value)
            return value

        return transform(deepcopy(snapshot))

    def _collect_translatable_texts(self, snapshot: dict[str, Any]) -> list[str]:
        texts: list[str] = []

        def walk(value: Any, parent_key: str | None = None) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    walk(item, key)
                return
            if isinstance(value, list):
                for item in value:
                    walk(item, parent_key)
                return
            if isinstance(value, str) and parent_key in self.TRANSLATABLE_KEYS:
                stripped = value.strip()
                if stripped:
                    texts.append(stripped)

        walk(snapshot)
        return list(dict.fromkeys(texts))

    def _localize_decision(self, decision: str) -> str:
        normalized = decision.strip().upper()
        return self.DECISION_TRANSLATIONS.get(normalized, decision)

    def _translation_worker(self) -> None:
        while True:
            batch: list[str] = []
            with self._condition:
                while not self._queue and not self._stop_requested:
                    self._condition.wait(timeout=0.5)
                if self._stop_requested and not self._queue:
                    return

                total_chars = 0
                while self._queue and len(batch) < 3:
                    candidate = self._queue.popleft()
                    if candidate in batch:
                        continue
                    if total_chars and total_chars + len(candidate) > 9000:
                        self._queue.appendleft(candidate)
                        break
                    batch.append(candidate)
                    total_chars += len(candidate)

            translations = self._translate_batch(batch)

            with self._condition:
                for original in batch:
                    self._cache[original] = translations.get(original, original)
                    self._pending.discard(original)

    def _translate_batch(self, texts: list[str]) -> dict[str, str]:
        if not texts or not self._llm:
            return {text: text for text in texts}

        items = [
            {"id": str(index), "text": text}
            for index, text in enumerate(texts)
        ]
        prompt = (
            "You are a precise translation engine. "
            f"Translate every item's text into {self.output_language}. "
            "Keep Markdown structure, headings, bullet lists, tables, inline code, code fences, "
            "stock tickers, numbers, dates, and names intact where appropriate. "
            "Do not summarize. Do not add commentary. "
            f"If text is already in {self.output_language}, keep it unchanged. "
            "Return strict JSON array with keys id and translation only.\n\n"
            f"Items:\n{json.dumps(items, ensure_ascii=False)}"
        )

        try:
            response = self._llm.invoke(prompt)
            payload = self._extract_json_payload(getattr(response, "content", response))
            if isinstance(payload, list):
                by_id = {
                    str(item.get("id")): str(item.get("translation"))
                    for item in payload
                    if isinstance(item, dict)
                    and item.get("id") is not None
                    and item.get("translation") is not None
                }
                if len(by_id) == len(items):
                    return {
                        text: by_id[str(index)]
                        for index, text in enumerate(texts)
                    }
        except Exception:
            pass

        return {text: self._translate_single(text) for text in texts}

    def _translate_single(self, text: str) -> str:
        if not self._llm or not text.strip():
            return text

        prompt = (
            f"Translate the following text into {self.output_language}. "
            "Keep Markdown structure, headings, tables, inline code, code fences, "
            "stock tickers, numbers, dates, and names intact where appropriate. "
            "Do not summarize. Do not add commentary. "
            f"If the text is already in {self.output_language}, keep it unchanged.\n\n"
            f"{text}"
        )

        try:
            response = self._llm.invoke(prompt)
            translated = getattr(response, "content", response)
            return str(translated).strip() or text
        except Exception:
            return text

    @staticmethod
    def _extract_json_payload(raw: Any) -> Any:
        content = str(raw).strip()
        if not content:
            return None

        for candidate in (content, DisplayTranslator._strip_code_fence(content)):
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def _strip_code_fence(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return stripped
