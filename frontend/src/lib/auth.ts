import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;
export function getAuthClient(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key || typeof window === "undefined") return null;
  client ??= createClient(url, key, { auth: { flowType: "pkce", persistSession: true,
    autoRefreshToken: true, detectSessionInUrl: true } });
  return client;
}

export async function sessionHeaders(): Promise<Record<string, string>> {
  const auth = getAuthClient();
  if (!auth) return {};
  const { data, error } = await auth.auth.getSession();
  if (error || !data.session) throw new Error("Sign in through Account to continue.");
  return { Authorization: `Bearer ${data.session.access_token}` };
}
