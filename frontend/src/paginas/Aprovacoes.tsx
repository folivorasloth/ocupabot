import { useState } from "react";
import { api, qs } from "../api";
import EscolherHorario from "../componentes/EscolherHorario";
import { Abas, avisarContadores, Aviso, Cabecalho, Erro, Lista, Modal, Selo, useRecurso } from "../componentes/ui";
import { dataCurta, dataHora, telefone } from "../formato";
import { EQUIPE, useSessao } from "../sessao";
import type { Agendamento, Aprovacao } from "../tipos";

const VAZIO: Record<string, string> = {
  PENDENTE: "Nenhum pedido esperando a equipe.", AGUARDANDO_CLIENTE: "Nenhuma proposta esperando resposta do cliente.",
  APROVADA: "Nenhum pedido aprovado ainda.", RECUSADA: "Nenhum pedido recusado.", EXPIRADA: "Nenhuma proposta vencida.",
};

function Linha({ a }: { a: Agendamento }) {
  return (
    <div className="text-sm">
      <span className="font-medium">{dataCurta(a.data)} às {a.horario}</span> · {a.paciente.nome || "(sem nome)"}
      <span className="text-slate-500"> · {a.empresa ?? "Particular"} · {a.tipo_aso ?? "—"}</span>
      <div className="text-xs text-slate-500">{a.exames.map((e) => e.nome).join(", ")}</div>
    </div>
  );
}

