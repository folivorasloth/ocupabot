const DIAS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
export const DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

/** "seg 09/11"; mostra o ano quando não é o ano corrente. */
export function dataCurta(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number);
  const dt = new Date(a, m - 1, d);
  const ano = a === new Date().getFullYear() ? "" : `/${a}`;
  return `${DIAS[dt.getDay()]} ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}${ano}`;
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

/** Singular e plural de verdade: plural(1, "pedido", "pedidos") = "1 pedido". */
export function plural(n: number, um: string, varios: string): string {
  return `${n} ${n === 1 ? um : varios}`;
}

/** 5511987650001 -> (11) 98765-0001 */
export function telefone(t: string | null | undefined): string {
  const d = (t ?? "").replace(/\D/g, "").replace(/^55(?=\d{10,11}$)/, "");
  if (d.length < 10) return t ?? "";
  return `(${d.slice(0, 2)}) ${d.slice(2, d.length - 4)}-${d.slice(-4)}`;
}

export function cnpj(c: unknown): string {
  const d = String(c ?? "").replace(/\D/g, "");
  return d.length === 14 ? `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}` : String(c ?? "");
}

export const TIPO_CONTATO: Record<string, string> = {
  RH: "RH", CREDENCIADORA: "Credenciadora", CONTABILIDADE: "Contabilidade", PARTICULAR: "Particular",
  PACIENTE: "Paciente", DESCONHECIDO: "Não identificado",
};

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
  AGUARDANDO_CLIENTE: { rotulo: "Esperando o cliente", cor: "bg-amber-100 text-amber-800" },
  EXPIRADA: { rotulo: "Proposta vencida", cor: "bg-slate-200 text-slate-600" },
};
