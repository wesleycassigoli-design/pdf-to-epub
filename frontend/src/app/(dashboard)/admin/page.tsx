"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchAdminUsers, approveUser, revokeUser, promoteUser, demoteUser, deleteUser, updateAppAccess,
  getErrorMessage, type User,
} from "@/lib/api";
import { formatDate, cn, USER_STATUS_LABEL, USER_STATUS_COLOR } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2, AlertCircle, AlertTriangle, ShieldCheck, ShieldX, ShieldPlus, ShieldMinus, Trash2 } from "lucide-react";
import { toast } from "sonner";

const APP_LABELS: Record<string, string> = {
  epub: "Gerador de EPUB",
  thumbs: "Gerador de Thumbs",
};

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const [showDeleted, setShowDeleted] = useState(false);
  const [userPendingDelete, setUserPendingDelete] = useState<User | null>(null);

  const { data: users, isLoading, isError } = useQuery({
    queryKey: ["admin-users", showDeleted],
    queryFn: () => fetchAdminUsers(showDeleted),
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
  const demoteMutation = useMutation({
    mutationFn: demoteUser,
    onSuccess: () => { toast.success("Admin removido"); invalidate(); },
    onError: (err) => toast.error(getErrorMessage(err, "Não foi possível remover admin")),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => { toast.success("Usuário excluído"); setUserPendingDelete(null); invalidate(); },
    onError: (err) => { toast.error(getErrorMessage(err, "Não foi possível excluir")); setUserPendingDelete(null); },
  });
  const appAccessMutation = useMutation({
    mutationFn: ({ userId, access }: { userId: string; access: { epub: boolean; thumbs: boolean } }) =>
      updateAppAccess(userId, access),
    onSuccess: () => { toast.success("Acesso atualizado"); invalidate(); },
    onError: (err) => toast.error(getErrorMessage(err, "Não foi possível atualizar o acesso")),
  });

  const toggleAppAccess = (u: User, appKey: "epub" | "thumbs") => {
    const current = { epub: u.app_access.includes("epub"), thumbs: u.app_access.includes("thumbs") };
    current[appKey] = !current[appKey];
    appAccessMutation.mutate({ userId: u.id, access: current });
  };

  if (!currentUser?.is_admin) {
    return (
      <div className="p-8 flex items-center gap-2 text-red-600 text-sm">
        <AlertCircle className="h-4 w-4" />
        Acesso restrito a administradores
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Administração</h1>
          <p className="text-sm text-gray-500 mt-1">Gerencie cadastros e permissões de acesso</p>
        </div>
        <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer">
          <input
            type="checkbox"
            checked={showDeleted}
            onChange={(e) => setShowDeleted(e.target.checked)}
            className="rounded border-surface-border"
          />
          Mostrar excluídos
        </label>
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
        <div className="rounded-xl border border-surface-border bg-surface-card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border text-left text-xs text-gray-500 uppercase tracking-wider">
                <th className="px-5 py-3 font-medium">Nome</th>
                <th className="px-5 py-3 font-medium">E-mail</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Acesso</th>
                <th className="px-5 py-3 font-medium">Cadastro</th>
                <th className="px-5 py-3 font-medium">Último acesso</th>
                <th className="px-5 py-3 font-medium text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u: User) => {
                const isDeleted = !!u.deleted_at;
                return (
                  <tr key={u.id} className={cn(
                    "border-b border-surface-border last:border-0 hover:bg-surface-hover transition-colors",
                    isDeleted && "opacity-60"
                  )}>
                    <td className="px-5 py-3 text-ink">
                      {u.full_name}
                      {u.is_admin && (
                        <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium bg-secondary/10 text-secondary">
                          Admin
                        </span>
                      )}
                      {isDeleted && (
                        <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-200 text-gray-600">
                          Excluído
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-gray-500">
                      {u.email}
                      {!isDeleted && u.reused_deleted_email && (
                        <span
                          title="Este e-mail teve uma conta excluída anteriormente. Se for um recadastro, a senha é diferente da conta antiga."
                          className="ml-1.5 inline-flex items-center text-amber-500 cursor-help"
                        >
                          <AlertTriangle className="h-3.5 w-3.5" />
                        </span>
                      )}
                      {isDeleted && (
                        <p className="text-[11px] text-gray-400 mt-0.5">Original: {u.original_email || "—"}</p>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", USER_STATUS_COLOR[u.status])}>
                        {USER_STATUS_LABEL[u.status] || u.status}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      {u.is_admin ? (
                        <span className="text-xs text-gray-400">Todos (admin)</span>
                      ) : isDeleted ? (
                        <span className="text-xs text-gray-400">—</span>
                      ) : (
                        <div className="flex flex-col gap-1">
                          {(["epub", "thumbs"] as const).map((appKey) => (
                            <label key={appKey} className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={u.app_access.includes(appKey)}
                                onChange={() => toggleAppAccess(u, appKey)}
                                disabled={appAccessMutation.isPending}
                                className="rounded border-surface-border"
                              />
                              {APP_LABELS[appKey]}
                            </label>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3 text-gray-500 text-xs">{formatDate(u.created_at)}</td>
                    <td className="px-5 py-3 text-gray-500 text-xs">
                      {u.last_login_at ? formatDate(u.last_login_at) : "—"}
                    </td>
                    <td className="px-5 py-3">
                      {!isDeleted && (
                        <div className="flex items-center justify-end gap-1.5 flex-wrap">
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
                          {u.is_admin && (
                            <button
                              onClick={() => demoteMutation.mutate(u.id)}
                              disabled={demoteMutation.isPending}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-hover text-gray-600 text-xs font-medium hover:bg-surface-border transition-colors disabled:opacity-50"
                            >
                              <ShieldMinus className="h-3.5 w-3.5" />
                              Remover admin
                            </button>
                          )}
                          <button
                            onClick={() => setUserPendingDelete(u)}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-50 text-red-700 text-xs font-medium hover:bg-red-100 transition-colors"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            Excluir
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {userPendingDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-sm rounded-2xl border border-surface-border bg-surface-card p-6 shadow-lg">
            <h2 className="text-base font-semibold text-ink mb-2">Excluir usuário?</h2>
            <p className="text-sm text-gray-500 mb-6">
              Tem certeza que deseja excluir <strong className="text-ink">{userPendingDelete.full_name}</strong>{" "}
              ({userPendingDelete.email})? O login será bloqueado imediatamente. O histórico de conversões
              permanece, e o e-mail fica livre pra um novo cadastro.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setUserPendingDelete(null)}
                disabled={deleteMutation.isPending}
                className="px-3 py-1.5 rounded-lg bg-surface-hover text-gray-600 text-sm font-medium hover:bg-surface-border transition-colors disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={() => deleteMutation.mutate(userPendingDelete.id)}
                disabled={deleteMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleteMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
