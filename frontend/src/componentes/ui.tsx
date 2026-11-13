import { ReactNode, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { STATUS } from "../formato";

export function Selo({ valor }: { valor: string }) {
  const s = STATUS[valor] ?? { rotulo: valor, cor: "bg-slate-100 text-slate-700" };
  return <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${s.cor}`}>{s.rotulo}</span>;
}

export function Cabecalho({ titulo, sub, children }: { titulo: string; sub?: string; children?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="break-words text-xl font-semibold text-slate-800">{titulo}</h1>
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
  return <p className="py-8 text-center text-sm text-slate-400" role="status">Carregando…</p>;
}

export function Erro({ texto }: { texto: string | null }) {
  if (!texto) return null;
  return <p className="mb-3 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">{texto}</p>;
}

/** Aviso de que algo deu certo (ex.: "a mensagem entrou na fila"). */
export function Aviso({ texto }: { texto: string | null }) {
  if (!texto) return null;
  return <p className="mb-3 rounded-md bg-marca-50 px-3 py-2 text-sm text-marca-700" role="status">{texto}</p>;
}

/** Lista que depende da API: nunca mostra "nenhum…" enquanto carrega nem quando a API deu erro. */
export function Lista<T>({ dados, erro, vazio, children }: { dados: T[] | null; erro: string | null; vazio: string; children: (itens: T[]) => ReactNode }) {
  if (erro) return <Erro texto={erro} />;
  if (!dados) return <Carregando />;
  return dados.length === 0 ? <Vazio texto={vazio} /> : <>{children(dados)}</>;
}

/** Os menus atualizam os números (pedidos, conversas) logo depois de uma ação. */
export function avisarContadores() {
  window.dispatchEvent(new Event("contadores"));
}

const FOCAVEIS = "a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])";

export function Modal({ titulo, aberto, fechar, children, largo }: {
  titulo: string; aberto: boolean; fechar: () => void; children: ReactNode; largo?: boolean;
}) {
  const caixa = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!aberto) return;
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopPropagation(); fechar(); return; }
      if (e.key !== "Tab" || !caixa.current) return;
      // o Tab não sai da janela
      const itens = Array.from(caixa.current.querySelectorAll<HTMLElement>(FOCAVEIS));
      if (!itens.length) return;
      const [primeiro, ultimo] = [itens[0], itens[itens.length - 1]];
      const dentro = caixa.current.contains(document.activeElement);
      if (e.shiftKey && (!dentro || document.activeElement === primeiro)) { e.preventDefault(); ultimo.focus(); }
      else if (!e.shiftKey && (!dentro || document.activeElement === ultimo)) { e.preventDefault(); primeiro.focus(); }
    };
    window.addEventListener("keydown", tecla, true);
    return () => window.removeEventListener("keydown", tecla, true);
  }, [aberto, fechar]);
  if (!aberto) return null;
  // no portal do body: a janela não fica presa atrás de um cartão nem cortada por ele
  return createPortal(
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-3 sm:p-4" onClick={fechar}>
      <div ref={caixa} role="dialog" aria-modal="true" aria-label={titulo}
        className={`my-4 w-full sm:mt-10 ${largo ? "max-w-2xl" : "max-w-md"} rounded-lg bg-white p-4 shadow-xl sm:p-5`} onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between gap-2">
          <h2 className="break-words text-lg font-semibold text-slate-800">{titulo || "Alterar"}</h2>
          <button className="h-8 w-8 shrink-0 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600" onClick={fechar} aria-label="Fechar">✕</button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function Abas({ abas, ativa, mudar }: { abas: [string, string][]; ativa: string; mudar: (a: string) => void }) {
  return (
    <div className="mb-4 flex gap-1 overflow-x-auto overflow-y-hidden border-b border-slate-200" role="tablist">
      {abas.map(([id, rotulo]) => (
        <button key={id} role="tab" aria-selected={ativa === id} onClick={() => mudar(id)}
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
