import React, { useState } from "react";
import { supabase } from "../supabaseClient.js";

export default function Auth() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setNotice(
          "Account created. If email confirmation is on for this project, check your inbox; otherwise you're signed in."
        );
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-shell">
      <form className="card auth-card" onSubmit={submit}>
        <div className="auth-brand" aria-label="Kitsu AI brand">
          <img src="/kitsu-logo.png" alt="Kitsu AI logo" className="auth-logo" />
          <div>
            <div className="auth-brand-name">Kitsu AI</div>
            <div className="auth-brand-tag">Document intelligence</div>
          </div>
        </div>

        <div className="auth-header">
          <div className="section-label">{mode === "login" ? "Sign in" : "Create account"}</div>
        </div>

        <input
          className="filter-input auth-input"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="filter-input auth-input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={6}
        />
        {error && <div className="error-banner auth-error">{error}</div>}
        {notice && <p className="auth-notice">{notice}</p>}

        <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
          {busy ? "Please wait..." : mode === "login" ? "Sign in" : "Sign up"}
        </button>

        <button
          type="button"
          className="btn btn-ghost auth-toggle"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            setError(null);
            setNotice(null);
          }}
        >
          {mode === "login" ? "Need an account? Sign up" : "Have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
