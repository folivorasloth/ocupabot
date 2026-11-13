import { useEffect, useRef, useState } from "react";
import { api, qs } from "../api";
import { nomeEmpresa, useCatalogo } from "../componentes/catalogo";
import { Abas, avisarContadores, Aviso, Cabecalho, Carregando, Erro, Lista, Selo, useRecurso, Vazio } from "../componentes/ui";
import { dataHora, telefone, TIPO_CONTATO } from "../formato";
import { EQUIPE, useSessao } from "../sessao";
import type { Conversa } from "../tipos";

const AUTOR: Record<string, string> = { CONTATO: "bg-white border border-slate-200", BOT: "bg-marca-50", EQUIPE: "bg-indigo-50", SISTEMA: "bg-amber-50" };
const QUEM: Record<string, string> = { CONTATO: "contato", BOT: "bot", EQUIPE: "equipe", SISTEMA: "aviso automático" };
const ENVIO: Record<string, string> = { PENDENTE: "na fila", ENVIADA: "enviada", FALHOU: "não saiu", EXPIRADA: "venceu sem sair", BLOQUEADA: "não enviada", SIMULADA: "simulada" };
const VAZIO: Record<string, string> = { AGUARDANDO_HUMANO: "Nenhuma conversa esperando a equipe.", HUMANO: "Nenhuma conversa com a equipe.", BOT: "Nenhuma conversa com o bot.", TODAS: "Nenhuma conversa ainda." };

