from __future__ import annotations

from pathlib import Path

from web.translation.display_translation import DisplayTranslator


TRANSLATABLE_RUN_FILES = (
    "reports/market_report.md",
    "reports/sentiment_report.md",
    "reports/news_report.md",
    "reports/fundamentals_report.md",
    "reports/investment_plan.md",
    "reports/trader_investment_plan.md",
    "reports/final_trade_decision.md",
    "1_analysts/market.md",
    "1_analysts/sentiment.md",
    "1_analysts/news.md",
    "1_analysts/fundamentals.md",
    "2_research/bull.md",
    "2_research/bear.md",
    "2_research/peter_lynch.md",
    "2_research/manager.md",
    "3_trading/trader.md",
    "4_risk/aggressive.md",
    "4_risk/conservative.md",
    "4_risk/neutral.md",
    "5_portfolio/decision.md",
    "complete_report.md",
)


def translated_root(run_dir: str | Path, language: str) -> Path:
    return Path(run_dir) / "translated" / language


def translated_path(run_dir: str | Path, language: str, relative_path: str | Path) -> Path:
    return translated_root(run_dir, language) / Path(relative_path)


def load_translated_text(
    run_dir: str | Path,
    language: str | None,
    relative_path: str | Path,
) -> str | None:
    if not language or language.strip().lower() == "english":
        return None
    path = translated_path(run_dir, language, relative_path)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def materialize_translated_run(
    run_dir: str | Path,
    language: str,
    translator: DisplayTranslator,
    *,
    force_refresh: bool = False,
) -> list[Path]:
    if not translator.enabled:
        return []

    root = Path(run_dir)
    written: list[Path] = []
    for relative in TRANSLATABLE_RUN_FILES:
        source = root / relative
        if not source.exists():
            continue
        original_text = source.read_text(encoding="utf-8")
        translated_text = translator.translate_document(
            original_text,
            force=force_refresh,
        )
        # 将整篇结果写入缓存，避免后续重复翻译同一份文档
        translator.cache_document(original_text, translated_text)
        target = translated_path(root, language, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(translated_text, encoding="utf-8")
        written.append(target)
    return written