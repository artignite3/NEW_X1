import AppNav from "@/components/AppNav";
import AccountPanel from "@/components/AccountPanel";

export default function Account() {
  return (
    <div className="min-h-screen flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 md:py-10">
        <AccountPanel />
      </main>
    </div>
  );
}
