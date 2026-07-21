"use client";

import React from "react";
import { AgentStance } from "@/services/api";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip
} from "recharts";

interface RadarCanvasProps {
  agentStances: AgentStance[];
  options: string[];
}

export function RadarCanvas({ agentStances, options }: RadarCanvasProps) {
  // Parse agentStances to construct Recharts data
  // We want to group by agent_name, and get the score for each option.
  const getChartData = () => {
    const agents = Array.from(new Set(agentStances.map(s => s.agent_name)));
    
    return agents.map(agentName => {
      const dataPoint: Record<string, any> = {
        subject: agentName,
        fullMark: 10
      };
      
      options.forEach(opt => {
        const stance = agentStances.find(
          s => s.agent_name === agentName && s.option === opt
        );
        dataPoint[opt] = stance ? stance.score : 0;
      });
      
      return dataPoint;
    });
  };

  const data = getChartData();

  // Distinct monochrome & accent colors for comparative choices
  const colors = [
    "#FFFFFF", // Pure white
    "#A1A1A1", // Light-medium gray
    "#555555", // Medium-dark gray
    "#262626"  // Dark charcoal gray
  ];

  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-xs text-neutral-600 italic">
        Insufficient stance logs to compile Radar Canvas.
      </div>
    );
  }

  return (
    <div className="w-full h-80 min-h-64 relative bg-[#1C1C1C] border border-[#3A3A3A] p-4 rounded-custom">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarGrid stroke="#3A3A3A" />
          <PolarAngleAxis 
            dataKey="subject" 
            tick={{ fill: "#A1A1A1", fontSize: 10, fontWeight: 500 }}
          />
          <PolarRadiusAxis 
            angle={30} 
            domain={[0, 10]} 
            tick={{ fill: "#555555", fontSize: 9 }}
            stroke="#3A3A3A"
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#2F2F2F",
              borderColor: "#3A3A3A",
              borderRadius: "8px",
              color: "#ECECEC",
              fontSize: "11px",
              fontFamily: "monospace"
            }}
          />
          {options.map((opt, idx) => (
            <Radar
              key={opt}
              name={opt}
              dataKey={opt}
              stroke={colors[idx % colors.length]}
              fill={colors[idx % colors.length]}
              fillOpacity={0.15}
            />
          ))}
          <Legend 
            wrapperStyle={{ fontSize: "10px", marginTop: "10px", color: "#A1A1A1" }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
