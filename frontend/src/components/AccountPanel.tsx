"use client";
import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getAuthClient } from "@/lib/auth";
import { deleteSavedAnalysis, getSavedAnalyses, type SavedAnalysis } from "@/lib/api";
import AnalysisResult from "./AnalysisResult";
import { Button, PageHeader, Skeleton } from "./ui";

export default function AccountPanel() {
  const [session, setSession] = useState<Session | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [channel, setChannel] = useState<"email" | "sms">("email");
  const [address, setAddress] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [resendAt, setResendAt] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const [analyses, setAnalyses] = useState<SavedAnalysis[]>([]);
  const [opened, setOpened] = useState<SavedAnalysis | null>(null);
  const [analysesLoading, setAnalysesLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState("");
  const [factorId, setFactorId] = useState("");
  const [unfinishedFactorId, setUnfinishedFactorId] = useState("");
  const [qr, setQr] = useState("");
  const [secret, setSecret] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const auth = getAuthClient();
  const phoneEnabled = process.env.NEXT_PUBLIC_PHONE_AUTH_ENABLED === "true";
  const inputStyle = "field w-full h-10 px-3 text-sm text-fg mt-2";

  useEffect(() => {
    if (!auth) return;
    let active = true;
    auth.auth.getSession().then(({ data, error }) => {
      if (!active) return;
      if (error) setMessage(error.message);
      setSession(data.session);
    });
    const { data } = auth.auth.onAuthStateChange((_event, current) => setSession(current));
    return () => { active = false; data.subscription.unsubscribe(); };
  }, [auth]);

  useEffect(() => {
    const timer = setInterval(() => setSeconds(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000))), 1000);
    return () => clearInterval(timer);
  }, [resendAt]);

  useEffect(() => {
    if (!session || !auth) return;
    let active = true;
    getSavedAnalyses().then((saved) => {
      if (!active) return;
      setAnalyses(saved.analyses);
    }).catch((error) => { if (active) setMessage(error.message); })
      .finally(() => { if (active) setAnalysesLoading(false); });
    auth.auth.mfa.listFactors().then((factors) => {
      if (!active) return;
      const totp = factors.data?.totp ?? [];
      const verified = totp.find((f) => f.status === "verified");
      const unfinished = totp.find((f) => f.status !== "verified" && f.friendly_name?.startsWith("NEW_X1"));
      setFactorId(verified?.id ?? "");
      setUnfinishedFactorId(unfinished?.id ?? "");
    }).catch((error) => { if (active) setMessage(error.message); });
    return () => { active = false; };
  }, [session, auth]);

  async function act(work: () => Promise<void>) {
    setBusy(true); setMessage("");
    try { await work(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Please try again."); }
    finally { setBusy(false); }
  }

  async function startAuthenticatorEnrollment() {
    // Supabase keeps an abandoned, unverified factor name reserved. A unique name
    // allows a user to safely recover from an interrupted enrollment.
    const friendlyName = `NEW_X1-${crypto.randomUUID().slice(0, 8)}`;
    const { data, error } = await auth!.auth.mfa.enroll({ factorType: "totp", friendlyName });
    if (error) throw error;
    const image = data.totp.qr_code;
    setFactorId(data.id); setQr(image.startsWith("data:") ? image.slice(image.indexOf(",") + 1) : image); setSecret(data.totp.secret);
  }

  if (!auth) return <div className="space-y-8"><PageHeader title="Account" />
    <section className="plate p-6"><p className="text-sm text-fg-dim">Sign-in is not available yet. Try again later</p></section></div>;

  return <div className="space-y-8">
    <PageHeader title="Account" />
    <section className="plate p-6 space-y-4">
      <h2 className="text-base font-medium text-fg">{session ? "Signed in" : "Sign in"}</h2>
      {session ? <>
        <p className="text-sm text-fg-dim break-all">{session.user.email || session.user.phone}</p>
        <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
          <Button className="w-full sm:w-auto" disabled={busy} onClick={() => act(async () => {
            const { error } = await auth.auth.signOut(); if (error) throw error;
            setAnalyses([]); setOpened(null); setFactorId(""); setQr(""); setSecret("");
          })}>Sign out</Button>
          <Button variant="outline" className="w-full sm:w-auto" disabled={busy} onClick={() => act(async () => {
            const { error } = await auth.auth.linkIdentity({ provider: "google", options: { redirectTo: `${location.origin}/account` } });
            if (error) throw error;
          })}>Link Google account</Button>
        </div>
        <p className="text-xs text-fg-mute">Link sign-in methods to keep one account and one saved history</p>
      </> : <>
        <Button className="w-full sm:w-auto" disabled={busy} onClick={() => act(async () => {
          const { error } = await auth.auth.signInWithOAuth({ provider: "google", options: { redirectTo: `${location.origin}/account` } });
          if (error) throw error;
        })}>Continue with Google</Button>
        <form className="space-y-3 max-w-md" onSubmit={(event) => { event.preventDefault(); void act(async () => {
          if (Date.now() < resendAt) return;
          const { error } = await auth.auth.signInWithOtp(channel === "email"
            ? { email: address.trim(), options: { emailRedirectTo: `${location.origin}/account` } }
            : { phone: address.trim() });
          if (error) throw error;
          setSent(true); setResendAt(Date.now() + 60000); setSeconds(60); setMessage("Code sent, check your inbox");
        }); }}>
          {phoneEnabled && <label className="block text-sm text-fg-dim">Sign-in method<select className={inputStyle} value={channel} onChange={(event) => {
            setChannel(event.target.value as "email" | "sms"); setSent(false); setCode(""); setAddress("");
          }}><option value="email">Email code</option><option value="sms">Mobile code</option></select></label>}
          <label className="block text-sm text-fg-dim">{channel === "email" ? "Email address" : "Mobile number with country code"}
            <input required type={channel === "email" ? "email" : "tel"} autoComplete={channel === "email" ? "email" : "tel"}
              className={inputStyle} value={address} onChange={(event) => { setAddress(event.target.value); setSent(false); }} /></label>
          <Button className="w-full sm:w-auto" disabled={busy || seconds > 0} type="submit">{seconds > 0 ? `Resend in ${seconds}s` : sent ? "Resend code" : "Send code"}</Button>
        </form>
        {sent && <form className="space-y-3 max-w-md" onSubmit={(event) => { event.preventDefault(); void act(async () => {
          const { error } = await auth.auth.verifyOtp(channel === "email" ? { email: address.trim(), token: code, type: "email" }
            : { phone: address.trim(), token: code, type: "sms" });
          if (error) throw error;
          setCode(""); setSent(false);
        }); }}><label className="block text-sm text-fg-dim">Verification code<input required pattern="[0-9]{6,8}" maxLength={8} inputMode="numeric"
          autoComplete="one-time-code" className={inputStyle} value={code} onChange={(event) => setCode(event.target.value)} /></label>
          <Button className="w-full sm:w-auto" disabled={busy} type="submit">Verify and sign in</Button></form>}
      </>}
      {message && <p className="text-sm text-fg-dim break-words" role="status">{message}</p>}
    </section>

    {session && <section className="plate p-6 space-y-4">
      <h2 className="text-base font-medium text-fg">Two-step verification</h2>
      {!factorId && !unfinishedFactorId && <Button className="w-full sm:w-auto" disabled={busy} onClick={() => act(startAuthenticatorEnrollment)}>Set up Google Authenticator</Button>}
      {!factorId && unfinishedFactorId && <div className="space-y-3">
        <p className="text-sm text-fg-dim">An earlier authenticator setup was not finished. Restart it to get a new QR code</p>
        <Button className="w-full sm:w-auto" disabled={busy} onClick={() => act(async () => {
          const { error: removeError } = await auth.auth.mfa.unenroll({ factorId: unfinishedFactorId });
          if (removeError) throw removeError;
          setUnfinishedFactorId("");
          await startAuthenticatorEnrollment();
        })}>Restart authenticator setup</Button>
      </div>}
      {qr && <div className="space-y-2">
        {/* Supabase supplies this QR; a data URI avoids inserting SVG markup into the DOM. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(qr)}`} width={200} height={200} alt="Scan with your authenticator" className="max-w-full h-auto rounded-lg bg-white p-2" />
        <p className="text-sm break-all text-fg-dim">Setup key <span className="mono-value text-fg">{secret}</span></p>
      </div>}
      {factorId && <form className="space-y-3 max-w-md" onSubmit={(event) => { event.preventDefault(); void act(async () => {
        const { error } = await auth.auth.mfa.challengeAndVerify({ factorId, code: mfaCode });
        if (error) throw error;
        setQr(""); setSecret(""); setMfaCode(""); setMessage("Authenticator verified");
      }); }}><label className="block text-sm text-fg-dim">Authenticator code<input required pattern="[0-9]{6}" maxLength={6}
        inputMode="numeric" autoComplete="one-time-code" className={inputStyle} value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} /></label>
        <Button className="w-full sm:w-auto" disabled={busy} type="submit">Verify authenticator</Button></form>}
    </section>}

    {session && <section className="plate p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h2 className="text-base font-medium text-fg">Saved analyses</h2>
        <Button variant="outline" className="w-full sm:w-auto" disabled={busy} onClick={() => act(async () => setAnalyses((await getSavedAnalyses()).analyses))}>Refresh</Button>
      </div>
      {analysesLoading && <div className="space-y-3" aria-busy aria-label="Loading saved analyses">
        <Skeleton className="h-9 w-full" /><Skeleton className="h-9 w-full" />
      </div>}
      {!analysesLoading && !analyses.length && <p className="text-sm text-fg-dim">Nothing saved yet. Use Save analysis on any team selection</p>}
      {analyses.map((analysis) => <div key={analysis.id} className="border-t border-line-soft pt-4 flex flex-col sm:flex-row gap-3 sm:items-center">
        <span className="flex-1 text-sm text-fg break-words min-w-0">{analysis.payload.title}</span>
        {confirmDelete === analysis.id ? <div className="flex items-center gap-2 shrink-0" role="group" aria-label="Confirm delete">
          <span className="text-sm text-fg-dim">Delete for good?</span>
          <Button variant="ghost" onClick={() => setConfirmDelete("")}>Keep</Button>
          <Button variant="danger" disabled={busy} onClick={() => act(async () => {
            await deleteSavedAnalysis(analysis.id); setAnalyses((items) => items.filter((item) => item.id !== analysis.id));
            if (opened?.id === analysis.id) setOpened(null);
            setConfirmDelete("");
          })}>Delete</Button>
        </div> : <div className="flex items-center gap-2 shrink-0">
          <Button variant="outline" className="flex-1 sm:flex-initial" onClick={() => setOpened(analysis)}>View</Button>
          <Button variant="danger" className="flex-1 sm:flex-initial" disabled={busy} onClick={() => setConfirmDelete(analysis.id)}>Delete</Button>
        </div>}
      </div>)}
    </section>}
    {opened && <AnalysisResult key={opened.id} result={opened.payload.result} />}
  </div>;
}
