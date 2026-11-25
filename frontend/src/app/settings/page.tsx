"use client";

import { useEffect, useState } from "react";
import AppNav from "@/components/AppNav";
import {
  clearManualApiBase,
  getApiBase,
  getDiscoveredApiBase,
  getHealth,
  getManualApiBase,
  saveApiBase,
} from "@/lib/api";
import { Button, PageHeader, SiteFooter } from "@/components/ui";

export default function SettingsPage() {
  const [address, setAddress] = useState("");
  const [manual, setManual] = useState<string | null>(null);
  const [automatic, setAutomatic] = useState<string | null>(null);
  const [active, setActive] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const read = () => {
      setManual(getManualApiBase());
      setAutomatic(getDiscoveredApiBase());
      try { setActive(getApiBase()); } catch { setActive(""); }
    };
    queueMicrotask(read);
    window.addEventListener("new_x1_api_base_changed", read);
    return () => window.removeEventListener("new_x1_api_base_changed", read);
  }, []);

  async function test(label: string) {
    try {
      const health = await getHealth();
      setMessage(`${label}: connected, server status ${health.status}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not reach the analysis server");
    }
  }

  async function connect() {
    try {
      const origin = saveApiBase(address);
      setAddress(origin);
      await test("Manual address");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not reach the analysis server");
    }
  }

  async function useAutomatic() {
    clearManualApiBase();
    setAddress("");
    await test("Automatic address");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 space-y-8">
        <PageHeader title="Settings" />
        <section className="plate p-6">
          <h2 className="text-base font-medium text-fg">Analysis server</h2>
          <p className="text-sm text-fg-dim mt-2 leading-relaxed">
            The site finds the server automatically while it is running. A manual address is only needed for testing.
          </p>

          <dl className="grid sm:grid-cols-[160px_1fr] gap-x-6 gap-y-3 mt-6 text-sm">
            <dt className="text-fg-mute">In use</dt>
            <dd className="mono-value text-fg break-all">{active || "None, the server is offline"}</dd>
            <dt className="text-fg-mute">Automatic</dt>
            <dd className="mono-value text-fg-dim break-all">{automatic ?? "Not published"}</dd>
            <dt className="text-fg-mute">Manual override</dt>
            <dd className="mono-value text-fg-dim break-all">{manual ?? "None"}</dd>
          </dl>

          <label className="block text-sm text-fg-dim mt-8 mb-2" htmlFor="api-address">Manual address</label>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              id="api-address"
              type="url"
              value={address}
              onChange={(event) => setAddress(event.target.value)}
              placeholder="https://example.trycloudflare.com"
              className="field flex-1 h-10 px-3 text-sm text-fg mono-value placeholder:text-fg-mute"
            />
            <Button onClick={connect} className="h-10">Save and test</Button>
          </div>
          {manual && (
            <Button variant="outline" onClick={useAutomatic} className="mt-3">Use automatic address</Button>
          )}
          {message && <p role="status" className="text-sm text-fg-dim mt-4 break-words">{message}</p>}
          <p className="text-xs text-fg-mute mt-6">A manual address is saved only in this browser</p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
