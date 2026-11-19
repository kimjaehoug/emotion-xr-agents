import { useState, type ReactNode } from "react";
import { AppStateProvider } from "./context/AppStateContext";
import { DashboardTab } from "./tabs/DashboardTab";
import { StateReportSimulatorTab } from "./tabs/StateReportSimulatorTab";
import { PromptPreviewTab } from "./tabs/PromptPreviewTab";
import { ActionPlanViewerTab } from "./tabs/ActionPlanViewerTab";
import { PolicyManagerTab } from "./tabs/PolicyManagerTab";
import { ActionCatalogTab } from "./tabs/ActionCatalogTab";
import { ContentCatalogTab } from "./tabs/ContentCatalogTab";
import { MockXrRuntimeTab } from "./tabs/MockXrRuntimeTab";
import { MemoryViewerTab } from "./tabs/MemoryViewerTab";
import { LlmSettingsTab } from "./tabs/LlmSettingsTab";

interface TabDef {
  id: string;
  label: string;
  render: () => ReactNode;
}

const TABS: TabDef[] = [
  { id: "dashboard", label: "대시보드", render: () => <DashboardTab /> },
  { id: "simulator", label: "State Report 시뮬레이터", render: () => <StateReportSimulatorTab /> },
  { id: "prompt", label: "프롬프트 미리보기", render: () => <PromptPreviewTab /> },
  { id: "plan", label: "Action Plan 뷰어", render: () => <ActionPlanViewerTab /> },
  { id: "policy", label: "정책 관리", render: () => <PolicyManagerTab /> },
  { id: "actions", label: "행동 카탈로그", render: () => <ActionCatalogTab /> },
  { id: "contents", label: "콘텐츠 카탈로그", render: () => <ContentCatalogTab /> },
  { id: "xr-runtime", label: "모의 XR 런타임", render: () => <MockXrRuntimeTab /> },
  { id: "memory", label: "메모리 뷰어", render: () => <MemoryViewerTab /> },
  { id: "llm-settings", label: "LLM 설정", render: () => <LlmSettingsTab /> },
];

function AppShell() {
  const [activeTab, setActiveTab] = useState(TABS[0].id);
  const active = TABS.find((t) => t.id === activeTab) ?? TABS[0];

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-teal-600">Research PoC</p>
            <h1 className="text-lg font-semibold text-slate-900">XR Control Agent 관리 콘솔</h1>
          </div>
          <div className="text-right text-xs text-slate-400">
            <p>backend: http://127.0.0.1:8001</p>
            <p>frontend: :5174</p>
          </div>
        </div>
      </header>

      <nav className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl overflow-x-auto px-6">
          <div className="flex gap-1">
            {TABS.map((tab) => {
              const isActive = tab.id === activeTab;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`whitespace-nowrap border-b-2 px-3 py-3 text-sm font-medium transition-colors duration-150 ${
                    isActive
                      ? "border-teal-600 text-teal-700"
                      : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-6 py-6">{active.render()}</main>

      <footer className="mx-auto max-w-7xl px-6 py-6 text-center text-xs text-slate-400">
        XR Control Agent PoC · 연구용 관리 콘솔 · 실제 서비스 배포에는 사용하지 마세요.
      </footer>
    </div>
  );
}

function App() {
  return (
    <AppStateProvider>
      <AppShell />
    </AppStateProvider>
  );
}

export default App;
