export class ErroApi extends Error {
  constructor(public status: number, mensagem: string) {
    super(mensagem);
  }
}

async function chamar<T>(metodo: string, caminho: string, corpo?: unknown): Promise<T> {
  const r = await fetch(`/api${caminho}`, {
    method: metodo,
    credentials: "same-origin",
    headers: corpo !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
  });
  if (r.status === 204) return undefined as T;
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) {
    const det = (dados as { detail?: unknown }).detail;
    const msg = typeof det === "string" ? det : Array.isArray(det) ? "dados inválidos" : `erro ${r.status}`;
    if (r.status === 401 && !caminho.startsWith("/auth/")) window.dispatchEvent(new Event("sessao-expirada"));
    throw new ErroApi(r.status, msg);
  }
  return dados as T;
}

export const api = {
  get: <T,>(c: string) => chamar<T>("GET", c),
  post: <T,>(c: string, corpo: unknown = {}) => chamar<T>("POST", c, corpo),
  put: <T,>(c: string, corpo: unknown) => chamar<T>("PUT", c, corpo),
  patch: <T,>(c: string, corpo: unknown) => chamar<T>("PATCH", c, corpo),
  del: (c: string) => chamar<void>("DELETE", c),
};

export function qs(params: Record<string, string | number | (string | number)[] | undefined | null>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => u.append(k, String(x)));
    else u.append(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : "";
}
