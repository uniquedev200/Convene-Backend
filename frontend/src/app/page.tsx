"use client";

import React, { useState, useEffect } from "react";
import { api, Preset, DebateSummary, DebateResult, getAuthHeaders } from "@/services/api";
import { useDebateStream } from "@/hooks/useDebateStream";
import { supabase } from "@/lib/supabaseClient";
import { Configurator } from "@/components/debate/Configurator";
import { LiveStream } from "@/components/debate/LiveStream";
import { ArtifactsPanel } from "@/components/debate/ArtifactsPanel";
import { LoginPanel } from "@/components/debate/LoginPanel";
import { SettingsPanel } from "@/components/debate/SettingsPanel";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Terminal,
  Layers,
  Clock,
  PlusCircle,
  HelpCircle,
  LogOut,
  Sparkles,
  GitBranch,
  Shield,
  Activity,
  History,
  AlertTriangle,
  X,
  Menu,
  Settings
} from "lucide-react";
import { BouncingBallsBackground } from "@/components/debate/BouncingBallsBackground";

const APP_VERSION = "2.1";

export default function Home() {
  const [activeView, setActiveView] = useState<"config" | "live" | "history" | "login" | "settings">("config");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [presets, setPresets] = useState<Preset[]>([]);
  const [historyList, setHistoryList] = useState<DebateSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  
  // Active debate states
  const [activeDebateId, setActiveDebateId] = useState<string | null>(null);
  const [activePresetId, setActivePresetId] = useState<string>("developer");
  const [activeQuestion, setActiveQuestion] = useState<string>("");
  const [activeOptions, setActiveOptions] = useState<string[]>([]);
  const [isStarting, setIsStarting] = useState<boolean>(false);

  // Loaded result for historic debates
  const [selectedResult, setSelectedResult] = useState<DebateResult | null>(null);
  const [selectedResultLoading, setSelectedResultLoading] = useState<boolean>(false);
  const [selectedResultError, setSelectedResultError] = useState<string | null>(null);

  // SSE Stream integration
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      // 1. Initial theme load
      const savedTheme = localStorage.getItem("convene_theme") as "dark" | "light";
      if (savedTheme) {
        setTheme(savedTheme);
      }

      // 2. Check local token if any
      const localToken = localStorage.getItem("convene_token");
      if (localToken) {
        setToken(localToken);
      }

      // 3. Listen to Supabase auth events
      const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
        if (session) {
          try {
            const data = await api.exchangeOAuthToken(session.access_token);
            localStorage.setItem("convene_token", data.access_token);
            localStorage.setItem("convene_user_id", data.user_id);
            localStorage.setItem("convene_email", session.user.email ?? "user@supabase.com");
            setToken(data.access_token);
            loadHistory();
          } catch (err) {
            console.error("Token exchange failed:", err);
          }
        }
      });

      return () => {
        subscription.unsubscribe();
      };
    }
  }, []);

  const handleToggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    if (typeof window !== "undefined") {
      localStorage.setItem("convene_theme", next);
    }
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      const root = window.document.documentElement;
      root.classList.remove("light", "dark");
      root.classList.add(theme);
    }
  }, [theme]);

  const stream = useDebateStream({
    debateId: activeDebateId,
    token,
    onComplete: (res) => {
      // Refresh history list once debate completes
      loadHistory();
      // Fetch full result details to render visual artifacts
      fetchCompletedResult(activeDebateId!);
    },
    onError: (err) => {
      setIsStarting(false);
    }
  });

  // Fetch presets on mount
  useEffect(() => {
    async function loadInitialData() {
      try {
        const presetData = await api.getPresets();
        setPresets(presetData);
      } catch (err) {
        console.error("Failed to load initial presets", err);
      }
      loadHistory();
    }
    loadInitialData();
  }, []);

  const loadHistory = async () => {
    const isLoggedIn = localStorage.getItem("convene_token");
    if (!isLoggedIn) return;
    
    setHistoryLoading(true);
    try {
      const list = await api.getMyDebates();
      setHistoryList(list);
    } catch (err) {
      console.error("Failed to load debates history", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const fetchCompletedResult = async (id: string) => {
    setSelectedResultLoading(true);
    setSelectedResultError(null);
    try {
      if (id === "demo-simulation") {
        setSelectedResult({
          debate_id: "demo-simulation",
          preset_id: "developer",
          question: "Should we use Postgres or MongoDB for our new core analytics pipeline?",
          options: ["Postgres", "MongoDB"],
          status: "complete",
          created_at: new Date().toISOString(),
          agent_stances: [
            { agent_name: "Architect", option: "Postgres", score: 9.0, reasoning: "Schema safety, ACID compliance, and predictable relational queries are standard requirements." },
            { agent_name: "ProductDX", option: "MongoDB", score: 9.0, reasoning: "Rapid development, flexible JSON documents, and easy API integration." },
            { agent_name: "Security", option: "Postgres", score: 8.0, reasoning: "MongoDB's flexible schema increases application validation bugs and input injection risks." },
            { agent_name: "Performance", option: "Postgres", score: 7.0, reasoning: "Postgres tables with indexing will handle our analytics read-queries more efficiently." }
          ],
          cross_exam_transcript: [
            {
              from_agent: "Architect",
              to_agent: "ProductDX",
              challenge: "Relational schema enforcement is non-negotiable for accounting data consistency. MongoDB's schema-less model will push validation logic into application code, increasing developer cognitive load and risking data corruption.",
              response: "While constraints are nice, our SaaS events schema is evolving weekly as we add new client metrics. MongoDB lets us store polymorphic event blobs instantly without heavy schema migrations."
            },
            {
              from_agent: "Security",
              to_agent: "ProductDX",
              challenge: "Accepting raw polymorphic documents into MongoDB without strict typing bypasses traditional access controls and invites query-injection vulnerabilities. How will you secure this schema-less setup?",
              response: "We will implement strict document-validation schemas directly in MongoDB using JSON Schema, coupled with standard object-document mapping (ODM) sanitation layers in Node.js."
            },
            {
              from_agent: "Performance",
              to_agent: "Architect",
              challenge: "Postgres excels at complex analytical queries, but under write-heavy telemetry workloads (10,000 writes/sec), index write amplification and WAL serialization bottlenecks will spike CPU limits.",
              response: "For scaling write loads, we can configure table partitioning based on event timestamps, allowing us to detach historic tables easily."
            }
          ],
          consensus: {
            winner: "Postgres",
            agreement_percentage: 75,
            reasoning: "While MongoDB offers agility for telemetry events, Postgres is selected due to strict validation needs for accounting data, partition support, and lower long-term risk. ProductDX has agreed to store event blobs inside Postgres JSONB columns to compromise.",
            trade_offs: [
              "Agility vs validation safety: JSONB inside Postgres offers a middle ground.",
              "Write amplification: Requires custom partition strategies by timestamp."
            ],
            suggested_implementation: "CREATE TABLE analytics_logs (\n  id SERIAL PRIMARY KEY,\n  event_type VARCHAR(100),\n  payload JSONB\n) PARTITION BY RANGE (created_at);"
          },
          user_id: null
        });
        return;
      }

      const data = await api.getDebateResult(id);
      setSelectedResult(data);
    } catch (err: any) {
      setSelectedResultError(err.message || "Failed to load result");
    } finally {
      setSelectedResultLoading(false);
    }
  };

  const handleStartDebate = async (config: {
    preset_id: string;
    question: string;
    options: string[];
    constraints: {
      team_size: number;
      timeline: string;
      budget?: string;
    };
    isAnonymous: boolean;
  }) => {
    setIsStarting(true);
    setSelectedResult(null);
    try {
      if (config.question === "demo-simulation") {
        setActivePresetId(config.preset_id);
        setActiveQuestion("Should we use Postgres or MongoDB for our new core analytics pipeline?");
        setActiveOptions(["Postgres", "MongoDB"]);
        setActiveDebateId("demo-simulation");
        setActiveView("live");
        return;
      }

      const data = await api.createDebate({
        preset_id: config.preset_id,
        question: config.question,
        options: config.options,
        constraints: config.constraints
      });
      
      setActivePresetId(config.preset_id);
      setActiveQuestion(config.question);
      setActiveOptions(config.options);
      setActiveDebateId(data.debate_id);
      setActiveView("live");
    } catch (err: any) {
      alert("Failed to initialize debate: " + err.message);
    } finally {
      setIsStarting(false);
    }
  };

  const handleSelectHistoryDebate = async (debateId: string, questionText: string, optionsText: string[]) => {
    setActiveView("live");
    setActiveDebateId(null); // Clear SSE stream connection
    setActiveQuestion(questionText);
    setActiveOptions(optionsText);
    fetchCompletedResult(debateId);
  };

  const getActivePersonas = () => {
    const preset = presets.find(p => p.preset_id === activePresetId);
    if (preset && preset.personas) {
      return preset.personas.map((p: any) => (typeof p === "string" ? p : p.agent_name));
    }
    return ["Architect", "Security", "Performance", "ProductDX"];
  };

  return (
    <div className={`flex h-screen bg-background overflow-hidden relative ${theme}`}>
      <BouncingBallsBackground />
      {/* Sidebar navigation */}
      {isSidebarOpen && (
        <aside className="w-72 bg-sidebar border-r border-border-color flex flex-col justify-between hidden md:flex z-20 animate-in slide-in-from-left duration-200">
        <div className="flex flex-col flex-1 overflow-y-auto">
          {/* Logo */}
          <div className="p-6 border-b border-border-color flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-accent pulse-accent" />
              <h1 className="text-lg font-black tracking-wider text-primary-text uppercase">Convene</h1>
            </div>
            <button
              type="button"
              onClick={() => setIsSidebarOpen(false)}
              className="p-1 hover:bg-accent-muted rounded transition-colors text-secondary-text hover:text-primary-text cursor-pointer"
              title="Close Sidebar"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Quick Menu */}
          <nav className="p-4 space-y-1">
            <Button
              variant={activeView === "config" ? "primary" : "ghost"}
              onClick={() => {
                setActiveView("config");
                setActiveDebateId(null);
                setSelectedResult(null);
              }}
              className="w-full justify-start gap-2 h-9 text-xs"
            >
              <PlusCircle className="h-4 w-4" />
              New Board
            </Button>
            <Button
              variant={activeView === "history" ? "secondary" : "ghost"}
              onClick={() => {
                setActiveView("history");
                loadHistory();
              }}
              className="w-full justify-start gap-2 h-9 text-xs"
            >
              <History className="h-4 w-4" />
              Debates History
            </Button>
            <Button
              variant={activeView === "settings" ? "secondary" : "ghost"}
              onClick={() => {
                setActiveView("settings");
              }}
              className="w-full justify-start gap-2 h-9 text-xs"
            >
              <Settings className="h-4 w-4" />
              Settings
            </Button>
            
            {token ? (
              <Button
                variant="ghost"
                onClick={async () => {
                  localStorage.removeItem("convene_token");
                  localStorage.removeItem("convene_email");
                  await supabase.auth.signOut();
                  setToken(null);
                  setHistoryList([]);
                  setActiveView("config");
                }}
                className="w-full justify-start gap-2 h-9 text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-950/20"
              >
                <LogOut className="h-4 w-4 text-rose-400" />
                Log Out
              </Button>
            ) : (
              <Button
                variant={activeView === "login" ? "secondary" : "ghost"}
                onClick={() => {
                  setActiveView("login");
                }}
                className="w-full justify-start gap-2 h-9 text-xs"
              >
                <Shield className="h-4 w-4" />
                Sign In
              </Button>
            )}
          </nav>

          {/* Sidebar Historic Debates list */}
          <div className="p-4 flex-1 flex flex-col min-h-0">
            <div className="flex items-center gap-1.5 px-2 mb-3">
              <Clock className="h-3.5 w-3.5 text-secondary-text" />
              <span className="text-[10px] uppercase font-bold text-secondary-text tracking-wider">Recent Runs</span>
            </div>
            
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {historyLoading ? (
                <div className="text-center py-6 text-neutral-600 text-xs">Syncing workspace logs...</div>
              ) : historyList.length === 0 ? (
                <div className="text-center py-8 text-neutral-600 text-xs border border-dashed border-border-color rounded-custom p-4">
                  No active logs. Start a debate to populate index.
                </div>
              ) : (
                historyList.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => handleSelectHistoryDebate(item.id, item.question, [/* options parsed in details */])}
                    className="p-3 bg-card-bg border border-border-color hover:border-accent rounded-custom cursor-pointer transition-all space-y-1"
                  >
                    <p className="text-xs text-primary-text font-semibold line-clamp-1">{item.question}</p>
                    <div className="flex items-center justify-between text-[10px] text-secondary-text font-mono">
                      <span className="capitalize">{item.preset_id}</span>
                      <span className="text-accent">{item.status}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="p-4 border-t border-border-color text-center bg-sidebar">
          <span className="text-[10px] font-mono text-neutral-600">Convene Engine v{APP_VERSION}</span>
        </div>
      </aside>
      )}

      {/* Main workspace viewport */}
      <main className="flex-1 flex flex-col overflow-hidden relative z-10 bg-background">
        {/* Navigation Top Header */}
        <header className="h-16 border-b border-border-color flex items-center justify-between px-6 bg-card-bg">
          <div className="flex items-center gap-4">
            {!isSidebarOpen && (
              <button
                type="button"
                onClick={() => setIsSidebarOpen(true)}
                className="p-1.5 hover:bg-accent-muted rounded transition-all text-secondary-text hover:text-primary-text cursor-pointer mr-2 flex items-center justify-center"
                title="Open Sidebar"
              >
                <Menu className="h-5 w-5" />
              </button>
            )}
            <h2 className="text-sm font-extrabold uppercase tracking-widest text-primary-text hidden md:block">
              {activeView === "config" && "Dashboard Workspace"}
              {activeView === "live" && "War Room Command Console"}
              {activeView === "history" && "Workspace Logs Index"}
              {activeView === "login" && "Workspace Access Control"}
              {activeView === "settings" && "Workspace Configuration Settings"}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveView("settings")}
              className={`p-1.5 rounded transition-all text-secondary-text hover:text-white cursor-pointer hover:bg-accent-muted ${
                activeView === "settings" ? "text-accent bg-accent-muted animate-spin-once" : ""
              }`}
              title="Settings"
            >
              <Settings className="h-4.5 w-4.5" />
            </button>
            <span className="text-[10px] font-mono bg-background border border-border-color px-2.5 py-1 rounded-full text-secondary-text uppercase">
              {token ? "Enterprise Auth" : "Anonymous Guest"}
            </span>
          </div>
        </header>

        {/* Dynamic content area */}
        <div className="flex-1 overflow-y-auto bg-background">
          {activeView === "config" && (
            <div className="py-6">
              <Configurator onStartDebate={handleStartDebate} isStarting={isStarting} />
            </div>
          )}

          {activeView === "live" && (
            <div className="py-6 space-y-6">
              {/* SSE stream live traces */}
              {activeDebateId && (
                <LiveStream
                  status={stream.status}
                  agentStances={stream.agentStances}
                  toolCalls={stream.toolCalls}
                  crossExamTranscript={stream.crossExamTranscript}
                  activeAgent={stream.activeAgent}
                  personas={getActivePersonas()}
                  question={activeQuestion}
                />
              )}

              {/* Render Artifacts panel for either streaming consensus or selected history result */}
              {selectedResultLoading ? (
                <div className="flex flex-col h-96 items-center justify-center space-y-4">
                  <div className="w-8 h-8 rounded-full border-4 border-accent border-t-transparent animate-spin" />
                  <p className="text-xs text-secondary-text">Compiling multi-agent report artifacts...</p>
                </div>
              ) : selectedResultError ? (
                <div className="max-w-2xl mx-auto p-6 bg-red-950/20 border border-red-900 rounded-custom flex items-start gap-4">
                  <AlertTriangle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
                  <div>
                    <h4 className="text-sm font-bold text-red-400">Report Generation Interrupted</h4>
                    <p className="text-xs text-neutral-400 mt-1">{selectedResultError}</p>
                    <Button variant="outline" size="sm" className="mt-3 text-xs" onClick={() => fetchCompletedResult(activeDebateId || selectedResult?.debate_id || "")}>
                      Retry Compilation
                    </Button>
                  </div>
                </div>
              ) : selectedResult ? (
                <ArtifactsPanel result={selectedResult} />
              ) : null}
            </div>
          )}

          {activeView === "history" && (
            <div className="max-w-5xl mx-auto p-6 space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-bold text-primary-text">Historical Run Indexes</h3>
                  <p className="text-xs text-secondary-text mt-1">Review past consensus reports generated in this workspace.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {historyList.map((item) => (
                  <Card
                    key={item.id}
                    onClick={() => handleSelectHistoryDebate(item.id, item.question, [])}
                    className="border-border-color bg-card-bg hover:border-neutral-500 cursor-pointer transition-all"
                  >
                    <CardHeader className="p-4 pb-2">
                      <div className="flex items-center justify-between text-[10px] text-neutral-500 font-mono">
                        <span>ID: {item.id}</span>
                        <span className="capitalize px-2 py-0.5 bg-[#1A1A1A] border border-[#2B2B2B] rounded-full">
                          {item.preset_id}
                        </span>
                      </div>
                      <CardTitle className="text-sm font-bold text-primary-text mt-2 leading-relaxed">
                        {item.question}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 pt-0 flex justify-between items-center text-xs">
                      <span className="text-neutral-600">Created: {new Date(item.created_at).toLocaleDateString()}</span>
                      <span className="text-accent font-bold uppercase tracking-wider">{item.status}</span>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {activeView === "login" && (
            <div className="py-12">
              <LoginPanel
                onSuccess={(jwt) => {
                  setToken(jwt);
                  loadHistory();
                  setActiveView("config");
                }}
                onCancel={() => {
                  setActiveView("config");
                }}
              />
            </div>
          )}

          {activeView === "settings" && (
            <div className="py-12">
              <SettingsPanel
                theme={theme}
                onToggleTheme={handleToggleTheme}
                onCancel={() => {
                  setActiveView("config");
                }}
                onClearHistory={() => {
                  localStorage.removeItem("convene_token");
                  localStorage.removeItem("convene_theme");
                  localStorage.removeItem("convene_api_base");
                  setToken(null);
                  setHistoryList([]);
                  setTheme("dark");
                  setActiveView("config");
                }}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
