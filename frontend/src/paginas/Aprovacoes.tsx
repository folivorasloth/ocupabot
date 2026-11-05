import { useState } from "react";
import { api, qs } from "../api";
import EscolherHorario from "../componentes/EscolherHorario";
import { Abas, Cabecalho, Carregando, Erro, Modal, Selo, useRecurso, Vazio } from "../componentes/ui";
import { dataCurta, dataHora } from "../formato";
import { EQUIPE, useSessao } from "../sessao";
import type { Agendamento, Aprovacao } from "../tipos";

function Linha({ a }: { a: Agendamento }) {
  return (
    <div className="text-sm">
      <span className="font-medium">{dataCurta(a.data)} às {a.horario}</span> · {a.paciente.nome}
      <span className="text-slate-500"> · {a.empresa ?? "Particular"} · {a.tipo_aso ?? "—"}</span>
      <div className="text-xs text-slate-500">{a.exames.map((e) => e.nome).join(", ")}</div>
    </div>
  );
}

export default function Aprovacoes() {
  const { pode } = useSessao();
  const [status, setStatus] = useState("PENDENTE");
  const [lista, erro, recarregar] = useRecurso(() => api.get<Aprovacao[]>(`/aprovacoes${qs({ status })}`), [status], 20000);
  const [alvo, setAlvo] = useState<{ ap: Aprovacao; modo: "alterar" | "recusar" } | null>(null);
  const [nova, setNova] = useState({ data: "", horario: "" });
  const [motivo, setMotivo] = useState("");
  const [falha, setFalha] = useState<string | null>(null);
  const equipe = pode(...EQUIPE);

  async function enviar(ap: Aprovacao, rota: "aprovar" | "recusar", corpo: unknown = {}) {
    setFalha(null);
    try { await api.post(`/aprovacoes/${ap.id}/${rota}`, corpo); setAlvo(null); recarregar(); }
    catch (e) { setFalha((e as Error).message); }
  }

  return (
    <>
      <Cabecalho titulo="Aprovações" sub="Tudo o que o bot agenda, remarca ou cancela espera a equipe. A vaga fica segura enquanto isso." />
      <Abas abas={[["PENDENTE", "Pendentes"], ["APROVADA", "Aprovadas"], ["RECUSADA", "Recusadas"]]} ativa={status} mudar={setStatus} />
      <Erro texto={erro || (alvo ? null : falha)} />
      {!lista ? <Carregando /> : lista.length === 0 ? <Vazio texto="Nada aqui." /> : (
        <div className="space-y-3">
          {lista.map((ap) => (
            <div key={ap.id} className="cartao">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Selo valor={ap.tipo} />
                <span className="text-xs text-slate-500">pedido em {dataHora(ap.pedida_em)} · contato {ap.agendamento.contato ?? "—"}</span>
                {ap.exige_supervisao && <span className="rounded bg-amber-100 px-1.5 text-xs text-amber-800">exige Supervisão</span>}
                {ap.status !== "PENDENTE" && <span className="text-xs text-slate-500">decidido em {dataHora(ap.decidida_em)}{ap.alterada ? " (alterado)" : ""}{ap.motivo ? ` · ${ap.motivo}` : ""}</span>}
              </div>
              {ap.original && <div className="mb-1 text-xs text-slate-500 line-through"><Linha a={ap.original} /></div>}
              <Linha a={ap.agendamento} />
              {ap.status === "PENDENTE" && equipe && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className="botao-primario" onClick={() => enviar(ap, "aprovar")}>{ap.tipo === "CANCELAMENTO" ? "Aprovar cancelamento" : "Aprovar"}</button>
                  {ap.tipo !== "CANCELAMENTO" && <button className="botao-secundario" onClick={() => { setNova({ data: ap.agendamento.data, horario: "" }); setAlvo({ ap, modo: "alterar" }); }}>Alterar horário e aprovar</button>}
                  <button className="botao-secundario" onClick={() => { setMotivo(""); setAlvo({ ap, modo: "recusar" }); }}>Recusar</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <Modal titulo={alvo?.modo === "recusar" ? "Recusar pedido" : "Alterar e aprovar"} aberto={!!alvo} fechar={() => setAlvo(null)}>
        {alvo && (
          <div className="space-y-3">
            <Erro texto={falha} />
            {alvo.modo === "recusar" ? (
              <><p className="text-sm text-slate-600">A vaga é liberada e a conversa vai para a equipe.</p>
                <label className="rotulo">Motivo (fica no histórico)</label><input className="campo" value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />
                <button className="botao-perigo" disabled={motivo.length < 2} onClick={() => enviar(alvo.ap, "recusar", { motivo })}>Recusar</button></>
            ) : (
              <><EscolherHorario exames={alvo.ap.agendamento.exames.map((e) => e.id)} data={nova.data} horario={nova.horario} mudar={(data, horario) => setNova({ data, horario })} />
                <button className="botao-primario" disabled={!nova.horario} onClick={() => enviar(alvo.ap, "aprovar", nova)}>Aprovar em {nova.horario || "…"}</button></>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}
