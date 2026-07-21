"use client";

import React, { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings, Moon, Sun, Database, Trash2, Mail, Check } from "lucide-react";

interface SettingsPanelProps {
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onCancel: () => void;
  onClearHistory: () => void;
}

export function SettingsPanel({ theme, onToggleTheme, onCancel, onClearHistory }: SettingsPanelProps) {
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [apiBase, setApiBase] = useState<string>("");
  const [savedBase, setSavedBase] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const email = localStorage.getItem("convene_email");
      if (email && !email.endsWith("@convene.anon")) {
        setUserEmail(email);
      } else {
        setUserEmail(null);
      }

      const currentBase = localStorage.getItem("convene_api_base") || "http://localhost:8000";
      setApiBase(currentBase);
    }
  }, []);

  const handleSaveApiBase = (val: string) => {
    localStorage.setItem("convene_api_base", val);
    setApiBase(val);
    setSavedBase(true);
    setTimeout(() => {
      setSavedBase(false);
      // Reload page to apply new fetch endpoints across services
      window.location.reload();
    }, 1000);
  };

  return (
    <div className="w-full max-w-lg mx-auto p-4 animate-in fade-in duration-200">
      <Card className="border-border-color bg-card-bg shadow-[0_8px_32px_rgba(0,0,0,0.1)]">
        <CardHeader className="pb-3 border-b border-border-color bg-background/30 p-4">
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            <CardTitle className="text-sm font-bold text-primary-text uppercase tracking-wider">Workspace Settings</CardTitle>
          </div>
          <CardDescription className="text-xs text-secondary-text">
            Configure theme aesthetics, database targets, and credential permissions.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 space-y-6">
          {/* Theme Selector */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-primary-text uppercase tracking-wider">Workspace Theme</h4>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => { if (theme !== "light") onToggleTheme(); }}
                className={`flex items-center justify-center gap-2 p-3 rounded-custom border transition-all text-xs font-semibold cursor-pointer ${
                  theme === "light"
                    ? "bg-foreground border-foreground text-background shadow-[0_2px_8px_rgba(0,0,0,0.06)]"
                    : "border-border-color text-secondary-text bg-transparent hover:text-primary-text"
                }`}
              >
                <Sun className="h-4 w-4" />
                Light Mode
              </button>
              <button
                type="button"
                onClick={() => { if (theme !== "dark") onToggleTheme(); }}
                className={`flex items-center justify-center gap-2 p-3 rounded-custom border transition-all text-xs font-semibold cursor-pointer ${
                  theme === "dark"
                    ? "bg-foreground border-foreground text-background shadow-[0_2px_8px_rgba(255,255,255,0.06)]"
                    : "border-border-color text-secondary-text bg-transparent hover:text-primary-text"
                }`}
              >
                <Moon className="h-4 w-4" />
                Dark Mode
              </button>
            </div>
          </div>

          {/* Database & API Endpoint Base */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-primary-text uppercase tracking-wider flex items-center gap-1.5">
              <Database className="h-4 w-4" />
              API Routing Target
            </h4>
            <div className="space-y-1.5">
              <button
                type="button"
                onClick={() => handleSaveApiBase("https://convene-backend-0fwn.onrender.com")}
                className={`w-full flex items-center justify-between p-3 rounded-custom border text-left text-xs transition-all cursor-pointer ${
                  apiBase === "https://convene-backend-0fwn.onrender.com"
                    ? "border-accent bg-accent-muted text-primary-text"
                    : "border-border-color text-secondary-text hover:text-primary-text"
                }`}
              >
                <div>
                  <span className="font-bold block">Hosted Backend</span>
                  <span className="text-[10px] text-neutral-500">https://convene-backend-0fwn.onrender.com</span>
                </div>
                {apiBase === "https://convene-backend-0fwn.onrender.com" && <Check className="h-4 w-4 text-accent" />}
              </button>

              <button
                type="button"
                onClick={() => handleSaveApiBase("http://localhost:8000")}
                className={`w-full flex items-center justify-between p-3 rounded-custom border text-left text-xs transition-all cursor-pointer ${
                  apiBase === "http://localhost:8000"
                    ? "border-accent bg-accent-muted text-primary-text"
                    : "border-border-color text-secondary-text hover:text-primary-text"
                }`}
              >
                <div>
                  <span className="font-bold block">Local server</span>
                  <span className="text-[10px] text-neutral-500">http://localhost:8000</span>
                </div>
                {apiBase === "http://localhost:8000" && <Check className="h-4 w-4 text-accent" />}
              </button>
            </div>
            {savedBase && (
              <span className="text-[10px] text-accent block text-center animate-pulse">
                Routing saved! Reloading workspace...
              </span>
            )}
          </div>

          {/* User Identity */}
          {userEmail && (
            <div className="bg-background border border-border-color p-3 rounded-custom space-y-2">
              <h4 className="text-[10px] uppercase font-bold text-secondary-text flex items-center gap-1">
                <Mail className="h-3.5 w-3.5" />
                Active Account Credentials
              </h4>
              <p className="text-xs text-primary-text font-mono truncate">{userEmail}</p>
            </div>
          )}

          {/* Clear Cache / Data */}
          <div className="space-y-2 border-t border-border-color pt-4">
            <h4 className="text-xs font-bold text-primary-text uppercase tracking-wider">Danger Zone</h4>
            <div className="bg-background border border-border-color p-3 rounded-custom flex items-center justify-between gap-4">
              <div>
                <span className="text-xs font-bold text-primary-text block">Clear Local Debate History</span>
                <span className="text-[10px] text-neutral-500">Wipes all cached tokens and session items in local storage.</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (confirm("Are you sure you want to clear all history and log out?")) {
                    onClearHistory();
                  }
                }}
                className="p-2 border border-rose-500/30 bg-rose-950/20 text-rose-400 hover:bg-rose-950/40 rounded transition-all cursor-pointer"
                title="Clear Data"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Cancel button */}
          <div className="pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={onCancel}
              className="w-full h-10 text-xs hover:bg-accent-muted"
            >
              Back to Dashboard
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
