"use client";

import React, { useState } from "react";
import { api } from "@/services/api";
import { supabase } from "@/lib/supabaseClient";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Shield, KeyRound, Mail, AlertCircle, CheckCircle2 } from "lucide-react";

interface LoginPanelProps {
  onSuccess: (token: string) => void;
  onCancel: () => void;
}

export function LoginPanel({ onSuccess, onCancel }: LoginPanelProps) {
  const [isSignUp, setIsSignUp] = useState<boolean>(false);
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const { error: err } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: window.location.origin,
        },
      });
      if (err) throw err;
    } catch (err: any) {
      setError(err.message || "Failed to trigger Google Sign-In.");
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Please fill out all fields.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      if (isSignUp) {
        const res = await api.signup(email, password);
        setSuccess("Account registered successfully! Logging you in...");
        setTimeout(() => {
          localStorage.setItem("convene_token", res.access_token);
          onSuccess(res.access_token);
        }, 1500);
      } else {
        const res = await api.login(email, password);
        setSuccess("Authentication successful! Welcome back.");
        setTimeout(() => {
          localStorage.setItem("convene_token", res.access_token);
          onSuccess(res.access_token);
        }, 1200);
      }
    } catch (err: any) {
      setError(err.message || "An error occurred during authentication.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md mx-auto p-4 animate-in fade-in duration-200">
      <Card className="border-border-color bg-card-bg shadow-[0_8px_32px_rgba(0,0,0,0.1)]">
        <CardHeader className="pb-3 text-center">
          <div className="mx-auto w-10 h-10 rounded-full bg-accent-muted border border-accent/10 flex items-center justify-center mb-3">
            <Shield className="h-5 w-5 text-foreground" />
          </div>
          <CardTitle className="text-xl font-black uppercase tracking-wider text-primary-text">
            {isSignUp ? "Create Workspace" : "Access Workspace"}
          </CardTitle>
          <CardDescription className="text-xs text-secondary-text">
            {isSignUp
              ? "Sign up to persist debate history and configurations"
              : "Enter credentials to access your debate panels"}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label className="text-[10px] uppercase font-bold tracking-wider text-secondary-text">Email Address</label>
              <div className="relative">
                <Mail className="absolute left-3 top-3 h-4 w-4 text-neutral-500" />
                <Input
                  type="email"
                  placeholder="name@workspace.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-9"
                  disabled={loading}
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] uppercase font-bold tracking-wider text-secondary-text">Password</label>
              <div className="relative">
                <KeyRound className="absolute left-3 top-3 h-4 w-4 text-neutral-500" />
                <Input
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-9"
                  disabled={loading}
                />
              </div>
            </div>

            {error && (
              <div className="bg-background border border-border-color p-3 rounded-custom flex items-start gap-2 animate-in slide-in-from-top-1">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span className="text-[11px] text-primary-text leading-relaxed">{error}</span>
              </div>
            )}

            {success && (
              <div className="bg-background border border-border-color p-3 rounded-custom flex items-start gap-2 animate-in slide-in-from-top-1">
                <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                <span className="text-[11px] text-primary-text leading-relaxed">{success}</span>
              </div>
            )}

            <div className="pt-2 flex gap-3">
              <Button
                type="button"
                variant="ghost"
                onClick={onCancel}
                className="flex-1 h-10 text-xs hover:bg-accent-muted"
                disabled={loading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                className="flex-grow h-10 text-xs font-bold"
                disabled={loading}
              >
                {loading ? "Processing..." : isSignUp ? "Sign Up" : "Sign In"}
              </Button>
            </div>

            <div className="relative flex py-2 items-center">
              <div className="flex-grow border-t border-border-color/30"></div>
              <span className="flex-shrink mx-4 text-[9px] text-secondary-text uppercase font-bold">Or</span>
              <div className="flex-grow border-t border-border-color/30"></div>
            </div>

            <Button
              type="button"
              variant="outline"
              onClick={handleGoogleSignIn}
              disabled={loading}
              className="w-full h-10 text-xs flex items-center justify-center gap-2"
            >
              <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              Sign in with Google
            </Button>
          </form>

          <div className="border-t border-border-color pt-4 text-center">
            <button
              type="button"
              onClick={() => {
                setIsSignUp(!isSignUp);
                setError(null);
                setSuccess(null);
              }}
              className="text-[11px] text-secondary-text hover:text-primary-text transition-colors underline cursor-pointer"
            >
              {isSignUp ? "Already have an account? Sign In" : "Need a workspace account? Sign Up"}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
