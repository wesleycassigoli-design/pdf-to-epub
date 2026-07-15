"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAdminUsers, approveUser, revokeUser, promoteUser, getErrorMessage, type User } from "@/lib/api";
import { formatDate, cn, USER_STATUS_LABEL, USER_STATUS_COLOR } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2, AlertCircle, ShieldCheck, ShieldX, ShieldPlus } from "lucide-react";
import { toast } from "sonner";

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();

  const { data: users, isLoading, isError } = useQuery({
    queryKey: ["admin-users"],
    queryFn: fetchAdminUsers,
    enabled: !!currentUser?.is_admin,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-users"] });

  const approveMutation = useMutation({
    mutationFn: approveUser,
    onSuccess: () => { toast.success("Cadastro aprovado"); invalidate(); },
    onError: (err) => toast.error(getErrorMessage(err, "Não foi possível aprovar")),
  });
  const revokeMutation = useMutation({
    mutationFn: revokeUser,
    onSuccess: () => { toast.success("Acesso revogado"); invalidate(); },
    onError: (err) => toast.error(getErrorMessage(err, "Não foi possível revogar")),
  });
  const promoteMutation = useMutation({
    mutationFn: promoteUser,
    onSuccess: () => { toast.success("Usuário promovido a admin"); invalidate(); },
    onError: (err) => toast.error(getErrorMessage(err, "Não foi possível promover")),
  });

  if (!currentUser?.is_admin) {
    return (
      <div className="p-8 flex items-center gap-2 text-red-600 text-sm">
        <AlertCircle className="h-4 w-4" />
        Acesso restrito a administradores
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-ink">Administração</h1>
        <p className="text-sm text-gray-500 mt-1">Gerencie cadastros e permissões de acesso</p>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-gray-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Carregando...
        </div>
      )}

      {isError && (
        <div className="flex items-center gap-2 text-red-600 text-sm">
          <AlertCircle className="h-4 w-4" />
          Erro ao carregar usuários
        </div>
      )}

      {users && (
        <div className="rounded-xl border border-surface-border bg-surface-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border text-left text-xs text-gray-500 uppercase tracking-wider">
                <th className="px-5 py-3 font-medium">Nome</th>
                <th className="px-5 py-3 font-medium">E-mail</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Cadastro</th>
                <th className="px-5 py-3 font-medium">Último acesso</th>
                <th className="px-5 py-3 font-medium text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u: User) => (
                <tr key={u.id} className="border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors">
                  <td className="px-5 py-3 text-ink">
                    {u.full_name}
                    {u.is_admin && (
                      <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium bg-secondary/10 text-secondary">
                        Admin
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-gray-500">{u.email}</td>
                  <td className="px-5 py-3">
                    <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", USER_STATUS_COLOR[u.status])}>
                      {USER_STATUS_LABEL[u.status] || u.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-500 text-xs">{formatDate(u.created_at)}</td>
                  <td className="px-5 py-3 text-gray-500 text-xs">
                    {u.last_login_at ? formatDate(u.last_login_at) : "—"}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-1.5">
                      {u.status === "pending" && (
                        <button
                          onClick={() => approveMutation.mutate(u.id)}
                          disabled={approveMutation.isPending}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium hover:bg-emerald-100 transition-colors disabled:opacity-50"
                        >
                          <ShieldCheck className="h-3.5 w-3.5" />
                          Aprovar
                        </button>
                      )}
                      {u.status === "approved" && (
                        <button
                          onClick={() => revokeMutation.mutate(u.id)}
                          disabled={revokeMutation.isPending}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-50 text-red-700 text-xs font-medium hover:bg-red-100 transition-colors disabled:opacity-50"
                        >
                          <ShieldX className="h-3.5 w-3.5" />
                          Revogar
                        </button>
                      )}
                      {!u.is_admin && (
                        <button
                          onClick={() => promoteMutation.mutate(u.id)}
                          disabled={promoteMutation.isPending}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-secondary/10 text-secondary text-xs font-medium hover:bg-secondary/20 transition-colors disabled:opacity-50"
                        >
                          <ShieldPlus className="h-3.5 w-3.5" />
                          Promover
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
