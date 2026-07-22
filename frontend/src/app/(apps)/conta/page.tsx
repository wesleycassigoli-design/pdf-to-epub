"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { changePassword, getErrorMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { ArrowLeft, Loader2, KeyRound } from "lucide-react";
import { toast } from "sonner";

export default function ContaPage() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: () => changePassword(currentPassword, newPassword),
    onSuccess: () => {
      toast.success("Senha alterada com sucesso");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setError("");
    },
    onError: (err) => setError(getErrorMessage(err, "Não foi possível alterar a senha")),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (newPassword.length < 8) {
      setError("A nova senha precisa ter pelo menos 8 caracteres");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("A confirmação não bate com a nova senha");
      return;
    }
    mutation.mutate();
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16 bg-surface">
      <div className="w-full max-w-sm">
        <Link
          href="/apps"
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-ink transition-colors mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Aplicativos
        </Link>

        <div className="rounded-2xl border border-surface-border bg-surface-card p-6">
          <div className="flex items-center gap-2 mb-1">
            <KeyRound className="h-4 w-4 text-gray-400" />
            <h1 className="text-base font-display font-semibold text-ink">Trocar senha</h1>
          </div>
          <p className="text-xs text-gray-500 mb-6">{user?.email}</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1.5">Senha atual</label>
              <input
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full rounded-lg bg-surface border border-surface-border px-3 py-2 text-sm text-ink focus:border-brand-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1.5">Nova senha</label>
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded-lg bg-surface border border-surface-border px-3 py-2 text-sm text-ink focus:border-brand-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1.5">Confirmar nova senha</label>
              <input
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full rounded-lg bg-surface border border-surface-border px-3 py-2 text-sm text-ink focus:border-brand-500 outline-none"
              />
            </div>

            {error && <p className="text-xs text-red-600">{error}</p>}

            <button
              type="submit"
              disabled={mutation.isPending}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white text-sm font-medium py-2.5 transition-colors"
            >
              {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Salvar nova senha
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