function Detalhe({ id, mudou }: { id: number; mudou: () => void }) {
  const { pode } = useSessao();
  const [c, erro, recarregar] = useRecurso(() => api.get<Conversa>(`/conversas/${id}`), [id], 5000);
  const [cat] = useCatalogo();
  const [texto, setTexto] = useState("");
  const [tipo, setTipo] = useState("RH");
  const [falha, setFalha] = useState<string | null>(null);
  const [feito, setFeito] = useState<string | null>(null);
  const fim = useRef<HTMLDivElement>(null);
  useEffect(() => { fim.current?.scrollIntoView({ block: "end" }); }, [c?.mensagens?.length]);
  if (!c) return erro ? <Erro texto={erro} /> : <Carregando />;
  const equipe = pode(...EQUIPE);
  const informada = c.empresa_informada && !c.contato.empresas_ids.includes(c.empresa_informada) ? c.empresa_informada : null;

  async function acao(caminho: string, aviso: string | null = null, corpo: unknown = {}) {
    setFalha(null);
    setFeito(null);
    try { await api.post(caminho, corpo); setFeito(aviso); recarregar(); mudou(); avisarContadores(); return true; }
    catch (e) { setFalha((e as Error).message); return false; }
  }
  async function responder() {
    // rascunho só sai da caixa se a mensagem entrou na fila
    if (texto.trim() && await acao(`/conversas/${id}/responder`, "Mensagem na fila: sai em instantes pelo WhatsApp.", { texto })) setTexto("");
  }

  return (
    <div className="flex h-[70vh] flex-col">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2">
        <div className="min-w-0">
          <div className="font-medium">{c.contato.nome ?? telefone(c.contato.telefone)} <Selo valor={c.estado} /></div>
          <div className="text-xs text-slate-500">{telefone(c.contato.telefone)} · {TIPO_CONTATO[c.contato.tipo] ?? c.contato.tipo}{c.contato.empresa ? ` · ${c.contato.empresa}` : ""}{c.simulada ? " · conversa do simulador" : ""}</div>
          {c.contato.optout && <div className="text-xs font-medium text-rose-700">Pediu SAIR: não recebe avisos nem respostas da equipe. Combine por telefone.</div>}
          {c.motivo_humano && <div className="text-xs text-amber-700">Motivo: {c.motivo_humano}</div>}
        </div>
        {equipe && (
          <div className="flex flex-wrap gap-2">
            {c.estado !== "HUMANO" && <button className="botao-secundario" onClick={() => acao(`/conversas/${id}/assumir`)}>Assumir</button>}
            {c.estado !== "BOT" && <button className="botao-secundario" onClick={() => acao(`/conversas/${id}/devolver`)}>Devolver ao bot</button>}
            <button className="botao-secundario" title={c.contato.optout ? "A pessoa volta a receber mensagens" : "A pessoa pediu (por telefone, por exemplo) para não receber mais mensagens"}
              onClick={() => acao(`/contatos/${c.contato.id}/sair${qs({ ativo: String(!c.contato.optout) })}`, c.contato.optout ? "A pessoa voltou a receber mensagens." : "Registrado: a pessoa não recebe mais mensagens.")}>
              {c.contato.optout ? "Desfazer o SAIR" : "Registrar pedido de SAIR"}
            </button>
          </div>
        )}
      </div>
      {equipe && informada && cat && (
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 py-2 text-xs text-slate-600">
          Este número disse agendar por <b>{nomeEmpresa(cat.empresas.find((e) => e.id === informada) ?? { razao_social: "?" })}</b>. Confirmar como
          <select className="campo w-36" value={tipo} onChange={(e) => setTipo(e.target.value)} aria-label="Tipo de contato">
            <option value="RH">RH</option><option value="CREDENCIADORA">Credenciadora</option><option value="CONTABILIDADE">Contabilidade</option>
          </select>
          <button className="botao-secundario" title="Passa a agendar por esta empresa sem perguntar o CNPJ" onClick={() => acao(`/conversas/${id}/confirmar-rh${qs({ empresa_id: informada, tipo })}`, "Contato confirmado.")}>Confirmar</button>
        </div>
      )}
      <Erro texto={falha} />
      <Aviso texto={feito} />
      <div className="flex-1 space-y-2 overflow-y-auto bg-slate-50 p-3">
        {c.mensagens?.length === 0 && <Vazio texto="Esta conversa ainda não tem mensagens." />}
        {c.mensagens?.map((m) => (
          <div key={m.id} className={`flex ${m.autor === "CONTATO" ? "justify-start" : "justify-end"}`}>
            <div className={`max-w-[80%] whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm ${AUTOR[m.autor]}`}>
              {m.texto}
              <div className="mt-1 text-right text-[10px] text-slate-500">{QUEM[m.autor] ?? m.autor} · {dataHora(m.em)}{m.autor !== "CONTATO" ? ` · ${ENVIO[m.status] ?? m.status}` : ""}{m.erro ? ` · ${m.erro}` : ""}</div>
            </div>
          </div>
        ))}
        <div ref={fim} />
      </div>
      {equipe && (
        <form className="flex gap-2 border-t border-slate-200 pt-2" onSubmit={(e) => { e.preventDefault(); responder(); }}>
          <textarea className="campo" rows={2} value={texto} onChange={(e) => setTexto(e.target.value)} disabled={c.contato.optout && !c.simulada} maxLength={4000}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); responder(); } }}
            placeholder={c.contato.optout && !c.simulada ? "A pessoa pediu SAIR: a mensagem não seria entregue" : "Responder como equipe (assume a conversa). Ctrl+Enter envia. Não escreva CPF, RG nem resultado de exame."} />
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
      <div className="grid gap-4 md:grid-cols-[320px_minmax(0,1fr)]">
        <div className={`cartao max-h-[70vh] overflow-y-auto p-0 ${aberta ? "hidden md:block" : ""}`}>
          <Lista dados={lista} erro={erro} vazio={VAZIO[estado]}>{(itens) => itens.map((c) => (
            <button key={c.id} onClick={() => setAberta(c.id)} className={`block w-full border-b border-slate-100 px-3 py-2 text-left hover:bg-slate-50 ${aberta === c.id ? "bg-marca-50" : ""}`}>
              <div className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium">{c.contato.nome ?? telefone(c.contato.telefone)}</span><Selo valor={c.estado} /></div>
              <div className="truncate text-xs text-slate-500">{c.ultima_mensagem ?? c.motivo_humano ?? "—"}</div>
              <div className="text-[10px] text-slate-500">{dataHora(c.ultima_entrada_em)}{c.contato.optout ? " · pediu SAIR" : ""}</div>
            </button>
          ))}</Lista>
        </div>
        <div className={`cartao min-w-0 ${aberta ? "" : "hidden md:block"}`}>
          {aberta && <button className="botao-secundario mb-2 md:hidden" onClick={() => setAberta(null)}>← Voltar para a lista</button>}
          {aberta ? <Detalhe key={aberta} id={aberta} mudou={recarregar} /> : <Vazio texto="Escolha uma conversa." />}
        </div>
      </div>
    </>
  );
}
