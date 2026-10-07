"use client";
import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getAuthClient } from "@/lib/auth";
import { deleteSavedAnalysis, getSavedAnalyses, type SavedAnalysis } from "@/lib/api";
import AnalysisResult from "./AnalysisResult";
import { Button } from "./ui";

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
  const [factorId, setFactorId] = useState("");
  const [qr, setQr] = useState("");
  const [secret, setSecret] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const auth = getAuthClient();
  const phoneEnabled = process.env.NEXT_PUBLIC_PHONE_AUTH_ENABLED === "true";
  const inputStyle = "w-full rounded border border-line bg-ink px-3 py-2 text-fg";

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
    }).catch((error) => { if (active) setMessage(error.message); });
    auth.auth.mfa.listFactors().then((factors) => {
      if (!active) return;
      const factor = factors.data?.totp.find((f) => f.status === "verified");
      if (factor) setFactorId(factor.id);
    }).catch((error) => { if (active) setMessage(error.message); });
    return () => { active = false; };
  }, [session, auth]);

  async function act(work: () => Promise<void>) {
    setBusy(true); setMessage("");
    try { await work(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Please try again."); }
    finally { setBusy(false); }
  }

  if (!auth) return <section className="plate p-6"><h1 className="text-2xl font-semibold">Account</h1>
    <p className="mt-3 text-fg-dim">Sign-in is being set up. Please try again later.</p></section>;

  return <div className="space-y-6">
    <section className="plate p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Your account</h1>
      {session ? <>
        <p className="text-fg-dim">Signed in as {session.user.email || session.user.phone}</p>
        <div className="flex gap-3 flex-wrap">
          <Button disabled={busy} onClick={() => act(async () => {
            const { error } = await auth.auth.signOut(); if (error) throw error;
            setAnalyses([]); setOpened(null); setFactorId(""); setQr(""); setSecret("");
          })}>Sign out</Button>
          <Button disabled={busy} onClick={() => act(async () => {
            const { error } = await auth.auth.linkIdentity({ provider: "google", options: { redirectTo: `${location.origin}/account` } });
            if (error) throw error;
          })}>Link Google account</Button>
        </div>
        <p className="text-xs text-fg-mute">Link verified sign-in methods to keep one account and one analysis history.</p>
      </> : <>
        <Button disabled={busy} onClick={() => act(async () => {
          const { error } = await auth.auth.signInWithOAuth({ provider: "google", options: { redirectTo: `${location.origin}/account` } });
          if (error) throw error;
        })}>Continue with Google</Button>
        <form className="space-y-3 max-w-md" onSubmit={(event) => { event.preventDefault(); void act(async () => {
          if (Date.now() < resendAt) return;
          const { error } = await auth.auth.signInWithOtp(channel === "email"
            ? { email: address.trim(), options: { emailRedirectTo: `${location.origin}/account` } }
            : { phone: address.trim() });
          if (error) throw error;
          setSent(true); setResendAt(Date.now() + 60000); setSeconds(60); setMessage("Code sent. Check your messages.");
        }); }}>
          {phoneEnabled && <label className="block text-sm">Sign-in method<select className={inputStyle} value={channel} onChange={(event) => {
            setChannel(event.target.value as "email" | "sms"); setSent(false); setCode(""); setAddress("");
          }}><option value="email">Email code</option><option value="sms">Mobile code</option></select></label>}
          <label className="block text-sm">{channel === "email" ? "Email address" : "Mobile number with country code"}
            <input required type={channel === "email" ? "email" : "tel"} autoComplete={channel === "email" ? "email" : "tel"}
              className={inputStyle} value={address} onChange={(event) => { setAddress(event.target.value); setSent(false); }} /></label>
          <Button disabled={busy || seconds > 0} type="submit">{seconds > 0 ? `Resend in ${seconds}s` : sent ? "Resend code" : "Send code"}</Button>
        </form>
        {sent && <form className="space-y-3 max-w-md" onSubmit={(event) => { event.preventDefault(); void act(async () => {
          const { error } = await auth.auth.verifyOtp(channel === "email" ? { email: address.trim(), token: code, type: "email" }
            : { phone: address.trim(), token: code, type: "sms" });
          if (error) throw error;
          setCode(""); setSent(false);
        }); }}><label className="block text-sm">Verification code<input required pattern="[0-9]{6}" maxLength={6} inputMode="numeric"
          autoComplete="one-time-code" className={inputStyle} value={code} onChange={(event) => setCode(event.target.value)} /></label>
          <Button disabled={busy} type="submit">Verify and sign in</Button></form>}
      </>}
      <p className="text-sm text-fg-dim" role="status">{message}</p>
    </section>

    {session && <section className="plate p-6 space-y-3">
      <h2 className="text-xl font-semibold">Authenticator verification</h2>
      {!factorId && <Button disabled={busy} onClick={() => act(async () => {
        const { data, error } = await auth.auth.mfa.enroll({ factorType: "totp", friendlyName: "NEW_X1" });
        if (error) throw error;
        const image = data.totp.qr_code;
        setFactorId(data.id); setQr(image.startsWith("data:") ? image.slice(image.indexOf(",") + 1) : image); setSecret(data.totp.secret);
      })}>Set up Google Authenticator</Button>}
      {qr && <div>
        {/* Supabase supplies this QR; a data URI avoids inserting SVG markup into the DOM. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(qr)}`} width={200} height={200} alt="Scan with your authenticator" />
        <p className="text-sm break-all">Manual setup key: {secret}</p>
      </div>}
      {factorId && <form className="space-y-3 max-w-md" onSubmit={(event) => { event.preventDefault(); void act(async () => {
        const { error } = await auth.auth.mfa.challengeAndVerify({ factorId, code: mfaCode });
        if (error) throw error;
        setQr(""); setSecret(""); setMfaCode(""); setMessage("Authenticator verified.");
      }); }}><label className="block text-sm">Authenticator code<input required pattern="[0-9]{6}" maxLength={6}
        inputMode="numeric" autoComplete="one-time-code" className={inputStyle} value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} /></label>
        <Button disabled={busy} type="submit">Verify authenticator</Button></form>}
    </section>}

    {session && <section className="plate p-6 space-y-3">
      <h2 className="text-xl font-semibold">Saved analyses</h2>
      <Button disabled={busy} onClick={() => act(async () => setAnalyses((await getSavedAnalyses()).analyses))}>Refresh history</Button>
      {!analyses.length && <p className="text-fg-dim">Save an analysis after generating your team.</p>}
      {analyses.map((analysis) => <div key={analysis.id} className="border-t border-line-soft py-3 flex gap-3 flex-wrap items-center">
        <span className="flex-1">{analysis.payload.title}</span>
        <Button onClick={() => setOpened(analysis)}>View</Button>
        <Button disabled={busy} onClick={() => act(async () => {
          await deleteSavedAnalysis(analysis.id); setAnalyses((items) => items.filter((item) => item.id !== analysis.id));
          if (opened?.id === analysis.id) setOpened(null);
        })}>Delete</Button>
      </div>)}
    </section>}
    {opened && <AnalysisResult key={opened.id} result={opened.payload.result} />}
  </div>;
}
