const DIAS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
export const DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

export function dataCurta(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number);
  const dt = new Date(a, m - 1, d);
  return `${DIAS[dt.getDay()]} ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
}

export function dataHora(iso: string | null): string {
  if (!iso) return "—";
  const dt = new Date(iso);
  return dt.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function hojeIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function somarDias(iso: string, n: number): string {
  const [a, m, d] = iso.split("-").map(Number);
  const dt = new Date(a, m - 1, d + n);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

export const STATUS: Record<string, { rotulo: string; cor: string }> = {
  AGUARDANDO_APROVACAO: { rotulo: "Aguardando aprovação", cor: "bg-amber-100 text-amber-800" },
  AGENDADO: { rotulo: "Agendado", cor: "bg-sky-100 text-sky-800" },
  CONFIRMADO: { rotulo: "Confirmado", cor: "bg-indigo-100 text-indigo-800" },
  COMPARECEU: { rotulo: "Compareceu", cor: "bg-emerald-100 text-emerald-800" },
  FALTOU: { rotulo: "Faltou", cor: "bg-rose-100 text-rose-800" },
  CANCELADO: { rotulo: "Cancelado", cor: "bg-slate-200 text-slate-600" },
  REMARCADO: { rotulo: "Remarcado", cor: "bg-slate-200 text-slate-600" },
  BOT: { rotulo: "Bot", cor: "bg-marca-100 text-marca-700" },
  AGUARDANDO_HUMANO: { rotulo: "Esperando equipe", cor: "bg-amber-100 text-amber-800" },
  HUMANO: { rotulo: "Com a equipe", cor: "bg-indigo-100 text-indigo-800" },
  NOVO: { rotulo: "Novo", cor: "bg-sky-100 text-sky-800" },
  REMARCACAO: { rotulo: "Remarcação", cor: "bg-violet-100 text-violet-800" },
  CANCELAMENTO: { rotulo: "Cancelamento", cor: "bg-rose-100 text-rose-800" },
};
