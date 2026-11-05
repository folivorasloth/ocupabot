import { ReactNode, useEffect, useState } from "react";
import { STATUS } from "../formato";

export function Selo({ valor }: { valor: string }) {
  const s = STATUS[valor] ?? { rotulo: valor, cor: "bg-slate-100 text-slate-700" };
  return <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${s.cor}`}>{s.rotulo}</span>;
}

export function Cabecalho({ titulo, sub, children }: { titulo: string; sub?: string; children?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">{titulo}</h1>
        {sub && <p className="text-sm text-slate-500">{sub}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

export function Vazio({ texto }: { texto: string }) {
  return <p className="py-8 text-center text-sm text-slate-500">{texto}</p>;
}

export function Carregando() {
  return <p className="py-8 text-center text-sm text-slate-400">Carregando…</p>;
}

export function Erro({ texto }: { texto: string | null }) {
  if (!texto) return null;
  return <p className="mb-3 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{texto}</p>;
}

export function Modal({ titulo, aberto, fechar, children, largo }: {
  titulo: string; aberto: boolean; fechar: () => void; children: ReactNode; largo?: boolean;
}) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && fechar();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [fechar]);
  if (!aberto) return null;
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4" onClick={fechar}>
      <div className={`mt-10 w-full ${largo ? "max-w-2xl" : "max-w-md"} rounded-lg bg-white p-5 shadow-xl`} onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">{titulo}</h2>
          <button className="text-slate-400 hover:text-slate-600" onClick={fechar} aria-label="Fechar">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Abas({ abas, ativa, mudar }: { abas: [string, string][]; ativa: string; mudar: (a: string) => void }) {
  return (
    <div className="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200">
      {abas.map(([id, rotulo]) => (
        <button key={id} onClick={() => mudar(id)}
          className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${ativa === id ? "border-marca-600 text-marca-700" : "border-transparent text-slate-500 hover:text-slate-700"}`}>
          {rotulo}
        </button>
      ))}
    </div>
  );
}

/** Carrega um recurso da API e devolve [dados, erro, recarregar]. */
export function useRecurso<T>(carregar: () => Promise<T>, deps: unknown[] = [], intervaloMs?: number) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  useEffect(() => {
    let vivo = true;
    const rodar = () => carregar().then((d) => vivo && (setDados(d), setErro(null))).catch((e) => vivo && setErro(e.message));
    rodar();
    const id = intervaloMs ? window.setInterval(rodar, intervaloMs) : undefined;
    return () => { vivo = false; if (id) window.clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, versao]);
  return [dados, erro, () => setVersao((v) => v + 1)] as const;
}
