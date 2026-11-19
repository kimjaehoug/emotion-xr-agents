import { Card } from "../components/common/Card";
import { EmptyState } from "../components/common/EmptyState";
import { JsonBlock } from "../components/common/JsonBlock";
import { useAppState } from "../context/AppStateContext";

const CANDIDATE_FIELDS = ["prompt_preview", "sanitized_prompt", "system_prompt", "user_prompt"] as const;

export function PromptPreviewTab() {
  const { lastPlan } = useAppState();

  const preview = lastPlan
    ? CANDIDATE_FIELDS.map((field) => ({
        field,
        value: (lastPlan as unknown as Record<string, unknown>)[field],
      })).find((entry) => typeof entry.value === "string" && entry.value.length > 0)
    : undefined;

  return (
    <div className="flex flex-col gap-6">
      <Card
        title="정제된(Sanitized) 프롬프트 미리보기"
        description="마지막 Plan 응답에서 프롬프트 관련 필드를 탐색합니다."
      >
        {!lastPlan && (
          <EmptyState>
            아직 생성된 계획이 없습니다. "State Report 시뮬레이터" 탭에서 Plan을 먼저 생성하세요.
          </EmptyState>
        )}

        {lastPlan && preview && (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-slate-500">
              감지된 필드: <span className="mono">{preview.field}</span>
            </p>
            <JsonBlock value={preview.value} />
          </div>
        )}

        {lastPlan && !preview && (
          <div className="space-y-3">
            <EmptyState>
              현재 백엔드의 <span className="mono">PlanResponse</span>에는 sanitized prompt를 노출하는 필드(
              <span className="mono">prompt_preview</span> 등)가 포함되어 있지 않습니다.
              <br />
              (참고: <span className="mono">app/core/config.py</span>의{" "}
              <span className="mono">llm_store_sanitized_prompts</span> 설정이 있지만, API 응답 스키마(
              <span className="mono">PlanResponse</span>)에는 아직 반영되지 않았습니다.)
            </EmptyState>
            <p className="text-xs text-slate-400">
              백엔드가 이 필드를 추가하면 이 탭이 자동으로 감지하여 표시합니다. 그 전까지는 마지막 계획의 원본
              응답을 참고용으로 표시합니다.
            </p>
            <JsonBlock value={lastPlan} />
          </div>
        )}
      </Card>
    </div>
  );
}
