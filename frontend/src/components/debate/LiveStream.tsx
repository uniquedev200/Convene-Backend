import React, { useEffect, useRef } from "react";
import { AgentStance, CrossExamMessage, ToolCall } from "@/services/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { motion, AnimatePresence } from "framer-motion";
import {
  Terminal as TerminalIcon,
  Shield,
  Cpu,
  Layers,
  GraduationCap,
  Briefcase,
  Search,
  FlaskConical,
  TrendingUp,
  Award,
  DollarSign,
  Megaphone,
  User,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Code
} from "lucide-react";

interface LiveStreamProps {
  status: string;
  agentStances: AgentStance[];
  toolCalls: ToolCall[];
  crossExamTranscript: CrossExamMessage[];
  activeAgent: string | null;
  personas: any[];
  question: string;
}

export function LiveStream({
  status,
  agentStances,
  toolCalls,
  crossExamTranscript,
  activeAgent,
  personas,
  question
}: LiveStreamProps) {
  const terminalEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [crossExamTranscript, toolCalls]);

  // Helper to get agent icon
  const getAgentIcon = (nameInput: any) => {
    const name = typeof nameInput === "string" ? nameInput : (nameInput?.agent_name || "");
    const n = name.toLowerCase();
    if (n.includes("architect")) return <Layers className="h-5 w-5 text-neutral-300" />;
    if (n.includes("security")) return <Shield className="h-5 w-5 text-neutral-300" />;
    if (n.includes("performance") || n.includes("ops")) return <Cpu className="h-5 w-5 text-neutral-300" />;
    if (n.includes("product") || n.includes("dx")) return <Code className="h-5 w-5 text-neutral-300" />;
    if (n.includes("professor")) return <GraduationCap className="h-5 w-5 text-neutral-300" />;
    if (n.includes("industry") || n.includes("engineer")) return <TerminalIcon className="h-5 w-5 text-neutral-300" />;
    if (n.includes("recruiter")) return <Search className="h-5 w-5 text-neutral-300" />;
    if (n.includes("research") || n.includes("scientist")) return <FlaskConical className="h-5 w-5 text-neutral-300" />;
    if (n.includes("investor")) return <TrendingUp className="h-5 w-5 text-neutral-300" />;
    if (n.includes("founder")) return <Award className="h-5 w-5 text-neutral-300" />;
    if (n.includes("marketing")) return <Megaphone className="h-5 w-5 text-neutral-300" />;
    if (n.includes("finance")) return <DollarSign className="h-5 w-5 text-neutral-300" />;
    return <User className="h-5 w-5 text-neutral-300" />;
  };

  // Helper to check if agent is thinking/running
  const isAgentThinking = (nameInput: any) => {
    const name = typeof nameInput === "string" ? nameInput : (nameInput?.agent_name || "");
    if (status === "analyzing") {
      // If agent has not submitted stance yet and is either active or no active agent is set yet
      const hasStance = agentStances.some(s => s.agent_name === name);
      const cleanActive = typeof activeAgent === "string" ? activeAgent : (activeAgent as any)?.agent_name || activeAgent;
      return !hasStance && (cleanActive === name || !cleanActive);
    }
    return false;
  };

  // Get stances for a specific agent
  const getAgentStanceList = (nameInput: any) => {
    const name = typeof nameInput === "string" ? nameInput : (nameInput?.agent_name || "");
    return agentStances.filter(s => s.agent_name === name);
  };

  // Timeline phases
  const phases = [
    { id: "analyzing", label: "Initial Analysis" },
    { id: "cross_examining", label: "Cross-Examination" },
    { id: "consensus", label: "Moderator Consensus" }
  ];

  const getPhaseIndex = () => {
    if (status === "analyzing" || status === "pending") return 0;
    if (status === "cross_examining") return 1;
    if (status === "consensus" || status === "complete") return 2;
    return -1;
  };

  const currentPhaseIdx = getPhaseIndex();

  return (
    <div className="space-y-6 w-full max-w-5xl mx-auto p-4">
      {/* State Indicator Hub */}
      <Card className="border-border-color bg-card-bg p-4">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex-1">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-secondary-text">Debate Focus</h3>
            <p className="text-md font-bold text-primary-text mt-1">{question || "Active Session Query"}</p>
          </div>
          <div className="flex items-center gap-2">
            {phases.map((p, idx) => {
              const isPast = idx < currentPhaseIdx;
              const isCurrent = idx === currentPhaseIdx;
              return (
                <React.Fragment key={p.id}>
                  {idx > 0 && <div className={`w-6 h-[2px] ${isPast || isCurrent ? "bg-accent" : "bg-[#3A3A3A]"}`} />}
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold transition-all ${
                        isPast
                          ? "bg-accent text-black"
                          : isCurrent
                          ? "bg-accent text-black pulse-accent"
                          : "bg-[#2F2F2F] border border-border-color text-secondary-text"
                      }`}
                    >
                      {isPast ? "✓" : idx + 1}
                    </div>
                    <span
                      className={`text-xs font-semibold hidden md:inline ${
                        isCurrent ? "text-accent font-bold" : isPast ? "text-primary-text" : "text-secondary-text"
                      }`}
                    >
                      {p.label}
                    </span>
                  </div>
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </Card>

      {/* Main War Room Content */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left 2 Columns: Persona Grid & Console */}
        <div className="md:col-span-2 space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {personas.map((personaName) => {
              const stances = getAgentStanceList(personaName);
              const thinking = isAgentThinking(personaName);
              const hasStance = stances.length > 0;

              // Calculate min and max scores for this agent
              const scores = stances.map(st => st.score);
              const maxScore = scores.length > 0 ? Math.max(...scores) : 0;
              const minScore = scores.length > 0 ? Math.min(...scores) : 0;

              return (
                <Card
                  key={personaName}
                  className={`border-border-color bg-card-bg overflow-hidden flex flex-col justify-between transition-all ${
                    thinking ? "ring-2 ring-accent bg-accent/[0.02]" : ""
                  }`}
                >
                  <CardHeader className="pb-3 flex flex-row items-center justify-between border-b border-[#3A3A3A] bg-[#2A2A2A]/40 p-4">
                    <div className="flex items-center gap-2">
                      {getAgentIcon(personaName)}
                      <CardTitle className="text-sm font-bold text-primary-text">{personaName}</CardTitle>
                    </div>
                    {thinking && (
                      <span className="flex h-2 w-2 relative">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
                      </span>
                    )}
                  </CardHeader>
                  <CardContent className="p-4 flex-1 flex flex-col justify-between min-h-48">
                    <AnimatePresence mode="wait">
                      {thinking ? (
                        <motion.div
                          key="thinking"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="flex-1 flex flex-col justify-center items-center py-6 text-center space-y-3"
                        >
                          <div className="flex space-x-1 justify-center items-center">
                            <div className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                            <div className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                            <div className="w-2 h-2 bg-accent rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                          </div>
                          <span className="text-xs font-medium text-secondary-text">Running local MCP tools & analyzing tradeoffs...</span>
                        </motion.div>
                      ) : hasStance ? (
                        <motion.div
                          key="stance"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          className="space-y-4 flex-1 flex flex-col justify-between"
                        >
                          {stances.map((s, idx) => {
                            const isWinner = s.score === maxScore && maxScore > minScore;
                            const isLoser = s.score === minScore && maxScore > minScore;
                            const badgeClass = isWinner
                              ? "text-xs font-extrabold text-emerald-400 bg-emerald-950/30 px-2 py-0.5 rounded-full border border-emerald-500/30 font-mono"
                              : isLoser
                              ? "text-xs font-extrabold text-rose-400 bg-rose-950/30 px-2 py-0.5 rounded-full border border-rose-500/30 font-mono"
                              : "text-xs font-extrabold text-accent bg-accent-muted px-2 py-0.5 rounded-full border border-accent/20 font-mono";

                            return (
                              <div key={idx} className="space-y-3">
                                <div className="flex items-center justify-between bg-[#262626] p-2 rounded-custom border border-border-color">
                                  <span className="text-xs text-secondary-text">Proposed Choice:</span>
                                  <span className="text-xs font-bold text-primary-text">{s.option}</span>
                                  <span className={badgeClass}>
                                    {s.score}/10
                                  </span>
                                </div>
                                <p className="text-xs leading-relaxed text-secondary-text line-clamp-4">{s.reasoning}</p>

                                {/* Tool calls drawer inside the card */}
                                {s.tool_calls_used && s.tool_calls_used.length > 0 && (
                                  <div className="mt-3 border-t border-[#3A3A3A] pt-3">
                                    <span className="text-[10px] uppercase font-bold text-secondary-text block mb-1">Tools Evaluated:</span>
                                    <div className="space-y-1.5 max-h-24 overflow-y-auto pr-1">
                                      {s.tool_calls_used.map((tool, tIdx) => (
                                        <div key={tIdx} className="bg-[#1A1A1A] p-1.5 rounded border border-[#2F2F2F] text-[10px]">
                                          <div className="flex items-center justify-between text-accent font-semibold">
                                            <span>{tool.tool_name}</span>
                                          </div>
                                          <p className="text-neutral-500 truncate mt-0.5">{tool.query}</p>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </motion.div>
                      ) : (
                        <div className="flex-1 flex items-center justify-center text-center text-neutral-600 text-xs py-8">
                          Waiting in queue...
                        </div>
                      )}
                    </AnimatePresence>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Active Live Tool Calls Console (Global trace) */}
          <Card className="border-border-color bg-card-bg">
            <CardHeader className="py-3 bg-[#262626] border-b border-border-color flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-bold text-primary-text flex items-center gap-2">
                <TerminalIcon className="h-4 w-4 text-accent" />
                MCP Server Console Logs
              </CardTitle>
              <span className="text-[10px] text-secondary-text font-mono bg-[#1C1C1C] px-2 py-0.5 rounded-full">
                {toolCalls.length} logs
              </span>
            </CardHeader>
            <CardContent className="p-0">
              <div className="bg-[#1A1A1A] font-mono text-xs p-4 h-48 overflow-y-auto space-y-3 rounded-b-custom">
                {toolCalls.length === 0 ? (
                  <p className="text-neutral-600 italic">No tool transactions logged yet. Waiting for analysis phase...</p>
                ) : (
                  toolCalls.map((tc, idx) => (
                    <div key={idx} className="space-y-1 border-b border-[#2A2A2A] pb-2 last:border-0 last:pb-0">
                      <div className="flex items-center gap-2">
                        <span className="text-accent font-bold">➔ [{tc.tool_name}]</span>
                        <span className="text-neutral-400 text-[10px] truncate">{tc.query}</span>
                      </div>
                      <p className="text-neutral-500 pl-4 leading-relaxed text-[11px]">{tc.result_summary}</p>
                    </div>
                  ))
                )}
                <div ref={terminalEndRef} />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Cross-Examination Visual Duel */}
        <div className="space-y-6">
          <Card className="border-border-color bg-card-bg h-[600px] flex flex-col justify-start">
            <CardHeader className="py-4 bg-[#262626] border-b border-border-color">
              <CardTitle className="text-sm font-bold flex items-center justify-between">
                <span>Visual Duel Log</span>
                {status === "cross_examining" && (
                  <span className="text-[10px] bg-neutral-800 border border-neutral-700 text-neutral-300 px-2 py-0.5 rounded-full animate-pulse">
                    Active Cross-Exam
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 flex-1 overflow-y-auto min-h-0">
              <div className="space-y-4">
                {crossExamTranscript.length === 0 ? (
                  <div className="flex flex-col items-center justify-center text-center py-20 space-y-2 text-neutral-600">
                    <HelpCircle className="h-8 w-8 text-neutral-700" />
                    <p className="text-xs">Visual duel triggers after initial stances are locked in.</p>
                  </div>
                ) : (
                  crossExamTranscript.map((msg, idx) => (
                    <div key={idx} className="space-y-2">
                      {/* Thread Node line */}
                      <div className="flex items-center gap-1.5 text-[10px] text-accent font-mono uppercase tracking-wider">
                        <span>Duel Thread #{idx + 1}</span>
                        <span className="text-[#3A3A3A]">|</span>
                        <span>{msg.from_agent} vs {msg.to_agent}</span>
                      </div>
                      
                      {/* Split Side-by-side terminal duel */}
                      <div className="grid grid-cols-1 gap-2">
                        {/* Challenger terminal */}
                        <div className="bg-[#1C1C1C] border border-border-color rounded-custom p-3 font-mono text-[11px]">
                          <span className="text-white font-extrabold block mb-1">⚡ CHALLENGE [{msg.from_agent}]:</span>
                          <p className="text-neutral-300 leading-relaxed">&ldquo;{msg.challenge}&rdquo;</p>
                        </div>
                        {/* Responder terminal */}
                        <div className="bg-[#1C1C1C] border border-border-color rounded-custom p-3 font-mono text-[11px]">
                          <span className="text-neutral-400 font-bold block mb-1">➔ RESPONSE [{msg.to_agent}]:</span>
                          <p className="text-neutral-300 leading-relaxed">&ldquo;{msg.response}&rdquo;</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
