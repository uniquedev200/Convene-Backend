import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseClient";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get("code");

  if (code) {
    try {
      // Exchange callback code for a Supabase session
      await supabase.auth.exchangeCodeForSession(code);
    } catch (err) {
      console.error("OAuth code exchange failed:", err);
    }
  }

  // Redirect back to main dashboard page
  return NextResponse.redirect(requestUrl.origin);
}
