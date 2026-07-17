"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { getErrorMessage } from "@/lib/api";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/apps");
    } catch (err) {
      setError(getErrorMessage(err, "Não foi possível fazer login"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h1 className="text-xl font-display font-semibold text-ink mb-1">Entrar</h1>
      <p className="text-sm text-gray-500 mb-6">Acesse com seu e-mail @afya.com.br</p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">E-mail</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg bg-surface border border-surface-border px-3 py-2 text-sm text-ink focus:border-brand-500 outline-none"
            placeholder="voce@afya.com.br"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Senha</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg bg-surface border border-surface-border px-3 py-2 text-sm text-ink focus:border-brand-500 outline-none"
          />
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white text-sm font-medium py-2.5 transition-colors"
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          Entrar
        </button>
      </form>

      <p className="text-xs text-gray-500 mt-6 text-center">
        Ainda não tem conta?{" "}
        <Link href="/register" className="text-brand-500 hover:text-brand-600 hover:underline">
          Cadastre-se
        </Link>
      </p>
    </>
  );
}
