"use client";

import React, { useState, useEffect, useRef } from "react";
import { DebateResult, AgentStance } from "@/services/api";
import { RadarCanvas } from "./RadarCanvas";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import {
  Award,
  ShieldAlert,
  BarChart4,
  Network,
  FileCode,
  Copy,
  Check,
  ChevronRight,
  Info,
  TrendingUp,
  Scale
} from "lucide-react";
import mermaid from "mermaid";

// Initialize mermaid once on client side
if (typeof window !== "undefined") {
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    securityLevel: "loose",
    fontFamily: "var(--font-geist-mono)",
    themeVariables: {
      background: "#1C1C1C",
      primaryColor: "#2F2F2F",
      primaryTextColor: "#ECECEC",
      lineColor: "#3A3A3A",
      edgeLabelBackground: "#2F2F2F"
    }
  });
}

// Sub-component: Mermaid Renderer
function MermaidDiagram({ chartCode }: { chartCode: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<boolean>(false);

  useEffect(() => {
    if (!chartCode) return;
    
    let isMounted = true;
    const elementId = `mermaid-${Math.random().toString(36).substring(2, 10)}`;

    const renderDiagram = async () => {
      try {
        setError(false);
        // Pre-validate diagram using parse
        await mermaid.parse(chartCode);
        const { svg: svgHtml } = await mermaid.render(elementId, chartCode);
        if (isMounted) {
          setSvg(svgHtml);
        }
      } catch (err) {
        console.error("Mermaid parsing/rendering error:", err);
        if (isMounted) {
          setError(true);
        }
      }
    };

    renderDiagram();

    return () => {
      isMounted = false;
    };
  }, [chartCode]);

  if (error) {
    return (
      <div className="bg-[#1C1C1C] border border-red-950 p-4 rounded-custom text-xs text-red-400 font-mono">
        Failed to render architectural diagram. Output:
        <pre className="mt-2 text-[10px] text-neutral-500 whitespace-pre-wrap">{chartCode}</pre>
      </div>
    );
  }

  return (
    <div 
      ref={containerRef} 
      className="w-full bg-[#1C1C1C] border border-[#3A3A3A] p-4 rounded-custom overflow-auto flex items-center justify-center min-h-[300px]"
      dangerouslySetInnerHTML={{ __html: svg || '<div class="text-xs text-neutral-500">Compiling diagram...</div>' }}
    />
  );
}

interface ArtifactsPanelProps {
  result: DebateResult;
}

export function ArtifactsPanel({ result }: ArtifactsPanelProps) {
  const [activeTab, setActiveTab] = useState<string>("scoring");
  const [copied, setCopied] = useState<boolean>(false);
  const [selectedAgentFilter, setSelectedAgentFilter] = useState<string | null>(null);

  const { consensus, agent_stances, options, question, preset_id } = result;

  const handleCopyCode = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Compile Dynamic Mermaid Diagram code based on the actual scores
  const getMermaidCode = () => {
    const winner = consensus.winning_option;
    const cleanWinner = winner.replace(/[^a-zA-Z0-9]/g, "");
    
    let code = `graph TD\n`;
    code += `  classDef default fill:#2F2F2F,stroke:#3A3A3A,stroke-width:1px,color:#ECECEC;\n`;
    code += `  classDef winner fill:#FFFFFF,stroke:#FFFFFF,stroke-width:2px,color:#000000;\n`;
    code += `  classDef agent fill:#1F1F1F,stroke:#3A3A3A,stroke-width:1px,color:#A1A1A1;\n`;
    
    code += `  Q["Tradeoff Query<br/>${question.substring(0, 45)}..."]\n`;
    code += `  M{"Moderator Consensus<br/>Confidence: ${consensus.confidence_pct}%"}\n`;
    code += `  W["🏆 Winner: ${winner}"]:::winner\n`;
    
    code += `  Q --> M\n`;
    
    // Add agents as decision nodes
    const uniqueAgents = Array.from(new Set(agent_stances.map(s => s.agent_name)));
    uniqueAgents.forEach((agent, idx) => {
      const cleanAgent = agent.replace(/[^a-zA-Z0-9]/g, "");
      const stance = agent_stances.find(s => s.agent_name === agent && s.option === winner);
      const score = stance ? stance.score : 0;
      
      code += `  A_${cleanAgent}["${agent}<br/>Score: ${score}/10"]:::agent\n`;
      code += `  Q -.-> A_${cleanAgent}\n`;
      code += `  A_${cleanAgent} -.-> M\n`;
    });
    
    code += `  M --> W\n`;
    
    // Add losing options
    consensus.option_breakdown.forEach((o, idx) => {
      if (o.option !== winner) {
        const cleanOpt = o.option.replace(/[^a-zA-Z0-9]/g, "");
        code += `  L_${cleanOpt}["${o.option}<br/>Avg Score: ${o.average_score}"]\n`;
        code += `  M --> L_${cleanOpt}\n`;
      }
    });
    
    return code;
  };

  const mermaidCode = getMermaidCode();

  // Generate mock boilerplate code snippets for the winning technology
  const getCodeSnippet = () => {
    const winner = consensus.winning_option.toLowerCase();
    
    if (winner.includes("postgres") || winner.includes("sql")) {
      return `-- PostgreSQL Database Connection Schema & Indexing\nCREATE TABLE IF NOT EXISTS users (\n  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n  email VARCHAR(255) UNIQUE NOT NULL,\n  password_hash VARCHAR(255) NOT NULL,\n  created_at TIMESTAMPTZ DEFAULT NOW()\n);\n\nCREATE TABLE IF NOT EXISTS debates (\n  id VARCHAR(64) PRIMARY KEY,\n  user_id UUID REFERENCES users(id) ON DELETE CASCADE,\n  question TEXT NOT NULL,\n  options JSONB NOT NULL,\n  status VARCHAR(32) NOT NULL,\n  created_at TIMESTAMPTZ DEFAULT NOW()\n);\n\n-- Performance indices for analytical query performance\nCREATE INDEX idx_debates_user_id ON debates(user_id);\nCREATE INDEX idx_debates_status ON debates(status);`;
    }
    
    if (winner.includes("mongo") || winner.includes("nosql")) {
      return `// MongoDB Mongoose Connection Schema for Debate Analytics\nconst mongoose = require('mongoose');\n\nconst DebateSchema = new mongoose.Schema({\n  debateId: { type: String, required: true, unique: true },\n  userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User' },\n  question: { type: String, required: true },\n  options: [{ type: String }],\n  status: { type: String, enum: ['pending', 'analyzing', 'complete', 'failed'], default: 'pending' },\n  consensus: {\n    winningOption: String,\n    confidencePct: Number,\n    rationale: String\n  }\n}, { timestamps: true });\n\nmodule.exports = mongoose.model('Debate', DebateSchema);`;
    }
    
    if (winner.includes("rust")) {
      return `// Rust performance-focused entry point\n#[derive(Debug, Serialize, Deserialize)]\nstruct DebateConfig {\n    preset_id: String,\n    question: String,\n    options: Vec<String>,\n    team_size: u32,\n}\n\nfn main() -> Result<(), Box<dyn std::error::Error>> {\n    let config = DebateConfig {\n        preset_id: String::from("developer"),\n        question: String::from("Rust vs Go"),\n        options: vec![String::from("Rust"), String::from("Go")],\n        team_size: 4,\n    };\n    println!("Initializing debate consensus analyzer: {:?}", config);\n    Ok(())\n}`;
    }

    // Default general mock configuration response
    return `{\n  "consensus": {\n    "winner": "${consensus.winning_option}",\n    "confidence": ${consensus.confidence_pct},\n    "agreement": ${consensus.agreement_pct},\n    "presetId": "${preset_id}"\n  },\n  "systemConstraints": {\n    "analyzedOptions": ${JSON.stringify(options)}\n  }\n}`;
  };

  const codeSnippet = getCodeSnippet();

  // Rationale LaTeX mockup
  const getLaTeXMath = () => {
    return `\\[ \\text{Weighted Consensus Score } (S_j) = \\sum_{i=1}^{N} w_i \\cdot s_{ij} \\]\n\\[ \\text{where: } w_i \\text{ is the weight of agent } i, \\text{ and } s_{ij} \\text{ is the score given by agent } i \\text{ to option } j. \\]\n\\[ \\text{Confidence Coefficient } (C) = \\frac{\\text{Agreement } \\%}{100} \\times \\max(S_j) = ${consensus.confidence_pct}\\% \\]`;
  };

  const filteredStances = selectedAgentFilter
    ? agent_stances.filter(s => s.agent_name === selectedAgentFilter)
    : agent_stances;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-5xl mx-auto p-4">
      {/* LEFT PANEL: Verdict Banner & Heatmap */}
      <div className="space-y-6">
        {/* Winner Banner */}
        <Card className="border-[#10A37F]/30 bg-gradient-to-br from-card-bg to-[#122A22] overflow-hidden relative shadow-[0_8px_32px_rgba(16,163,127,0.08)]">
          <div className="absolute top-0 right-0 w-24 h-24 bg-[#10A37F]/5 rounded-bl-full flex items-center justify-center">
            <Award className="h-10 w-10 text-[#10A37F] opacity-15" />
          </div>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase font-bold text-[#10A37F] bg-[#10A37F]/10 px-2.5 py-0.5 rounded-full border border-[#10A37F]/20 tracking-wider">
                Consensus Verdict
              </span>
            </div>
            <CardTitle className="text-2xl font-black text-[#10A37F] mt-2 tracking-wide drop-shadow-[0_2px_8px_rgba(16,163,127,0.2)]">
              {consensus.winning_option}
            </CardTitle>
            <CardDescription className="text-xs text-neutral-400">
              The multi-agent moderator aggregates these findings into a unified resolution.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#1C1C1C]/80 border border-[#3A3A3A] p-3 rounded-custom backdrop-blur-[1px]">
                <span className="text-[10px] text-secondary-text block font-mono">CONFIDENCE</span>
                <span className="text-xl font-black text-[#10A37F] flex items-center gap-1 mt-0.5">
                  <TrendingUp className="h-4 w-4 text-[#10A37F]" />
                  {consensus.confidence_pct}%
                </span>
              </div>
              <div className="bg-[#1C1C1C]/80 border border-[#3A3A3A] p-3 rounded-custom backdrop-blur-[1px]">
                <span className="text-[10px] text-secondary-text block font-mono">AGREEMENT</span>
                <span className="text-xl font-black text-[#10A37F] flex items-center gap-1 mt-0.5">
                  <Scale className="h-4 w-4 text-[#10A37F]" />
                  {consensus.agreement_pct}%
                </span>
              </div>
            </div>
            
            <div className="bg-[#1C1C1C] p-3 rounded-custom border border-[#3A3A3A] space-y-1">
              <span className="text-[10px] uppercase font-bold text-secondary-text flex items-center gap-1">
                <Info className="h-3 w-3" />
                Moderator Summary:
              </span>
              <p className="text-xs text-secondary-text leading-relaxed mt-1">
                {consensus.rationale}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Risk Heatmap & Rationale */}
        <Card className="border-border-color bg-card-bg">
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-md">Risk Assessments</CardTitle>
              <CardDescription>Major architectural & implementation risks identified.</CardDescription>
            </div>
            <div className="flex gap-1.5 overflow-x-auto max-w-[150px] md:max-w-none">
              <button
                onClick={() => setSelectedAgentFilter(null)}
                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                  selectedAgentFilter === null ? "bg-accent text-black border-transparent" : "border-[#3A3A3A] text-secondary-text hover:text-white"
                }`}
              >
                All
              </button>
              {Array.from(new Set(agent_stances.map(s => s.agent_name))).map(agent => (
                <button
                  key={agent}
                  onClick={() => setSelectedAgentFilter(agent)}
                  className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border whitespace-nowrap ${
                    selectedAgentFilter === agent ? "bg-accent text-black border-transparent" : "border-[#3A3A3A] text-secondary-text hover:text-white"
                  }`}
                >
                  {agent}
                </button>
              ))}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Risk Heatmap items */}
            <div className="space-y-2">
              {consensus.risks && consensus.risks.length > 0 ? (
                consensus.risks.map((risk, idx) => (
                  <div
                    key={idx}
                    className="flex gap-3 bg-[#1C1C1C] border border-[#3A3A3A] p-3 rounded-custom items-start"
                  >
                    <ShieldAlert className="h-4.5 w-4.5 text-neutral-400 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-xs text-primary-text leading-relaxed">{risk}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="bg-[#1C1C1C] p-3 rounded text-xs text-neutral-500 text-center">
                  No severe risks detected by the moderator.
                </div>
              )}
            </div>

            {/* Agent Specific Rationale Details */}
            <div className="border-t border-[#3A3A3A] pt-4">
              <span className="text-xs uppercase font-bold text-secondary-text block mb-3">Agent Stance Log:</span>
              <div className="space-y-3 max-h-48 overflow-y-auto pr-1">
                {filteredStances.map((stance, idx) => (
                  <div key={idx} className="bg-[#1C1C1C] border border-border-color p-3 rounded-custom space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-primary-text">{stance.agent_name}</span>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-neutral-500">{stance.option}</span>
                        <span className="text-[11px] text-accent font-bold bg-accent-muted px-1.5 py-0.2 rounded">
                          {stance.score}/10
                        </span>
                      </div>
                    </div>
                    <p className="text-[11px] text-secondary-text leading-relaxed">
                      {stance.reasoning}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* RIGHT PANEL: Analytical Tabs (Radar, Mermaid, Code Sandbox) */}
      <div>
        <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col justify-between">
          <TabsList className="grid grid-cols-3 w-full bg-[#1C1C1C] border border-[#3A3A3A]">
            <TabsTrigger value="scoring" className="flex items-center gap-1.5">
              <BarChart4 className="h-3.5 w-3.5" />
              Radar Chart
            </TabsTrigger>
            <TabsTrigger value="diagram" className="flex items-center gap-1.5">
              <Network className="h-3.5 w-3.5" />
              Diagram
            </TabsTrigger>
            <TabsTrigger value="sandbox" className="flex items-center gap-1.5">
              <FileCode className="h-3.5 w-3.5" />
              Code Sandbox
            </TabsTrigger>
          </TabsList>

          <TabsContent value="scoring" className="flex-1 mt-4">
            <Card className="border-border-color bg-card-bg h-full p-4">
              <h3 className="text-sm font-bold text-primary-text mb-3">Consensus Radar Grid</h3>
              <RadarCanvas agentStances={agent_stances} options={options} />
              <p className="text-[10px] text-neutral-500 mt-3 leading-relaxed">
                * Layered axes highlight the scores of each persona. Overlapping areas represent solid alignment, while divergent spikes show trade-offs.
              </p>
            </Card>
          </TabsContent>

          <TabsContent value="diagram" className="flex-1 mt-4">
            <Card className="border-border-color bg-card-bg h-full p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-primary-text">Decision Architecture Graph</h3>
                <span className="text-[10px] font-mono text-accent bg-accent-muted px-2 py-0.5 rounded-full border border-accent/10">
                  Mermaid.js Flow
                </span>
              </div>
              <MermaidDiagram chartCode={mermaidCode} />
              <p className="text-[10px] text-neutral-500 leading-relaxed">
                * Dynamic flowchart compiles evaluation flows showing weighted agents leading to the moderator consensus.
              </p>
            </Card>
          </TabsContent>

          <TabsContent value="sandbox" className="flex-1 mt-4">
            <Card className="border-border-color bg-card-bg h-full p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-primary-text">Math & Schema Sandbox</h3>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopyCode(codeSnippet)}
                  className="h-7 text-xs flex items-center gap-1 px-2.5"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-accent" /> : <Copy className="h-3.5 w-3.5" />}
                  {copied ? "Copied" : "Copy Schema"}
                </Button>
              </div>

              {/* LaTeX formulas rendering */}
              <div className="bg-[#1C1C1C] border border-[#3A3A3A] p-3 rounded-custom font-serif text-center text-xs text-primary-text leading-relaxed overflow-x-auto select-all"
                   dangerouslySetInnerHTML={{ __html: getLaTeXMath() }}
              />

              {/* Code Snippet Box */}
              <div className="relative">
                <pre className="bg-[#1A1A1A] border border-[#3A3A3A] p-3 rounded-custom font-mono text-[11px] text-neutral-300 overflow-x-auto h-40 max-h-40 select-all">
                  <code>{codeSnippet}</code>
                </pre>
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
