import { useState, useEffect, useRef } from "react";
import { API_BASE, DebateResult, AgentStance, CrossExamMessage, ToolCall, ConsensusResult } from "@/services/api";

export interface UseDebateStreamOptions {
  debateId: string | null;
  token: string | null;
  onComplete?: (result: DebateResult) => void;
  onError?: (err: string) => void;
}

export function useDebateStream({ debateId, token, onComplete, onError }: UseDebateStreamOptions) {
  const [status, setStatus] = useState<string>("pending");
  const [agentStances, setAgentStances] = useState<AgentStance[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [crossExamTranscript, setCrossExamTranscript] = useState<CrossExamMessage[]>([]);
  const [consensus, setConsensus] = useState<ConsensusResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!debateId) {
      // Reset state if debateId is null
      setStatus("pending");
      setAgentStances([]);
      setToolCalls([]);
      setCrossExamTranscript([]);
      setConsensus(null);
      setError(null);
      setActiveAgent(null);
      return;
    }

    if (debateId === "demo-simulation") {
      setStatus("analyzing");
      setAgentStances([]);
      setToolCalls([]);
      setCrossExamTranscript([]);
      setConsensus(null);
      setError(null);

      let step = 0;
      const interval = setInterval(() => {
        step++;
        if (step === 1) {
          setAgentStances((prev) => [
            ...prev,
            { agent_name: "Architect", option: "Postgres", score: 9.0, reasoning: "Schema safety, ACID compliance, and predictable relational queries are standard requirements." }
          ]);
          setActiveAgent("Architect");
        } else if (step === 2) {
          setAgentStances((prev) => [
            ...prev,
            { agent_name: "ProductDX", option: "MongoDB", score: 9.0, reasoning: "Rapid development, flexible JSON documents, and easy API integration." }
          ]);
          setActiveAgent("ProductDX");
        } else if (step === 3) {
          setAgentStances((prev) => [
            ...prev,
            { agent_name: "Security", option: "Postgres", score: 8.0, reasoning: "MongoDB's flexible schema increases application validation bugs and input injection risks." }
          ]);
          setActiveAgent("Security");
        } else if (step === 4) {
          setAgentStances((prev) => [
            ...prev,
            { agent_name: "Performance", option: "Postgres", score: 7.0, reasoning: "Postgres tables with indexing will handle our analytics read-queries more efficiently." }
          ]);
          setActiveAgent("Performance");
        } else if (step === 5) {
          setToolCalls((prev) => [
            ...prev,
            { tool_name: "Database Analyzer", query: "pg_stat_statements check", result_summary: "Found low read overhead but high write index amplification on partition indexes." }
          ]);
        } else if (step === 6) {
          setStatus("cross_examining");
          setActiveAgent(null);
          setCrossExamTranscript((prev) => [
            ...prev,
            {
              from_agent: "Architect",
              to_agent: "ProductDX",
              challenge: "Relational schema enforcement is non-negotiable for accounting data consistency. MongoDB's schema-less model will push validation logic into application code, increasing developer cognitive load and risking data corruption.",
              response: "While constraints are nice, our SaaS events schema is evolving weekly as we add new client metrics. MongoDB lets us store polymorphic event blobs instantly without heavy schema migrations."
            }
          ]);
        } else if (step === 7) {
          setCrossExamTranscript((prev) => [
            ...prev,
            {
              from_agent: "Security",
              to_agent: "ProductDX",
              challenge: "Accepting raw polymorphic documents into MongoDB without strict typing bypasses traditional access controls and invites query-injection vulnerabilities. How will you secure this schema-less setup?",
              response: "We will implement strict document-validation schemas directly in MongoDB using JSON Schema, coupled with standard object-document mapping (ODM) sanitation layers in Node.js."
            }
          ]);
        } else if (step === 8) {
          setCrossExamTranscript((prev) => [
            ...prev,
            {
              from_agent: "Performance",
              to_agent: "Architect",
              challenge: "Postgres excels at complex analytical queries, but under write-heavy telemetry workloads (10,000 writes/sec), index write amplification and WAL serialization bottlenecks will spike CPU limits.",
              response: "For scaling write loads, we can configure table partitioning based on event timestamps, allowing us to detach historic tables easily."
            }
          ]);
        } else if (step === 9) {
          const consensusResult = {
            winner: "Postgres",
            agreement_percentage: 75,
            reasoning: "While MongoDB offers agility for telemetry events, Postgres is selected due to strict validation needs for accounting data, partition support, and lower long-term risk. ProductDX has agreed to store event blobs inside Postgres JSONB columns to compromise.",
            trade_offs: [
              "Agility vs validation safety: JSONB inside Postgres offers a middle ground.",
              "Write amplification: Requires custom partition strategies by timestamp."
            ],
            suggested_implementation: "CREATE TABLE analytics_logs (\n  id SERIAL PRIMARY KEY,\n  event_type VARCHAR(100),\n  payload JSONB\n) PARTITION BY RANGE (created_at);"
          };
          setConsensus(consensusResult);
          setStatus("complete");
          clearInterval(interval);
          if (onComplete) {
            onComplete({
              debate_id: "demo-simulation",
              preset_id: "developer",
              question: "Should we use Postgres or MongoDB for our new core analytics pipeline?",
              options: ["Postgres", "MongoDB"],
              status: "complete",
              created_at: new Date().toISOString(),
              agent_stances: [
                { agent_name: "Architect", option: "Postgres", score: 9.0, reasoning: "" },
                { agent_name: "ProductDX", option: "MongoDB", score: 9.0, reasoning: "" },
                { agent_name: "Security", option: "Postgres", score: 8.0, reasoning: "" },
                { agent_name: "Performance", option: "Postgres", score: 7.0, reasoning: "" }
              ],
              cross_exam_transcript: [],
              consensus: consensusResult,
              user_id: null
            });
          }
        }
      }, 1500);

      return () => {
        clearInterval(interval);
      };
    }

    setStatus("analyzing");
    setAgentStances([]);
    setToolCalls([]);
    setCrossExamTranscript([]);
    setConsensus(null);
    setError(null);

    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : "";
    const url = `${API_BASE}/debate/${debateId}/stream${tokenParam}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener("agent_stance", (e) => {
      try {
        const stance: AgentStance = JSON.parse(e.data);
        setAgentStances((prev) => {
          // Avoid duplicates
          if (prev.some((s) => s.agent_name === stance.agent_name && s.option === stance.option)) {
            return prev;
          }
          return [...prev, stance];
        });
        setActiveAgent(stance.agent_name);
      } catch (err) {
        console.error("Failed to parse agent_stance event data", err);
      }
    });

    es.addEventListener("tool_call", (e) => {
      try {
        const toolCall: ToolCall = JSON.parse(e.data);
        setToolCalls((prev) => [...prev, toolCall]);
      } catch (err) {
        console.error("Failed to parse tool_call event data", err);
      }
    });

    es.addEventListener("cross_exam", (e) => {
      try {
        const crossMsg: CrossExamMessage = JSON.parse(e.data);
        setCrossExamTranscript((prev) => {
          if (prev.some((m) => m.from_agent === crossMsg.from_agent && m.challenge === crossMsg.challenge)) {
            return prev;
          }
          return [...prev, crossMsg];
        });
        setStatus("cross_examining");
        setActiveAgent(null);
      } catch (err) {
        console.error("Failed to parse cross_exam event data", err);
      }
    });

    es.addEventListener("consensus_final", (e) => {
      try {
        const consensusResult: ConsensusResult = JSON.parse(e.data);
        setConsensus(consensusResult);
        setStatus("complete");
        setActiveAgent(null);
        es.close();

        if (onComplete) {
          // Build a dummy/complete DebateResult to return
          onComplete({
            debate_id: debateId,
            preset_id: "developer", // Will be overridden or set later
            question: "",
            options: [],
            status: "complete",
            created_at: new Date().toISOString(),
            agent_stances: [], // Will be merged in states
            cross_exam_transcript: [],
            consensus: consensusResult,
            user_id: null,
          });
        }
      } catch (err) {
        console.error("Failed to parse consensus_final event data", err);
      }
    });

    es.addEventListener("error", (e: any) => {
      es.close();
      let errMsg = "Stream error occurred";
      if (e.data) {
        try {
          const data = JSON.parse(e.data);
          errMsg = data.message || errMsg;
        } catch {}
      }
      setError(errMsg);
      setStatus("failed");
      if (onError) onError(errMsg);
    });

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [debateId, token]);

  return {
    status,
    agentStances,
    toolCalls,
    crossExamTranscript,
    consensus,
    error,
    activeAgent,
  };
}
