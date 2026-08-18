import React, { useState } from "react";
import { supabase } from "../supabaseClient.js";
import { ShineBorder } from "./ShineBorder.jsx";
import SlicedWaves from "./SlicedWaves/SlicedWaves.jsx";

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
      <div className="app-bg">
        <SlicedWaves
          color1="#c79a55"
          color2="#1b2430"
          color3="#a9752f"
          columns={14}
          rows={8}
          barThickness={0.08}
          speed={0.25}
          travel={0.7}
          waveSpread={0.9}
          rowOffset={1.0}
          softness={0.12}
          glow={0}
          brightness={1.0}
          contrast={1.0}
          opacity={0.13}
          orientation="horizontal"
          alternate={false}
          mouseInteraction={true}
          mouseStrength={1}
          mouseRadius={0.3}
          grain={true}
          grainIntensity={0.05}
        />
      </div>

      <form className="card auth-card" onSubmit={submit}>
        <ShineBorder />
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
