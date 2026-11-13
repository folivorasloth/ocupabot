import { useState } from "react";
import { api } from "../api";
import { dataCurta, hojeIso, telefone } from "../formato";
import { EQUIPE, useSessao } from "../sessao";
import type { Agendamento } from "../tipos";
import EscolherHorario from "./EscolherHorario";
import { Erro, Modal, Selo, Vazio } from "./ui";

const ORIGEM: Record<string, string> = { WHATSAPP: "WhatsApp", PAINEL: "Painel", IMPORTACAO: "Importado" };

export default function ListaAgenda({ itens, recarregar, mostrarData, vazio }: { itens: Agendamento[]; recarregar: () => void; mostrarData?: boolean; vazio?: string }) {
  const { pode } = useSessao();
  const [alvo, setAlvo] = useState<{ ag: Agendamento; acao: "cancelar" | "remarcar" } | null>(null);
  const [motivo, setMotivo] = useState("");
  const [nova, setNova] = useState({ data: "", horario: "" });
  const [erro, setErro] = useState<string | null>(null);
  const equipe = pode(...EQUIPE);
  const supervisao = pode("SUPERVISAO");
  const hoje = hojeIso();

  async function acao(ag: Agendamento, rota: string, corpo: unknown = {}) {
    setErro(null);
    try { await api.post(`/agendamentos/${ag.id}/${rota}`, corpo); setAlvo(null); recarregar(); }
    catch (e) { setErro((e as Error).message); }
  }

  if (!itens.length) return <Vazio texto={vazio ?? "Nenhum agendamento no período."} />;
  return (
    <>
      <Erro texto={alvo ? null : erro} />
      <div className="overflow-x-auto">
        <table className="tabela tabela-cartao">
          <thead><tr>{mostrarData && <th>Dia</th>}<th>Hora</th><th>Paciente</th><th>Empresa / tipo</th><th>Exames</th><th>Status</th>{equipe && <th></th>}</tr></thead>
          <tbody>
            {itens.map((a) => {
              const ativo = a.status === "AGENDADO" || a.status === "CONFIRMADO";
              const chegouODia = a.data <= hoje; // presença e falta só a partir do dia do exame
              const mexe = !a.no_sistema_externo || supervisao; // o que está no sistema externo só a Supervisão altera
              return (
                <tr key={a.id}>
                  {mostrarData && <td className="whitespace-nowrap">{dataCurta(a.data)}</td>}
                  <td className="font-medium">{a.horario}</td>
                  <td>{a.paciente.nome || "(sem nome)"}<div className="text-xs text-slate-400">{a.paciente.cpf}{a.paciente.cpf ? " · " : ""}{ORIGEM[a.origem] ?? "Outro"}</div>
                    {a.contato && <div className="text-xs text-slate-500">pediu: {a.contato_nome ? `${a.contato_nome} · ` : ""}{telefone(a.contato)}</div>}
                    {ativo && a.sem_aviso && <div className="text-xs text-amber-700">{a.contato ? "pediu SAIR: não recebe avisos" : "sem WhatsApp: ninguém recebe avisos"}</div>}</td>
                  <td>{a.empresa ?? <span className="text-slate-400">Particular</span>}<div className="text-xs text-slate-500">{a.tipo_aso}</div></td>
                  <td className="text-xs">{a.exames.map((e) => <div key={e.id}>{e.nome}{e.profissional && <span className="text-slate-400"> · {e.profissional}</span>}</div>)}</td>
                  <td><Selo valor={a.status} />{a.no_sistema_externo && <div className="mt-1 text-xs text-slate-500">no sistema externo</div>}
                    {a.motivo_cancelamento && <div className="mt-1 max-w-[14rem] text-xs text-slate-500">{a.motivo_cancelamento}</div>}</td>
                  {equipe && (
                    <td className="text-right">
                      <div className="flex flex-wrap justify-end gap-1">
                        {ativo && chegouODia && <button className="botao-secundario" onClick={() => acao(a, "presenca")}>Chegou</button>}
                        {ativo && chegouODia && <button className="botao-secundario" onClick={() => acao(a, "falta")}>Faltou</button>}
                        {(ativo || a.status === "FALTOU") && mexe && <button className="botao-secundario" onClick={() => { setNova({ data: a.data < hoje ? hoje : a.data, horario: "" }); setAlvo({ ag: a, acao: "remarcar" }); }}>Remarcar</button>}
                        {ativo && mexe && <button className="botao-secundario" onClick={() => { setMotivo(""); setAlvo({ ag: a, acao: "cancelar" }); }}>Cancelar</button>}
                        {ativo && (!a.no_sistema_externo || supervisao) && <label className="inline-flex items-center gap-1 px-1 text-xs text-slate-500" title="Marque depois de lançar no sistema de gestão da clínica"><input type="checkbox" checked={a.no_sistema_externo} onChange={(e) => acao(a, `externo?lancado=${e.target.checked}`)} />lançado</label>}
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Modal titulo={alvo?.acao === "cancelar" ? "Cancelar agendamento" : "Remarcar"} aberto={!!alvo} fechar={() => setAlvo(null)}>
        {alvo && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (alvo.acao === "cancelar") { if (motivo.trim().length >= 2) acao(alvo.ag, "cancelar", { motivo }); } else if (nova.horario) acao(alvo.ag, "remarcar", nova); }}>
            <p className="text-sm text-slate-600">{alvo.ag.paciente.nome} · {dataCurta(alvo.ag.data)} às {alvo.ag.horario}</p>
            {alvo.ag.sem_aviso && <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">Ninguém vai receber mensagem sobre esta mudança ({alvo.ag.contato ? "a pessoa pediu SAIR" : "o agendamento não tem WhatsApp"}): avise por telefone.</p>}
            <Erro texto={erro} />
            {alvo.acao === "cancelar" ? (
              <><label className="rotulo" htmlFor="motivo">Motivo * (não escreva CPF nem RG)</label><input id="motivo" className="campo" value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus maxLength={300} />
                <button className="botao-perigo" disabled={motivo.trim().length < 2}>Cancelar agendamento</button></>
            ) : (
              <><EscolherHorario exames={alvo.ag.exames.map((e) => e.id)} data={nova.data} horario={nova.horario} mudar={(data, horario) => setNova({ data, horario })} />
                <button className="botao-primario" disabled={!nova.horario}>Remarcar para {nova.horario ? `${dataCurta(nova.data)} às ${nova.horario}` : "…"}</button></>
            )}
          </form>
        )}
      </Modal>
    </>
  );
}
