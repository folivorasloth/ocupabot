import { useEffect, useRef, useState } from "react";
import { api, qs } from "../api";
import { nomeEmpresa, useCatalogo } from "../componentes/catalogo";
import { Abas, Cabecalho, Carregando, Erro, Selo, useRecurso, Vazio } from "../componentes/ui";
import { dataHora } from "../formato";
import { EQUIPE, useSessao } from "../sessao";
import type { Conversa } from "../tipos";

const AUTOR: Record<string, string> = { CONTATO: "bg-white border border-slate-200", BOT: "bg-marca-50", EQUIPE: "bg-indigo-50", SISTEMA: "bg-amber-50" };

function Detalhe({ id, mudou }: { id: number; mudou: () => void }) {
  const { pode } = useSessao();
  const [c, erro, recarregar] = useRecurso(() => api.get<Conversa>(`/conversas/${id}`), [id], 5000);
  const [cat] = useCatalogo();
  const [texto, setTexto] = useState("");
  const [falha, setFalha] = useState<string | null>(null);
  const fim = useRef<HTMLDivElement>(null);
  useEffect(() => { fim.current?.scrollIntoView({ block: "end" }); }, [c?.mensagens?.length]);
  if (!c) return erro ? <Erro texto={erro} /> : <Carregando />;
  const equipe = pode(...EQUIPE);

  async function acao(rota: string, corpo: unknown = {}) {
    setFalha(null);
    try { await api.post(`/conversas/${id}/${rota}`, corpo); recarregar(); mudou(); }
    catch (e) { setFalha((e as Error).message); }
  }

  return (
    <div className="flex h-[70vh] flex-col">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2">
        <div>
          <div className="font-medium">{c.contato.nome ?? c.contato.telefone} <Selo valor={c.estado} /></div>
          <div className="text-xs text-slate-500">{c.contato.telefone} · {c.contato.tipo}{c.contato.empresa ? ` · ${c.contato.empresa}` : ""}{c.contato.optout ? " · pediu SAIR" : ""}</div>
          {c.motivo_humano && <div className="text-xs text-amber-700">Motivo: {c.motivo_humano}</div>}
        </div>
        {equipe && (
          <div className="flex gap-2">
            {c.estado !== "HUMANO" && <button className="botao-secundario" onClick={() => acao("assumir")}>Assumir</button>}
            {c.estado !== "BOT" && <button className="botao-secundario" onClick={() => acao("devolver")}>Devolver ao bot</button>}
            {c.empresa_informada && c.contato.tipo !== "RH" && cat && (
              <button className="botao-secundario" title="Passa a receber os avisos desta empresa" onClick={() => acao(`confirmar-rh${qs({ empresa_id: c.empresa_informada })}`)}>
                Confirmar RH de {nomeEmpresa(cat.empresas.find((e) => e.id === c.empresa_informada) ?? { razao_social: "?" })}
              </button>
            )}
          </div>
        )}
      </div>
      <Erro texto={falha} />
      <div className="flex-1 space-y-2 overflow-y-auto bg-slate-50 p-3">
        {c.mensagens?.length === 0 && <Vazio texto="Sem mensagens visíveis para o seu perfil." />}
        {c.mensagens?.map((m) => (
          <div key={m.id} className={`flex ${m.autor === "CONTATO" ? "justify-start" : "justify-end"}`}>
            <div className={`max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${AUTOR[m.autor]}`}>
              {m.texto}
              <div className="mt-1 text-right text-[10px] text-slate-400">{m.autor.toLowerCase()} · {dataHora(m.em)}{m.autor !== "CONTATO" ? ` · ${m.status.toLowerCase()}` : ""}{m.erro ? ` · ${m.erro}` : ""}</div>
            </div>
          </div>
        ))}
        <div ref={fim} />
      </div>
      {equipe && (
        <form className="flex gap-2 border-t border-slate-200 pt-2" onSubmit={(e) => { e.preventDefault(); if (texto.trim()) acao("responder", { texto }).then(() => setTexto("")); }}>
          <textarea className="campo" rows={2} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Responder como equipe (assume a conversa)" />
          <button className="botao-primario" disabled={!texto.trim()}>Enviar</button>
        </form>
      )}
    </div>
  );
}

export default function Conversas() {
  const [estado, setEstado] = useState("AGUARDANDO_HUMANO");
  const [lista, erro, recarregar] = useRecurso(() => api.get<Conversa[]>(`/conversas${qs({ estado: estado === "TODAS" ? undefined : estado })}`), [estado], 10000);
  const [aberta, setAberta] = useState<number | null>(null);
  return (
    <>
      <Cabecalho titulo="Conversas" sub="Assuma uma conversa para o bot parar de responder; devolva quando terminar." />
      <Abas abas={[["AGUARDANDO_HUMANO", "Esperando equipe"], ["HUMANO", "Com a equipe"], ["BOT", "Com o bot"], ["TODAS", "Todas"]]} ativa={estado} mudar={setEstado} />
      <Erro texto={erro} />
      <div className="grid gap-4 md:grid-cols-[320px_1fr]">
        <div className="cartao max-h-[70vh] overflow-y-auto p-0">
          {!lista ? <Carregando /> : lista.length === 0 ? <Vazio texto="Nenhuma conversa." /> : lista.map((c) => (
            <button key={c.id} onClick={() => setAberta(c.id)} className={`block w-full border-b border-slate-100 px-3 py-2 text-left hover:bg-slate-50 ${aberta === c.id ? "bg-marca-50" : ""}`}>
              <div className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium">{c.contato.nome ?? c.contato.telefone}</span><Selo valor={c.estado} /></div>
              <div className="truncate text-xs text-slate-500">{c.ultima_mensagem ?? c.motivo_humano ?? "—"}</div>
              <div className="text-[10px] text-slate-400">{dataHora(c.ultima_entrada_em)}</div>
            </button>
          ))}
        </div>
        <div className="cartao">{aberta ? <Detalhe id={aberta} mudou={recarregar} /> : <Vazio texto="Escolha uma conversa." />}</div>
      </div>
    </>
  );
}
