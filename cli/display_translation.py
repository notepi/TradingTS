from __future__ import annotations

import re
import threading
from copy import deepcopy
from typing import Any

from cli.translation_cache import TranslationCache
from tradingagents.llm_clients import create_llm_client


class DisplayTranslator:
    TRANSLATABLE_KEYS = {"current_report", "final_report", "error"}
    DECISION_TRANSLATIONS = {
        "BUY": "买入",
        "OVERWEIGHT": "增持",
        "HOLD": "持有",
        "UNDERWEIGHT": "减持",
        "SELL": "卖出",
    }
    HEADING_TRANSLATIONS = {
        "Research Manager Decision": "研究经理决策",
        "Bull Researcher Analysis": "多头研究员分析",
        "Bear Researcher Analysis": "空头研究员分析",
        "Aggressive Analyst Analysis": "激进分析师分析",
        "Conservative Analyst Analysis": "保守分析师分析",
        "Neutral Analyst Analysis": "中立分析师分析",
        "Recommendation": "建议",
        "Rationale": "理由",
        "Summary of the Debate": "辩论摘要",
        "Your Recommendation": "你的建议",
        "Executive Summary": "执行摘要",
        "Rating": "评级",
        "Analyst Team Reports": "分析师团队报告",
        "Research Team Decision": "研究团队决策",
        "Trading Team Plan": "交易团队计划",
        "Portfolio Management Decision": "投资组合管理决策",
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
        self._base_url = base_url
        self._llm_kwargs: dict[str, Any] = {}
        self._inflight: set[str] = set()
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

    def translate_text(self, text: str, *, force: bool = False) -> str:
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
        translated = self._translate_single(stripped)
        with self._lock:
            self._cache[stripped] = translated
        self._persistent_cache.set(stripped, translated)
        return translated

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
        """将整篇翻译结果加入缓存，供后续 localize_snapshot 使用。

        用于 materialize_translated_run 完成后，将翻译结果加载到内存缓存，
        避免 localize_snapshot 在运行期间触发额外的翻译调用。
        """
        if not self.enabled:
            return
        stripped = original.strip()
        translated_stripped = translated.strip()
        with self._lock:
            self._cache[stripped] = translated_stripped
        self._persistent_cache.set(stripped, translated_stripped)

    def queue_snapshot(self, snapshot: dict[str, Any]) -> None:
        if not self.enabled:
            return

        texts = self._collect_translatable_texts(snapshot)
        if not texts:
            return

        uncached: list[str] = []
        with self._lock:
            for text in texts:
                if text in self._cache or text in self._inflight:
                    continue
                persistent = self._persistent_cache.get(text)
                if persistent is not None:
                    self._cache[text] = persistent
                    continue
                self._inflight.add(text)
                uncached.append(text)

        for text in uncached:
            translated = self._translate_single(text)
            with self._lock:
                self._cache[text] = translated
                self._inflight.discard(text)
            self._persistent_cache.set(text, translated)

    def localize_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return snapshot

        with self._lock:
            cache = dict(self._cache)

        def transform(value: Any, parent_key: str | None = None) -> Any:
            if isinstance(value, dict):
                if self._should_translate_content_dict(value):
                    translated_dict = {
                        key: transform(item, key)
                        for key, item in value.items()
                    }
                    content = translated_dict.get("content")
                    if isinstance(content, str) and content.strip():
                        translated_dict["content"] = cache.get(content, content)
                    return translated_dict
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
                if self._should_translate_content_dict(value):
                    content = value.get("content")
                    if isinstance(content, str):
                        stripped = content.strip()
                        if stripped:
                            texts.append(stripped)
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

    def _should_translate_content_dict(self, value: dict[str, Any]) -> bool:
        content = value.get("content")
        if not isinstance(content, str) or not content.strip():
            return False

        event_type = str(value.get("type") or "").strip().lower()
        label = str(value.get("label") or "").strip().lower()

        if event_type == "report":
            return True

        if event_type == "message" and label == "agent":
            return True

        return False

    def _localize_decision(self, decision: str) -> str:
        normalized = decision.strip().upper()
        return self.DECISION_TRANSLATIONS.get(normalized, decision)

    def _translate_single(self, text: str) -> str:
        llm = self._ensure_llm()
        if not llm or not text.strip():
            return text
        parts = self._split_markdown_content(text)
        translated_parts: list[str] = []
        for part_type, part_text in parts:
            if part_type == "code":
                translated_parts.append(part_text)
                continue
            translated_parts.append(self._translate_plain_segment(llm, part_text))
        return "".join(translated_parts) or text

    def _translate_plain_segment(self, llm: Any, text: str) -> str:
        if not text.strip():
            return text

        text = self._translate_known_headings(text)
        translated_lines: list[str] = []
        for line in text.splitlines(keepends=True):
            translated_lines.append(self._translate_plain_line(llm, line))
        return "".join(translated_lines)

    def _translate_document_single(self, text: str) -> str:
        llm = self._ensure_llm()
        if not llm or not text.strip():
            return text
        prompt = (
            f"Translate the following Markdown document into {self.output_language}. "
            "Keep Markdown headings, lists, tables, stock tickers, numbers, dates, "
            "and code fences intact where appropriate. Preserve structure. "
            "Do not summarize. Do not add commentary. "
            f"If the text is already in {self.output_language}, keep it unchanged.\n\n"
            f"{text}"
        )
        try:
            response = llm.invoke(prompt)
            translated = getattr(response, "content", response)
            translated_text = str(translated).strip() or text
            with self._lock:
                self._last_error = None
        except Exception as exc:
            with self._lock:
                self._last_error = f"Document translation failed: {exc}"
            return text

        if self._translation_still_looks_english(text, translated_text):
            retry_prompt = (
                f"Translate all natural-language prose in the following Markdown document into "
                f"{self.output_language}. Keep Markdown syntax, stock tickers, numbers, dates, "
                "and code blocks unchanged. Output only the translated Markdown document.\n\n"
                f"{text}"
            )
            try:
                response = llm.invoke(retry_prompt)
                retried = getattr(response, "content", response)
                retried_text = str(retried).strip() or translated_text
                translated_text = retried_text
                with self._lock:
                    self._last_error = None
            except Exception as exc:
                with self._lock:
                    self._last_error = f"Document translation retry failed: {exc}"
                pass
        return translated_text

    def _translate_plain_line(self, llm: Any, line: str) -> str:
        stripped = line.strip()
        if not stripped:
            return line
        if stripped.startswith("#"):
            return line
        if stripped.startswith("|") and stripped.endswith("|"):
            return line

        sanitized_line, inline_tokens = self._protect_inline_code(line)
        prompt = (
            f"Translate the following text into {self.output_language}. "
            "Keep Markdown structure, stock tickers, numbers, dates, names, "
            "and punctuation intact where appropriate. "
            "Tokens like INLINE_CODE_0 must remain unchanged. "
            "Do not summarize. Do not add commentary. "
            f"If the text is already in {self.output_language}, keep it unchanged.\n\n"
            f"{sanitized_line}"
        )

        try:
            response = llm.invoke(prompt)
            translated = getattr(response, "content", response)
            translated_text = str(translated).strip() or sanitized_line.strip()
            restored = self._restore_inline_code(translated_text, inline_tokens)
            with self._lock:
                self._last_error = None
            return restored + ("\n" if line.endswith("\n") else "")
        except Exception as exc:
            with self._lock:
                self._last_error = f"Line translation failed: {exc}"
            return line

    def _translate_known_headings(self, text: str) -> str:
        translated = text
        for english, chinese in self.HEADING_TRANSLATIONS.items():
            translated = re.sub(
                rf"(?m)^(#{1,6}\s+){re.escape(english)}(\s*)$",
                rf"\1{chinese}\2",
                translated,
            )
            translated = re.sub(
                rf"(?m)^(\*\*){re.escape(english)}(\*\*:)",
                rf"\1{chinese}\2",
                translated,
            )
            translated = re.sub(
                rf"(?m)^({re.escape(english)}:)",
                chinese + ":",
                translated,
            )
        return translated

    def _translation_still_looks_english(self, original: str, translated: str) -> bool:
        if self.output_language.lower() != "chinese":
            return False
        if translated.strip() == original.strip():
            return True
        return bool(re.search(r"[A-Za-z]{20,}", translated)) and not bool(
            re.search(r"[\u4e00-\u9fff]", translated)
        )

    @staticmethod
    def _split_markdown_content(text: str) -> list[tuple[str, str]]:
        fence_pattern = re.compile(r"```[\s\S]*?```", re.MULTILINE)
        parts: list[tuple[str, str]] = []
        cursor = 0
        for match in fence_pattern.finditer(text):
            if match.start() > cursor:
                parts.append(("text", text[cursor:match.start()]))
            parts.append(("code", match.group(0)))
            cursor = match.end()
        if cursor < len(text):
            parts.append(("text", text[cursor:]))
        return parts or [("text", text)]

    @staticmethod
    def _protect_inline_code(text: str) -> tuple[str, list[str]]:
        tokens: list[str] = []

        def repl(match: re.Match[str]) -> str:
            index = len(tokens)
            tokens.append(match.group(0))
            return f"INLINE_CODE_{index}"

        return re.sub(r"`[^`\n]+`", repl, text), tokens

    @staticmethod
    def _restore_inline_code(text: str, tokens: list[str]) -> str:
        restored = text
        for index, token in enumerate(tokens):
            restored = restored.replace(f"INLINE_CODE_{index}", token)
        return restored

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
            self._llm = None
        return self._llm
