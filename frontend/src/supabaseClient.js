import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// createClient validates the URL eagerly and throws if it's missing or
// malformed. That throw happens at module-import time, before React ever
// mounts, so a missing env var here previously took down the entire page
// to a blank screen with no on-page error at all. Falling back to a
// harmless placeholder lets the module load; App.jsx checks
// supabaseConfigError and shows a real error screen instead.
export const supabaseConfigError =
  !supabaseUrl || !supabaseAnonKey
    ? "Missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY. Set them in frontend/.env locally, " +
      "or in your deployment's environment variables (then redeploy -- Vite bakes these in at build time)."
    : null;

if (supabaseConfigError) {
  console.error(supabaseConfigError);
}

export const supabase = createClient(
  supabaseUrl || "https://placeholder.supabase.co",
  supabaseAnonKey || "placeholder-anon-key"
);
