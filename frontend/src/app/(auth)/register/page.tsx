"use client";

import { useState } from "react";
import Link from "next/link";
import { registerUser, getErrorMessage } from "@/lib/api";
import { Loader2, CheckCircle2 } from "lucide-react";

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("As senhas não coincidem");
      return;
    }
    if (!privacyAccepted) {
      setError("É necessário aceitar a Política de Privacidade");
      return;
    }

    setLoading(true);
    try {
      const resp = await registerUser({
        full_name: fullName,
        email,
        password,
        privacy_accepted: privacyAccepted,
      });
      setSuccessMessage(resp.message);
    } catch (err) {
      setError(getErrorMessage(err, "Não foi possível concluir o cadastro"));
    } finally {
      setLoading(false);
    }
  };

  if (successMessage) {
    return (
      <div className="text-center">
        <CheckCircle2 className="h-10 w-10 text-emerald-600 mx-auto mb-3" />
        <p className="text-sm text-ink mb-4">{successMessage}</p>
        <Link href="/login" className="text-brand-500 hover:text-brand-600 text-sm hover:underline">
          Ir para o login
        </Link>
      </div>
    );
  }

  return (
    <>
      <h1 className="text-xl font-display font-semibold text-ink mb-1">Criar conta</h1>
      <p className="text-sm text-gray-500 mb-6">Use seu e-mail corporativo @afya.com.br</p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Nome completo</label>
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full rounded-lg bg-surface border border-surface-border px-3 py-2 text-sm text-ink focus:border-brand-500 outline-none"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">E-mail</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="voce@afya.com.br"
            className="w-full rounded-lg bg-surface border border-surface-border px-3 py-2 text-sm text-ink focus:border-brand-500 outline-none"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Senha</label>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg bg-surface border border-surface-border px-3 py-2 text-sm text-ink focus:border-brand-500 outline-none"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Confirmar senha</label>
          <input
            type="password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full rounded-lg bg-surface border border-surface-border px-3 py-2 text-sm text-ink focus:border-brand-500 outline-none"
          />
        </div>

        <label className="flex items-start gap-2 text-xs text-gray-500">
          <input
            type="checkbox"
            checked={privacyAccepted}
            onChange={(e) => setPrivacyAccepted(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            Li e aceito a{" "}
            <Link href="/privacidade" target="_blank" className="text-brand-500 hover:text-brand-600 hover:underline">
              Política de Privacidade
            </Link>
          </span>
        </label>

        {error && <p className="text-xs text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading || !privacyAccepted}
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-brand-500 hover:bg-brand-600 disabled:opacity-40 text-white text-sm font-medium py-2.5 transition-colors"
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          Cadastrar
        </button>
      </form>

      <p className="text-xs text-gray-500 mt-6 text-center">
        Já tem conta?{" "}
        <Link href="/login" className="text-brand-500 hover:text-brand-600 hover:underline">
          Entrar
        </Link>
      </p>
    </>
  );
}
