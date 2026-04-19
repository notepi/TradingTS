from __future__ import annotations

import re
import threading
from copy import deepcopy
from typing import Any

from web.translation.translation_cache import TranslationCache
from tradingagents.llm_clients import create_llm_client


class DisplayTranslator:
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
        cache_dir: str | None = None,
        runtime_enabled: bool = True,
    ) -> None:
        self.output_language = output_language.strip() or "English"
        self.enabled = self.output_language.lower() != "english"
        self._lock = threading.RLock()
        self._cache: dict[str, str] = {}
        self._llm = None
        self._last_error: str | None = None
        self._provider = provider.lower() if provider else None
        self._model = model
        self._stats = {
            "translation_calls": 0,
            "translation_tokens_in": 0,
            "translation_tokens_out": 0,
            "translation_documents": 0,
            "translation_failures": 0,
            "enabled": self.enabled,
            "language": self.output_language,
            "provider": self._provider,
            "model": self._model,
        }
        self._base_url = base_url
        self._llm_kwargs: dict[str, Any] = {}
        self._persistent_cache = TranslationCache(cache_dir, self.output_language)
        self._cache.update(self._persistent_cache.all())

        if not (runtime_enabled and self.enabled and provider and model):
            return

        if self._provider == "google":
            self._llm_kwargs["thinking_level"] = google_thinking_level or "minimal"
        elif self._provider == "openai":
            self._llm_kwargs["reasoning_effort"] = openai_reasoning_effort or "low"
        elif self._provider == "anthropic":
            self._llm_kwargs["effort"] = anthropic_effort or "low"

    def close(self) -> None:
        return

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            stats = dict(self._stats)
            stats["provider"] = self._provider
            stats["model"] = self._model
            stats["language"] = self.output_language
            stats["enabled"] = self.enabled
            return stats

    def translate_document(self, text: str, *, force: bool = False) -> str:
        if not self.enabled or not text.strip():
            return text
        stripped = text.strip()
        if not force:
            with self._lock:
                cached = self._cache.get(stripped)
            if cached is not None:
                return cached
            persistent = self._persistent_cache.get(stripped)
            if persistent is not None:
                with self._lock:
                    self._cache[stripped] = persistent
                return persistent
        translated = self._translate_document_single(stripped)
        with self._lock:
            self._cache[stripped] = translated
        self._persistent_cache.set(stripped, translated)
        return translated

    def cache_document(self, original: str, translated: str) -> None:
        """将整篇翻译结果写入缓存，供后续文档复用。"""
        if not self.enabled:
            return
        stripped = original.strip()
        translated_stripped = translated.strip()
        with self._lock:
            self._cache[stripped] = translated_stripped
        self._persistent_cache.set(stripped, translated_stripped)

    def localize_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return snapshot

        localized = deepcopy(snapshot)
        decision = localized.get("decision")
        if isinstance(decision, str) and decision.strip():
            localized["decision"] = self._localize_decision(decision)
        return localized

    def _localize_decision(self, decision: str) -> str:
        normalized = decision.strip().upper()
        return self.DECISION_TRANSLATIONS.get(normalized, decision)

    def _translate_document_single(self, text: str) -> str:
        llm = self._ensure_llm()
        if not llm or not text.strip():
            return text
        with self._lock:
            self._stats["translation_documents"] += 1
        prompt = (
            f"Translate the following Markdown document into {self.output_language}. "
            "Keep Markdown headings, lists, tables, stock tickers, numbers, dates, "
            "and code fences intact where appropriate. Preserve structure. "
            "Do not summarize. Do not add commentary. "
            "IMPORTANT: This is a Chinese stock market report. "
            "Currency symbols ¥ and abbreviations CNY refer to Chinese Yuan (人民币), NOT Japanese Yen (日元). "
            "When translating to Chinese, use '元' or '人民币', never '日元'. "
            f"If the text is already in {self.output_language}, keep it unchanged.\n\n"
            f"{text}"
        )
        try:
            response = llm.invoke(prompt)
            translated, usage = self._extract_content_and_usage(response)
            self._record_usage(usage)
            translated_text = str(translated).strip() or text
            with self._lock:
                self._last_error = None
        except Exception as exc:
            with self._lock:
                self._last_error = f"Document translation failed: {exc}"
                self._stats["translation_failures"] += 1
            return text

        if self._translation_still_looks_english(text, translated_text):
            retry_prompt = (
                f"Translate all natural-language prose in the following Markdown document into "
                f"{self.output_language}. Keep Markdown syntax, stock tickers, numbers, dates, "
                "and code blocks unchanged. "
                "IMPORTANT: This is a Chinese stock market report. "
                "Currency symbols ¥ and abbreviations CNY refer to Chinese Yuan (人民币), NOT Japanese Yen (日元). "
                "When translating to Chinese, use '元' or '人民币', never '日元'. "
                "Output only the translated Markdown document.\n\n"
                f"{text}"
            )
            try:
                response = llm.invoke(retry_prompt)
                retried, usage = self._extract_content_and_usage(response)
                self._record_usage(usage)
                retried_text = str(retried).strip() or translated_text
                translated_text = retried_text
                with self._lock:
                    self._last_error = None
            except Exception as exc:
                with self._lock:
                    self._last_error = f"Document translation retry failed: {exc}"
                    self._stats["translation_failures"] += 1
        return translated_text

    def _translation_still_looks_english(self, original: str, translated: str) -> bool:
        if self.output_language.lower() != "chinese":
            return False
        if translated.strip() == original.strip():
            return True
        return bool(re.search(r"[A-Za-z]{20,}", translated)) and not bool(
            re.search(r"[\u4e00-\u9fff]", translated)
        )

    def _ensure_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        if not (self._provider and self._model):
            return None
        try:
            self._llm = create_llm_client(
                provider=self._provider,
                model=self._model,
                base_url=self._base_url,
                **self._llm_kwargs,
            ).get_llm()
            with self._lock:
                self._last_error = None
        except Exception as exc:
            with self._lock:
                self._last_error = f"Translator client init failed: {exc}"
                self._stats["translation_failures"] += 1
            self._llm = None
        return self._llm

    def _record_usage(self, usage: dict[str, Any] | None) -> None:
        with self._lock:
            self._stats["translation_calls"] += 1
            if usage:
                self._stats["translation_tokens_in"] += int(usage.get("input_tokens", 0) or 0)
                self._stats["translation_tokens_out"] += int(usage.get("output_tokens", 0) or 0)

    @staticmethod
    def _extract_content_and_usage(response: Any) -> tuple[Any, dict[str, Any] | None]:
        usage = getattr(response, "usage_metadata", None)
        if usage is None and hasattr(response, "message"):
            usage = getattr(response.message, "usage_metadata", None)
        content = getattr(response, "content", response)
        return content, usage