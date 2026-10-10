"use client";

import { useEffect, useState } from "react";
import AppNav from "@/components/AppNav";
import { getApiBase, getHealth, saveApiBase } from "@/lib/api";
import { Button } from "@/components/ui";

export default function SettingsPage() {
  const [address, setAddress] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    queueMicrotask(() => {
      try { setAddress(getApiBase()); } catch { /* The first tunnel URL is entered here. */ }
    });
  }, []);

  async function connect() {
    try {
      const origin = saveApiBase(address);
      const health = await getHealth();
      setAddress(origin);
      setMessage(`Connected to backend: ${health.status}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not connect to backend.");
    }
  }

  return <>
    <AppNav />
    <main className="w-full max-w-3xl mx-auto px-5 py-8">
      <section className="plate p-6 space-y-4">
        <h1 className="text-2xl font-semibold">Backend connection</h1>
        <p className="text-fg-dim">Paste the HTTPS address shown by your backend tunnel. Update it here whenever the tunnel address changes.</p>
        <label className="block text-sm text-fg-dim" htmlFor="api-address">Backend address</label>
        <input id="api-address" type="url" value={address} onChange={(event) => setAddress(event.target.value)}
          placeholder="https://example.trycloudflare.com" className="w-full rounded border border-line bg-ink px-3 py-2 text-fg" />
        <Button onClick={connect}>Save and test connection</Button>
        {message && <p role="status" className="text-sm text-fg-dim">{message}</p>}
        <p className="text-xs text-fg-mute">This address is saved only in this browser. The backend is available while your laptop and tunnel are running.</p>
      </section>
    </main>
  </>;
}
