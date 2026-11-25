import AppNav from "@/components/AppNav";
import AccountPanel from "@/components/AccountPanel";
import { SiteFooter } from "@/components/ui";

export default function Account() {
  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        <AccountPanel />
      </main>
      <SiteFooter />
    </div>
  );
}