export default function Aprovacoes() {
  const { pode } = useSessao();
  const [status, setStatus] = useState("PENDENTE");
  const [lista, erro, recarregar] = useRecurso(() => api.get<Aprovacao[]>(`/aprovacoes${qs({ status })}`), [status], 20000);
  const [alvo, setAlvo] = useState<{ ap: Aprovacao; modo: "propor" | "recusar" } | null>(null);
  const [nova, setNova] = useState({ data: "", horario: "" });
  const [motivo, setMotivo] = useState("");
  const [falha, setFalha] = useState<string | null>(null);
  const [feito, setFeito] = useState<string | null>(null);
  const equipe = pode(...EQUIPE);

  async function enviar(chamada: () => Promise<unknown>, aviso: string) {
    setFalha(null);
    setFeito(null);
    try { await chamada(); setAlvo(null); setFeito(aviso); recarregar(); avisarContadores(); }
    catch (e) { setFalha((e as Error).message); }
  }
  const acao = (ap: Aprovacao, rota: string, aviso: string, corpo: unknown = {}) => enviar(() => api.post(`/aprovacoes/${ap.id}/${rota}`, corpo), aviso);

  return (
    <>
      <Cabecalho titulo="Pedidos do bot" sub="Tudo o que o bot agenda, remarca ou cancela espera a equipe. A vaga fica segura enquanto isso." />
      <Abas abas={[["PENDENTE", "Esperando a equipe"], ["AGUARDANDO_CLIENTE", "Esperando o cliente"], ["APROVADA", "Aprovados"], ["RECUSADA", "Recusados"], ["EXPIRADA", "Propostas vencidas"]]} ativa={status} mudar={(s) => { setStatus(s); setFeito(null); }} />
      <Erro texto={alvo ? null : falha} />
      <Aviso texto={feito} />
      <Lista dados={lista} erro={erro} vazio={VAZIO[status]}>{(itens) => (
        <div className="space-y-3">
          {itens.map((ap) => {
            const ag = ap.agendamento;
            return (
              <div key={ap.id} className="cartao">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Selo valor={ap.tipo} />
                  <span className="text-xs text-slate-500">pedido em {dataHora(ap.pedida_em)} · quem pediu: {ag.contato ? `${ag.contato_nome ? `${ag.contato_nome} · ` : ""}${telefone(ag.contato)}` : "—"}</span>
                  {ap.exige_supervisao && <span className="whitespace-nowrap rounded bg-amber-100 px-1.5 text-xs text-amber-800">Exige Supervisão</span>}
                  {ap.marcadores.map((m) => <span key={m} className="whitespace-nowrap rounded bg-rose-100 px-1.5 text-xs text-rose-800" title="Confira antes de aprovar">Atenção: {m}</span>)}
                  {ap.decidida_em && <span className="text-xs text-slate-500">decidido em {dataHora(ap.decidida_em)}{ap.alterada ? " (horário proposto pela equipe)" : ""}{ap.motivo ? ` · ${ap.motivo}` : ""}</span>}
                </div>
                {ap.original && <div className="mb-1 text-xs text-slate-500 line-through"><Linha a={ap.original} /></div>}
                <Linha a={ag} />
                {ap.status === "AGUARDANDO_CLIENTE" && <p className="mt-2 text-xs text-amber-800">Proposta enviada em {dataHora(ap.proposta_em)}. A pessoa responde 1 para confirmar ou 2 para outro horário, até {dataHora(ap.proposta_ate)}. O horário só vale depois do 1.</p>}
                {ag.sem_aviso && ap.status === "PENDENTE" && <p className="mt-2 text-xs text-amber-800">{ag.contato ? "Quem pediu mandou SAIR" : "Pedido sem WhatsApp"}: a resposta não chega por mensagem. Avise por telefone.</p>}
                {equipe && ap.status === "PENDENTE" && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button className="botao-primario" onClick={() => acao(ap, "aprovar", "Aprovado. A confirmação entrou na fila de envio.")}>{ap.tipo === "CANCELAMENTO" ? "Aprovar cancelamento" : "Aprovar"}</button>
                    {ap.tipo !== "CANCELAMENTO" && <button className="botao-secundario" onClick={() => { setFalha(null); setNova({ data: ag.data, horario: "" }); setAlvo({ ap, modo: "propor" }); }}>Propor outro horário</button>}
                    <button className="botao-secundario" onClick={() => { setFalha(null); setMotivo(""); setAlvo({ ap, modo: "recusar" }); }}>Recusar</button>
                    {ap.marcadores.includes("RH não confirmado") && ap.contato_id && ag.empresa_id && (
                      <button className="botao-secundario" title="Este número passa a agendar por esta empresa sem o aviso" onClick={() => enviar(() => api.put(`/contatos/${ap.contato_id}/empresas/${ag.empresa_id}`, {}), "Contato confirmado como quem agenda por esta empresa.")}>Confirmar como RH de {ag.empresa}</button>
                    )}
                  </div>
                )}
                {equipe && ap.status === "AGUARDANDO_CLIENTE" && (
                  <div className="mt-3"><button className="botao-secundario" onClick={() => acao(ap, "cancelar-proposta", "Proposta cancelada: a vaga foi liberada e a conversa está com a equipe.")}>Cancelar proposta</button></div>
                )}
              </div>
            );
          })}
        </div>
      )}</Lista>
      <Modal titulo={alvo?.modo === "recusar" ? "Recusar pedido" : "Propor outro horário"} aberto={!!alvo} fechar={() => setAlvo(null)}>
        {alvo && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (alvo.modo === "recusar") acao(alvo.ap, "recusar", "Pedido recusado: a vaga foi liberada e a conversa está com a equipe.", { motivo: motivo.trim() || null }); else if (nova.horario) acao(alvo.ap, "propor", "Proposta enviada. O pedido está em “Esperando o cliente”.", nova); }}>
            <Erro texto={falha} />
            {alvo.modo === "recusar" ? (
              <><p className="text-sm text-slate-600">A vaga é liberada e a conversa vai para a equipe.</p>
                <label className="rotulo" htmlFor="motivo">Motivo (opcional; fica no histórico, sem CPF nem RG)</label><input id="motivo" className="campo" value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus maxLength={300} />
                <button className="botao-perigo">Recusar pedido</button></>
            ) : (
              <><p className="text-sm text-slate-600">O horário proposto fica seguro e a pessoa recebe a pergunta pelo WhatsApp. Só é agendado quando ela responder 1.</p>
                <EscolherHorario exames={alvo.ap.agendamento.exames.map((e) => e.id)} data={nova.data} horario={nova.horario} mudar={(data, horario) => setNova({ data, horario })} />
                <button className="botao-primario" disabled={!nova.horario}>Propor {nova.horario ? `${dataCurta(nova.data)} às ${nova.horario}` : "…"}</button></>
            )}
          </form>
        )}
      </Modal>
    </>
  );
}
