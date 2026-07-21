import React, { useState, useEffect } from "react";
import { api, Preset, ToolInfo } from "@/services/api";
import { supabase } from "@/lib/supabaseClient";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Play, Plus, Trash2, Globe, Shield, Activity, Sparkles, User, Settings, Lock } from "lucide-react";

interface ConfiguratorProps {
  onStartDebate: (config: {
    preset_id: string;
    question: string;
    options: string[];
    constraints: {
      team_size: number;
      timeline: string;
      budget?: string;
    };
    isAnonymous: boolean;
  }) => void;
  isStarting: boolean;
}

export function Configurator({ onStartDebate, isStarting }: ConfiguratorProps) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string>("developer");
  const [question, setQuestion] = useState<string>("");
  const [options, setOptions] = useState<string[]>(["", ""]);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  
  // Constraints
  const [teamSize, setTeamSize] = useState<number>(3);
  const [timeline, setTimeline] = useState<string>("6 months");
  const [budget, setBudget] = useState<string>("");
  
  // Toggles & Flags
  const [isAnonymous, setIsAnonymous] = useState<boolean>(true);
  
  // Auth states (if not anonymous)
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState<boolean>(false);

  useEffect(() => {
    // Check initial state
    const localToken = localStorage.getItem("convene_token");
    if (localToken) {
      setIsLoggedIn(true);
      setUserEmail(localStorage.getItem("convene_email") || "user@workspace.com");
      setIsAnonymous(false);
    }

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (session) {
        setIsLoggedIn(true);
        setUserEmail(session.user.email ?? "user@supabase.com");
        setIsAnonymous(false);
      } else {
        if (!localStorage.getItem("convene_token")) {
          setIsLoggedIn(false);
          setUserEmail(null);
          setIsAnonymous(true);
        }
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  // Load presets on mount
  useEffect(() => {
    async function fetchPresets() {
      try {
        const data = await api.getPresets();
        setPresets(data);
        if (data.length > 0) {
          setSelectedPresetId(data[0].preset_id);
        }
      } catch (err) {
        console.error("Failed to fetch presets", err);
      }
    }
    fetchPresets();

    // Check existing auth token
    const token = localStorage.getItem("convene_token");
    const savedEmail = localStorage.getItem("convene_email");
    if (token && savedEmail) {
      setIsLoggedIn(true);
      setUserEmail(savedEmail);
      setIsAnonymous(false);
    }
  }, []);

  const handlePresetSelect = (presetId: string) => {
    setSelectedPresetId(presetId);
    
    // Set a matching starter prompt if available
    const activePreset = presets.find(p => p.preset_id === presetId);
    if (activePreset) {
      // Set some default starter prompts if needed
      if (presetId === "developer") {
        setQuestion("Should we use Postgres or MongoDB for our new core analytics pipeline?");
        setOptions(["Postgres", "MongoDB"]);
      } else if (presetId === "education") {
        setQuestion("Should a college CS student focus on learning Rust or Go?");
        setOptions(["Rust", "Go"]);
      } else if (presetId === "startup") {
        setQuestion("Should our pre-seed SaaS startup focus on subscription or one-time pricing?");
        setOptions(["Subscription", "One-time Pricing"]);
      }
    }
  };

  const handleAddOption = () => {
    if (options.length < 4) {
      setOptions([...options, ""]);
    }
  };

  const handleRemoveOption = (index: number) => {
    if (options.length > 2) {
      const newOptions = [...options];
      newOptions.splice(index, 1);
      setOptions(newOptions);
    }
  };

  const handleOptionChange = (index: number, val: string) => {
    const newOptions = [...options];
    newOptions[index] = val;
    setOptions(newOptions);
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthLoading(true);
    try {
      if (authMode === "login") {
        const data = await api.login(email, password);
        localStorage.setItem("convene_token", data.access_token);
        localStorage.setItem("convene_user_id", data.user_id);
        localStorage.setItem("convene_email", email);
        setIsLoggedIn(true);
        setUserEmail(email);
        setIsAnonymous(false);
      } else {
        const data = await api.signup(email, password);
        localStorage.setItem("convene_token", data.access_token);
        localStorage.setItem("convene_user_id", data.user_id);
        localStorage.setItem("convene_email", email);
        setIsLoggedIn(true);
        setUserEmail(email);
        setIsAnonymous(false);
      }
      setEmail("");
      setPassword("");
    } catch (err: any) {
      setAuthError(err.message || "Authentication failed");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    localStorage.removeItem("convene_token");
    localStorage.removeItem("convene_user_id");
    localStorage.removeItem("convene_email");
    await supabase.auth.signOut();
    setIsLoggedIn(false);
    setUserEmail(null);
    setIsAnonymous(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    
    const filteredOptions = options.map(o => o.trim()).filter(Boolean);
    if (filteredOptions.length < 2) {
      alert("Please provide at least 2 options.");
      return;
    }

    let activeToken = localStorage.getItem("convene_token");
    
    // Auto-login anonymous user if required
    if (isAnonymous && !activeToken) {
      try {
        const anonEmail = `anon_${Math.random().toString(36).substring(2, 10)}@convene.anon`;
        const anonPassword = `anonPass_${Math.random().toString(36).substring(2, 12)}!`;
        const data = await api.signup(anonEmail, anonPassword);
        localStorage.setItem("convene_token", data.access_token);
        localStorage.setItem("convene_user_id", data.user_id);
        localStorage.setItem("convene_email", anonEmail);
        activeToken = data.access_token;
      } catch (err: any) {
        console.error("Failed to generate anonymous session", err);
        alert("Failed to initialize guest session. Please log in manually.");
        return;
      }
    }

    onStartDebate({
      preset_id: selectedPresetId,
      question: question.trim(),
      options: filteredOptions,
      constraints: {
        team_size: teamSize,
        timeline: timeline.trim(),
        ...(budget.trim() ? { budget: budget.trim() } : {})
      },
      isAnonymous
    });
  };

  const activePreset = presets.find(p => p.preset_id === selectedPresetId);

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 p-4">
      {/* Left 2 Columns: Config Settings */}
      <div className="md:col-span-2 space-y-6">
        
        {/* Main Topic Input */}
        <Card className="border-border-color bg-card-bg relative">
          {/* Floating Mascot Bot on the left */}
          <div className="absolute -left-26 top-1/2 -translate-y-1/2 hidden lg:flex flex-col items-center group z-30">
            {/* Tooltip speech bubble (opens to the right of the mascot) */}
            <div className="absolute left-full ml-3 top-1/2 -translate-y-1/2 bg-[#1C1C1C] border border-border-color px-2.5 py-1.5 rounded-custom text-[10px] text-neutral-300 shadow-[0_4px_12px_rgba(0,0,0,0.15)] opacity-0 scale-95 group-hover:opacity-100 group-hover:scale-100 transition-all duration-200 pointer-events-none whitespace-nowrap font-semibold">
              Enter a topic to begin! 🤖
            </div>
            {/* Mascot Button */}
            <button
              type="button"
              onClick={() => textareaRef.current?.focus()}
              className="w-20 h-20 rounded-full border-2 border-blue-500 bg-[#111] shadow-[0_0_20px_rgba(59,130,246,0.4)] ring-4 ring-blue-500/20 overflow-hidden hover:scale-110 active:scale-95 hover:border-blue-400 hover:shadow-[0_0_25px_rgba(59,130,246,0.6)] transition-all duration-300 flex items-center justify-center cursor-pointer animate-float-slow"
              title="Convene Helper Mascot"
            >
              <img
                src="/mascot.jpg"
                alt="Mascot Helper"
                className="w-full h-full object-cover filter grayscale contrast-125 hover:grayscale-0 transition-all duration-300"
              />
            </button>
          </div>
          <CardHeader>
            <CardTitle className="text-xl flex items-center gap-2">
              <Sparkles className="text-accent h-5 w-5" />
              Debate Topic
            </CardTitle>
            <CardDescription>Enter the core architectural question or trade-off you want evaluated.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <textarea
              ref={textareaRef}
              required
              rows={3}
              placeholder="e.g. Should we migrate our monolith backend to Node.js microservices?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="w-full rounded-custom border border-border-color bg-background p-3 text-sm text-foreground focus:outline-none focus:border-accent resize-none placeholder:text-neutral-500"
            />
          </CardContent>
        </Card>

        {/* Presets Grid */}
        <div className="space-y-3">
          <Label className="text-xs uppercase tracking-wider text-secondary-text">Select Domain Persona Preset</Label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {presets.map((p) => {
              const isSelected = selectedPresetId === p.preset_id;
              return (
                <div
                  key={p.preset_id}
                  onClick={() => handlePresetSelect(p.preset_id)}
                  className={`cursor-pointer rounded-custom border p-5 flex flex-col justify-between h-40 transition-all duration-300 hover:scale-[1.03] active:scale-[0.97] ${
                    isSelected
                      ? "border-accent bg-accent/5 shadow-[0_0_25px_rgba(255,255,255,0.08)]"
                      : "border-border-color bg-card-bg hover:border-neutral-400 hover:shadow-[0_4px_20px_rgba(255,255,255,0.02)]"
                  }`}
                >
                  <div>
                    <h4 className="font-bold text-md text-primary-text capitalize">{p.display_name}</h4>
                    <p className="text-xs text-secondary-text mt-1">
                      {p.preset_id === "developer" && "Best for technical, code and framework trade-offs."}
                      {p.preset_id === "education" && "Focused on learning depth, rigor and career signal."}
                      {p.preset_id === "startup" && "Aimed at business agility, ROI, speed and marketing."}
                    </p>
                  </div>
                  <div className="flex -space-x-2 mt-4">
                    {p.personas?.map((persona: any, idx: number) => (
                      <div
                        key={idx}
                        title={persona.agent_name || persona}
                        className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold border border-card-bg ${
                          isSelected ? "bg-foreground text-background" : "bg-accent-muted text-secondary-text"
                        }`}
                      >
                        {(persona.agent_name || persona).substring(0, 2)}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Options List Builder */}
        <Card className="border-border-color bg-card-bg">
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">Comparative Options</CardTitle>
              <CardDescription>Define the choices to compare (min 2, max 4).</CardDescription>
            </div>
            {options.length < 4 && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddOption}
                className="flex items-center gap-1.5"
              >
                <Plus className="h-3.5 w-3.5" />
                Add Choice
              </Button>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            {options.map((opt, idx) => (
              <div key={idx} className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-[#1A1A1A] border border-border-color flex items-center justify-center text-xs font-semibold text-secondary-text">
                  {idx + 1}
                </div>
                <Input
                  required
                  type="text"
                  placeholder={`Option ${idx + 1}`}
                  value={opt}
                  onChange={(e) => handleOptionChange(idx, e.target.value)}
                  className="flex-1"
                />
                {options.length > 2 && (
                  <button
                    type="button"
                    onClick={() => handleRemoveOption(idx)}
                    className="p-2 text-neutral-500 hover:text-red-500 hover:scale-110 active:scale-90 transition-all cursor-pointer"
                  >
                    <Trash2 className="h-4.5 w-4.5" />
                  </button>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Right Column: Advanced parameters & auth */}
      <div className="space-y-6">
        {/* Advanced parameters */}
        <Card className="border-border-color bg-card-bg">
          <CardHeader>
            <CardTitle className="text-md flex items-center gap-2">
              <Settings className="text-secondary-text h-4 w-4" />
              Parameters
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="team-size">Team Size</Label>
              <Input
                id="team-size"
                type="number"
                min={1}
                max={50}
                value={teamSize}
                onChange={(e) => setTeamSize(parseInt(e.target.value) || 1)}
              />
            </div>
            
            <div className="space-y-1.5">
              <Label htmlFor="timeline">Timeline Constraint</Label>
              <Input
                id="timeline"
                type="text"
                placeholder="e.g. 3 months, 1 year"
                value={timeline}
                onChange={(e) => setTimeline(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="budget">Budget (Optional)</Label>
              <Input
                id="budget"
                type="text"
                placeholder="e.g. lean, $500/mo, $50k"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
              />
            </div>

            <div className="border-t border-border-color pt-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-sm font-semibold text-primary-text">Execute Anonymously</span>
                  <span className="text-xs text-secondary-text">Bypasses registration flow</span>
                </div>
                <Switch checked={isAnonymous} onCheckedChange={setIsAnonymous} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* User Auth Card (if not anonymous) */}
        {!isAnonymous && (
          <Card className="border-border-color bg-card-bg">
            <CardHeader>
              <CardTitle className="text-md flex items-center gap-2">
                <Lock className="text-secondary-text h-4 w-4" />
                Workspace Identity
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoggedIn ? (
                <div className="space-y-3 text-center">
                  <div className="flex items-center gap-2 bg-background p-2.5 rounded-custom border border-border-color text-xs text-primary-text justify-center">
                    <User className="h-4 w-4 text-secondary-text shrink-0" />
                    <span>{userEmail}</span>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full text-xs"
                    onClick={handleLogout}
                  >
                    Logout
                  </Button>
                </div>
              ) : (
                <form onSubmit={handleAuthSubmit} className="space-y-3">
                  <div className="flex border-b border-border-color">
                    <button
                      type="button"
                      onClick={() => setAuthMode("login")}
                      className={`flex-1 pb-2 text-center text-xs font-semibold ${
                        authMode === "login" ? "text-accent border-b-2 border-accent" : "text-secondary-text"
                      }`}
                    >
                      Login
                    </button>
                    <button
                      type="button"
                      onClick={() => setAuthMode("signup")}
                      className={`flex-1 pb-2 text-center text-xs font-semibold ${
                        authMode === "signup" ? "text-accent border-b-2 border-accent" : "text-secondary-text"
                      }`}
                    >
                      Sign Up
                    </button>
                  </div>

                  <Input
                    required
                    type="email"
                    placeholder="Workspace Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-8 text-xs"
                  />
                  <Input
                    required
                    type="password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-8 text-xs"
                  />

                  {authError && <p className="text-[10px] text-red-500 text-center">{authError}</p>}

                  <Button type="submit" disabled={authLoading} size="sm" className="w-full text-xs h-8">
                    {authLoading ? "Verifying..." : authMode === "login" ? "Sign In" : "Register"}
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        )}

        {/* Start Button */}
        <Button
          type="submit"
          disabled={isStarting || (!isAnonymous && !isLoggedIn)}
          className="w-full h-14 rounded-custom text-md font-bold flex items-center justify-center gap-2 shadow-lg hover:shadow-[0_0_25px_rgba(255,255,255,0.12)] cursor-pointer transition-all"
        >
          {isStarting ? (
            <>
              <div className="w-5 h-5 rounded-full border-2 border-t-transparent border-white animate-spin" />
              Initializing War Room...
            </>
          ) : (
            <>
              <Play className="h-5 w-5 fill-current" />
              Start Multi-Agent Debate
            </>
          )}
        </Button>

        <Button
          type="button"
          onClick={() => {
            onStartDebate({
              preset_id: "developer",
              question: "demo-simulation",
              options: ["Postgres", "MongoDB"],
              constraints: {
                team_size: 4,
                timeline: "3 months"
              },
              isAnonymous: true
            });
          }}
          disabled={isStarting}
          variant="outline"
          className="w-full h-11 rounded-custom text-xs font-semibold flex items-center justify-center gap-2 border border-dashed border-border-color hover:border-accent hover:bg-accent-muted cursor-pointer transition-all"
        >
          <Sparkles className="h-4 w-4 text-accent" />
          Preview Trial Simulation (No API Required)
        </Button>
        
        {!isAnonymous && !isLoggedIn && (
          <p className="text-center text-[10px] text-yellow-500">
            * Authentication is required to track debate histories.
          </p>
        )}
      </div>
    </form>
  );
}
