"use client";

import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { DashboardOptions, Selections } from "@/lib/types";

interface SidebarProps {
  options: DashboardOptions | null;
  selections: Selections | null;
  onStart: (payload: unknown) => void;
  onStop: () => void;
  onReset: () => void;
  isRunning: boolean;
  isStopping: boolean;
}

export function Sidebar({
  options,
  selections,
  onStart,
  onStop,
  onReset,
  isRunning,
  isStopping,
}: SidebarProps) {
  const [ticker, setTicker] = useState("600519.SH");
  const [analysisDate, setAnalysisDate] = useState("");
  const [researchDepth, setResearchDepth] = useState(3);
  const [provider, setProvider] = useState("openai");
  const [quickModel, setQuickModel] = useState("");
  const [deepModel, setDeepModel] = useState("");
  const [outputLanguage, setOutputLanguage] = useState("Chinese");
  const [selectedAnalysts, setSelectedAnalysts] = useState<Set<string>>(
    new Set(["market", "social", "news", "fundamentals"])
  );
  const [googleThinking, setGoogleThinking] = useState("");
  const [openaiEffort, setOpenaiEffort] = useState("");
  const [anthropicEffort, setAnthropicEffort] = useState("");

  useEffect(() => {
    if (options?.defaults) {
      setTicker(options.defaults.ticker);
      setAnalysisDate(options.defaults.analysis_date);
      setResearchDepth(options.defaults.research_depth);
      setProvider(options.defaults.llm_provider);
      setOutputLanguage(options.defaults.output_language);
      setSelectedAnalysts(new Set(options.defaults.analysts));
      setGoogleThinking(options.defaults.google_thinking_level || "");
      setOpenaiEffort(options.defaults.openai_reasoning_effort || "");
      setAnthropicEffort(options.defaults.anthropic_effort || "");
    }
  }, [options]);

  useEffect(() => {
    if (options?.models[provider]) {
      const quickOpts = options.models[provider].quick;
      const deepOpts = options.models[provider].deep;
      if (quickOpts.length > 0 && !quickOpts.find(([, v]) => v === quickModel)) {
        setQuickModel(quickOpts[0][1]);
      }
      if (deepOpts.length > 0 && !deepOpts.find(([, v]) => v === deepModel)) {
        setDeepModel(deepOpts[0][1]);
      }
    }
  }, [provider, options, quickModel, deepModel]);

  const handleAnalystToggle = (analyst: string, checked: boolean) => {
    const newSet = new Set(selectedAnalysts);
    if (checked) {
      newSet.add(analyst);
    } else {
      newSet.delete(analyst);
    }
    setSelectedAnalysts(newSet);
  };

  const handleSubmit = () => {
    const payload: Record<string, unknown> = {
      ticker,
      analysis_date: analysisDate,
      research_depth: researchDepth,
      llm_provider: provider,
      quick_think_llm: quickModel,
      deep_think_llm: deepModel,
      output_language: outputLanguage,
      analysts: Array.from(selectedAnalysts),
    };

    if (provider === "google" && googleThinking) {
      payload.google_thinking_level = googleThinking;
    }
    if (provider === "openai" && openaiEffort) {
      payload.openai_reasoning_effort = openaiEffort;
    }
    if (provider === "anthropic" && anthropicEffort) {
      payload.anthropic_effort = anthropicEffort;
    }

    onStart(payload);
  };

  if (!options) {
    return (
      <aside className="w-64 border-r border-border bg-card p-4">
        <div className="text-muted-foreground text-sm">Loading options...</div>
      </aside>
    );
  }

  return (
    <aside className="w-64 border-r border-border bg-card p-4 flex flex-col gap-4 overflow-y-auto">
      <div className="space-y-1.5">
        <Label htmlFor="ticker" className="text-xs text-muted-foreground uppercase tracking-wider">
          A股代码
        </Label>
        <Input
          id="ticker"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="600519.SH"
          disabled={isRunning || isStopping}
          className="h-8 text-sm font-mono"
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1.5">
          <Label htmlFor="analysis-date" className="text-xs text-muted-foreground uppercase tracking-wider">
            分析日期
          </Label>
          <Input
            id="analysis-date"
            type="date"
            value={analysisDate}
            onChange={(e) => setAnalysisDate(e.target.value)}
            disabled={isRunning || isStopping}
            className="h-8 text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="research-depth" className="text-xs text-muted-foreground uppercase tracking-wider">
            研究深度
          </Label>
          <Select
            value={String(researchDepth)}
            onValueChange={(v) => setResearchDepth(Number(v))}
            disabled={isRunning || isStopping}
          >
            <SelectTrigger id="research-depth" className="h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.research_depths.map((rd) => (
                <SelectItem key={rd.value} value={String(rd.value)}>
                  {rd.label} ({rd.value})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="provider" className="text-xs text-muted-foreground uppercase tracking-wider">
          LLM Provider
        </Label>
        <Select value={provider} onValueChange={(v) => v && setProvider(v)} disabled={isRunning || isStopping}>
          <SelectTrigger id="provider" className="h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {options.providers.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1.5">
          <Label htmlFor="quick-model" className="text-xs text-muted-foreground uppercase tracking-wider">
            Quick Model
          </Label>
          <Select value={quickModel} onValueChange={(v) => v && setQuickModel(v)} disabled={isRunning || isStopping}>
            <SelectTrigger id="quick-model" className="h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.models[provider]?.quick.map(([label, value]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="deep-model" className="text-xs text-muted-foreground uppercase tracking-wider">
            Deep Model
          </Label>
          <Select value={deepModel} onValueChange={(v) => v && setDeepModel(v)} disabled={isRunning || isStopping}>
            <SelectTrigger id="deep-model" className="h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.models[provider]?.deep.map(([label, value]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="output-language" className="text-xs text-muted-foreground uppercase tracking-wider">
          输出语言
        </Label>
        <Select value={outputLanguage} onValueChange={(v) => v && setOutputLanguage(v)} disabled={isRunning || isStopping}>
          <SelectTrigger id="output-language" className="h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {options.languages.map((lang) => (
              <SelectItem key={lang} value={lang}>
                {lang}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {provider === "google" && (
        <div className="space-y-1.5">
          <Label htmlFor="google-thinking" className="text-xs text-muted-foreground uppercase tracking-wider">
            Gemini Thinking
          </Label>
          <Select value={googleThinking} onValueChange={(v) => setGoogleThinking(v || "")} disabled={isRunning || isStopping}>
            <SelectTrigger id="google-thinking" className="h-8 text-sm">
              <SelectValue placeholder="Default" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">Default</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="minimal">Minimal</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {provider === "openai" && (
        <div className="space-y-1.5">
          <Label htmlFor="openai-effort" className="text-xs text-muted-foreground uppercase tracking-wider">
            OpenAI Effort
          </Label>
          <Select value={openaiEffort} onValueChange={(v) => setOpenaiEffort(v || "")} disabled={isRunning || isStopping}>
            <SelectTrigger id="openai-effort" className="h-8 text-sm">
              <SelectValue placeholder="Default" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">Default</SelectItem>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="high">High</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {provider === "anthropic" && (
        <div className="space-y-1.5">
          <Label htmlFor="anthropic-effort" className="text-xs text-muted-foreground uppercase tracking-wider">
            Claude Effort
          </Label>
          <Select value={anthropicEffort} onValueChange={(v) => setAnthropicEffort(v || "")} disabled={isRunning || isStopping}>
            <SelectTrigger id="anthropic-effort" className="h-8 text-sm">
              <SelectValue placeholder="Default" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">Default</SelectItem>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="high">High</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="space-y-2">
        <Label className="text-xs text-muted-foreground uppercase tracking-wider">
          Analyst Team
        </Label>
        <div className="grid grid-cols-2 gap-1.5">
          {options.analysts.map((analyst) => (
            <div key={analyst.value} className="flex items-center gap-1.5">
              <Checkbox
                id={`analyst-${analyst.value}`}
                checked={selectedAnalysts.has(analyst.value)}
                onCheckedChange={(checked) =>
                  handleAnalystToggle(analyst.value, Boolean(checked))
                }
                disabled={isRunning || isStopping}
                className="h-3.5 w-3.5"
              />
              <Label
                htmlFor={`analyst-${analyst.value}`}
                className="text-xs cursor-pointer leading-none"
              >
                {analyst.label}
              </Label>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-2 mt-auto pt-2">
        <Button
          onClick={isRunning ? onStop : handleSubmit}
          disabled={isStopping || (!isRunning && selectedAnalysts.size === 0)}
          variant={isRunning ? "secondary" : "default"}
          className="flex-1 h-9 text-sm font-medium"
        >
          {isRunning ? "停止分析" : isStopping ? "停止中..." : "开始分析"}
        </Button>
        <Button
          onClick={onReset}
          disabled={isRunning || isStopping}
          variant="outline"
          className="h-9 text-sm"
        >
          重置
        </Button>
      </div>
    </aside>
  );
}
