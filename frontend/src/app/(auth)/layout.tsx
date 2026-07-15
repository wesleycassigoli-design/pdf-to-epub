export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <img src="/logo-afya.svg" alt="Afya" className="h-10 w-auto mb-8" />
      <div className="w-full max-w-sm rounded-2xl border border-surface-border bg-surface-card p-8 shadow-sm">
        {children}
      </div>
    </div>
  );
}
