"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchStatus, type StatusResponse } from "@/lib/api";

/**
 * Faz polling do status de conversão enquanto não estiver concluído/erro.
 * Para automaticamente quando status = done ou error.
 */
export function useConversionStatus(bookId: string | null, enabled = true) {
  return useQuery<StatusResponse>({
    queryKey: ["status", bookId],
    queryFn: () => fetchStatus(bookId!),
    enabled: !!bookId && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.book_status;
      if (status === "done" || status === "error") return false;
      return 2000; // polling a cada 2s
    },
    staleTime: 0,
  });
}
