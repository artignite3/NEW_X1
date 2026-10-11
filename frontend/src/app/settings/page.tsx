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

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 md:py-10">
        <section className="plate p-4 sm:p-6 space-y-4">
          <h1 className="text-xl sm:text-2xl font-semibold">Backend connection</h1>
          <p className="text-xs sm:text-sm text-fg-dim leading-relaxed">
            Paste the HTTPS address shown by your backend tunnel. Update it here whenever the tunnel address changes.
          </p>
          <label className="block text-sm text-fg-dim" htmlFor="api-address">Backend address</label>
          <input
            id="api-address"
            type="url"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            placeholder="https://example.trycloudflare.com"
            className="field w-full px-3 py-2.5 text-sm text-fg"
          />
          <Button onClick={connect} className="w-full sm:w-auto">Save and test connection</Button>
          {message && <p role="status" className="text-xs sm:text-sm text-fg-dim break-words">{message}</p>}
          <p className="text-xs text-fg-mute leading-relaxed">
            This address is saved only in this browser. The backend is available while your laptop and tunnel are running.
          </p>
        </section>
      </main>
    </div>
  );
}
