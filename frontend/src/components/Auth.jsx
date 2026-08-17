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
    <div className="app-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
      <form className="card" style={{ width: 360 }} onSubmit={submit}>
        <div className="section-label">{mode === "login" ? "Sign in" : "Create account"}</div>
        <input
          className="filter-input"
          style={{ width: "100%", marginTop: 10 }}
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="filter-input"
          style={{ width: "100%", marginTop: 10 }}
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={6}
        />
        {error && <div className="error-banner" style={{ marginTop: 10 }}>{error}</div>}
        {notice && <p style={{ fontSize: 12.5, color: "var(--text-muted)" }}>{notice}</p>}
        <button className="btn btn-brass" type="submit" disabled={busy} style={{ marginTop: 12, width: "100%" }}>
          {busy ? "Please wait..." : mode === "login" ? "Sign in" : "Sign up"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ marginTop: 8, width: "100%" }}
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
