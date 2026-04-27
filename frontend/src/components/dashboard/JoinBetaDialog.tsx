"use client";

import { FormEvent, useMemo, useState } from "react";
import { supabase } from "@/lib/supabaseClient";

type SubmitState = "idle" | "submitting" | "success" | "error";

export function JoinBetaDialog() {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const isConfigured = useMemo(
    () => Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY),
    []
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!isConfigured) {
      setSubmitState("error");
      setMessage("Beta signups are not configured yet.");
      return;
    }

    setSubmitState("submitting");
    setMessage(null);

    const { error } = await supabase.from("beta_interest").insert({
      email: email.trim(),
      name: name.trim() || null,
      note: note.trim() || null,
      source: "dashboard"
    });

    if (error) {
      setSubmitState("error");
      setMessage("Could not save your interest right now. Please try again.");
      return;
    }

    setSubmitState("success");
    setMessage("Thanks - you're on the beta list.");
    setEmail("");
    setName("");
    setNote("");
  }

  function closeDialog() {
    setOpen(false);
    if (submitState !== "success") {
      setSubmitState("idle");
      setMessage(null);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-9 items-center justify-center rounded-md border border-blue-200 bg-blue-600 px-4 text-xs font-black text-white transition hover:bg-blue-700"
      >
        Join Beta
      </button>

      {open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4 backdrop-blur-sm">
          <button type="button" aria-label="Close beta form" className="absolute inset-0 cursor-default" onClick={closeDialog} />
          <div className="relative w-full max-w-md rounded-lg border border-slate-200 bg-white p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-blue-700">Request Access</p>
                <h3 className="mt-1 text-xl font-black text-ink">Join Beta</h3>
                <p className="mt-2 text-sm font-semibold leading-6 text-muted">
                  Leave your email and a quick note so we know what would make this useful for you.
                </p>
              </div>
              <button
                type="button"
                onClick={closeDialog}
                className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 text-lg font-black text-slate-500 transition hover:border-blue-300 hover:text-blue-700"
              >
                x
              </button>
            </div>

            <form className="mt-4 space-y-3" onSubmit={(event) => void handleSubmit(event)}>
              <div>
                <label htmlFor="beta-email" className="text-xs font-black text-ink">
                  Email
                </label>
                <input
                  id="beta-email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  className="mt-1 h-11 w-full rounded-md border border-slate-200 px-3 text-sm font-semibold text-ink outline-none transition focus:border-blue-400"
                />
              </div>

              <div>
                <label htmlFor="beta-name" className="text-xs font-black text-ink">
                  Name
                </label>
                <input
                  id="beta-name"
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="mt-1 h-11 w-full rounded-md border border-slate-200 px-3 text-sm font-semibold text-ink outline-none transition focus:border-blue-400"
                />
              </div>

              <div>
                <label htmlFor="beta-note" className="text-xs font-black text-ink">
                  Note
                </label>
                <textarea
                  id="beta-note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="What would you want from this tool?"
                  rows={4}
                  className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-semibold text-ink outline-none transition focus:border-blue-400"
                />
              </div>

              {message ? (
                <p className={`text-sm font-semibold ${submitState === "success" ? "text-emerald-700" : "text-red-600"}`}>{message}</p>
              ) : null}

              <button
                type="submit"
                disabled={submitState === "submitting"}
                className="inline-flex h-11 w-full items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-black text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitState === "submitting" ? "Submitting..." : "Submit interest"}
              </button>
            </form>
          </div>
        </div>
      ) : null}
    </>
  );
}
