"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [mode, setMode] = useState<"login" | "signup">("login");

  useEffect(() => {
    let mounted = true;

    async function checkSession() {
      const { data } = await supabase.auth.getSession();
      if (!mounted) return;

      if (data.session) {
        console.log("Logged in user:", data.session.user?.email);
        router.replace("/");
        return;
      }

      setCheckingSession(false);
    }

    void checkSession();

    return () => {
      mounted = false;
    };
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);

    if (mode === "signup") {
      const { error: signUpError } = await supabase.auth.signUp({
        email,
        password
      });

      if (signUpError) {
        setError(signUpError.message);
        setSubmitting(false);
        return;
      }

      setSuccess("Account created. You can now log in.");
      setMode("login");
      setSubmitting(false);
      return;
    }

    const { error: signInError, data } = await supabase.auth.signInWithPassword({
      email,
      password
    });

    if (signInError) {
      setError(signInError.message);
      setSubmitting(false);
      return;
    }

    console.log("Logged in user:", data.user?.email);
    router.replace("/");
  }

  if (checkingSession) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-6 py-8 shadow-soft">
          <p className="text-sm font-semibold text-slate-500">Checking session...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-lg border border-slate-200 bg-white px-6 py-8 shadow-soft">
        <p className="text-xs font-bold text-slate-500">Options MVP</p>
        <div className="mt-2 flex items-center justify-between gap-4">
          <h1 className="text-3xl font-black text-slate-950">{mode === "login" ? "Sign in" : "Sign up"}</h1>
          <button
            type="button"
            onClick={() => {
              setMode((current) => (current === "login" ? "signup" : "login"));
              setError(null);
              setSuccess(null);
            }}
            className="text-sm font-bold text-blue-600 transition hover:text-blue-700"
          >
            {mode === "login" ? "Sign up" : "Back to login"}
          </button>
        </div>
        <p className="mt-2 text-sm font-medium text-slate-500">
          {mode === "login"
            ? "Use your email and password to access the dashboard."
            : "Create an account with your email and password."}
        </p>

        <div className="mt-6 space-y-4">
          <label className="block">
            <span className="mb-2 block text-sm font-bold text-slate-700">Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="h-11 w-full rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-900 outline-none transition focus:border-blue-400"
              autoComplete="email"
              required
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-bold text-slate-700">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-11 w-full rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-900 outline-none transition focus:border-blue-400"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
            />
          </label>
        </div>

        {error ? <p className="mt-4 text-sm font-semibold text-red-600">{error}</p> : null}
        {success ? <p className="mt-4 text-sm font-semibold text-emerald-600">{success}</p> : null}

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 inline-flex h-11 w-full items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-black text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {submitting ? (mode === "login" ? "Signing in..." : "Creating account...") : mode === "login" ? "Login" : "Create account"}
        </button>
      </form>
    </main>
  );
}
