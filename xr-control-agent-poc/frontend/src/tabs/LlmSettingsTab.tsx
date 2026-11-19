import { useCallback, useEffect, useState } from "react";
import { ApiError, getLlmHealth, testLlm } from "../api/client";
import { Card } from "../components/common/Card";
import { Button } from "../components/common/Button";
import { Badge } from "../components/common/Badge";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorNotice } from "../components/common/ErrorNotice";
import { JsonBlock } from "../components/common/JsonBlock";
import type { LLMHealthResponse, TestLLMResponse } from "../api/types";

const DEFAULT_USER_PROMPT =
  "사용자는 시각 복잡도가 높은 콘텐츠를 26분간 이용 중이며 심박수와 동공 확장이 상승했습니다. " +
  "인지 부담을 줄이기 위한 XR Control 계획을 JSON으로 제안하세요.";

export function LlmSettingsTab() {
  const [health, setHealth] = useState<LLMHealthResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(false);
  const [healthError, setHealthError] = useState<{ message: string; detail?: string } | null>(null);

  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState(DEFAULT_USER_PROMPT);
  const [testResult, setTestResult] = useState<TestLLMResponse | null>(null);
  const [testing, setTesting] = useState(false);
  const [testError, setTestError] = useState<{ message: string; detail?: string } | null>(null);

  const loadHealth = useCallback(async () => {
    setLoadingHealth(true);
    setHealthError(null);
    try {
      const result = await getLlmHealth();
      setHealth(result);
    } catch (err) {
      const apiErr = err as ApiError;
      setHealthError({ message: apiErr.message ?? "LLM 헬스체크 실패", detail: apiErr.detail });
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  useEffect(() => {
    void loadHealth();
  }, [loadHealth]);

  const handleTest = async () => {
    if (!userPrompt.trim()) return;
    setTesting(true);
    setTestError(null);
    try {
      const result = await testLlm({
        user_prompt: userPrompt,
        system_prompt: systemPrompt.trim() ? systemPrompt : undefined,
      });
      setTestResult(result);
    } catch (err) {
      const apiErr = err as ApiError;
      setTestError({ message: apiErr.message ?? "LLM 테스트 호출 실패", detail: apiErr.detail });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card
        title="로컬 LLM 설정"
        description="GET /api/v1/xr-agent/health/llm"
        actions={
          <Button variant="ghost" onClick={() => void loadHealth()} loading={loadingHealth}>
            새로고침
          </Button>
        }
      >
        {healthError && <ErrorNotice message={healthError.message} detail={healthError.detail} />}

        {health ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-md border border-slate-100 p-3">
              <p className="text-xs text-slate-400">연결 상태</p>
              <Badge tone={health.reachable ? "emerald" : "rose"}>
                {health.reachable ? "정상 연결" : "연결 불가"}
              </Badge>
            </div>
            <div className="rounded-md border border-slate-100 p-3">
              <p className="text-xs text-slate-400">base_url</p>
              <p className="mono truncate text-sm text-slate-700" title={health.base_url}>
                {health.base_url}
              </p>
            </div>
            <div className="rounded-md border border-slate-100 p-3">
              <p className="text-xs text-slate-400">model</p>
              <p className="mono truncate text-sm text-slate-700" title={health.model}>
                {health.model}
              </p>
            </div>
            {health.detail && (
              <div className="sm:col-span-3">
                <p className="text-xs text-slate-500">{health.detail}</p>
              </div>
            )}
          </div>
        ) : (
          <EmptyState>{loadingHealth ? "로딩 중..." : "LLM 상태 정보를 불러오지 못했습니다."}</EmptyState>
        )}
      </Card>

      <Card title="LLM 직접 테스트" description="POST /api/v1/xr-agent/test-llm">
        <div className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">
              system_prompt (선택, 비워두면 기본 시스템 프롬프트 사용)
            </label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="비워두면 build_system_prompt() 기본값이 사용됩니다."
              className="mono h-20 w-full resize-y rounded-md border border-slate-300 bg-slate-50 p-2 text-xs focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">user_prompt</label>
            <textarea
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              className="mono h-28 w-full resize-y rounded-md border border-slate-300 bg-slate-50 p-2 text-xs focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
            />
          </div>
          <div>
            <Button variant="primary" onClick={() => void handleTest()} loading={testing}>
              LLM 호출 테스트
            </Button>
          </div>
        </div>

        {testError && <ErrorNotice message={testError.message} detail={testError.detail} />}

        {testResult && (
          <div className="mt-4 flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Badge tone={testResult.parse_error ? "rose" : "emerald"}>
                {testResult.parse_error ? "JSON 파싱 실패" : "JSON 파싱 성공"}
              </Badge>
            </div>
            <div>
              <p className="mb-1 text-xs font-medium text-slate-500">raw_output</p>
              <JsonBlock value={testResult.raw_output} maxHeight="14rem" />
            </div>
            {testResult.parsed && (
              <div>
                <p className="mb-1 text-xs font-medium text-slate-500">parsed</p>
                <JsonBlock value={testResult.parsed} maxHeight="14rem" />
              </div>
            )}
            {testResult.parse_error && (
              <p className="text-xs text-rose-600">parse_error: {testResult.parse_error}</p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
