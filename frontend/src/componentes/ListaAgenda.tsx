import { useState } from "react";
import { api } from "../api";
import { dataCurta } from "../formato";
import { EQUIPE, useSessao } from "../sessao";
import type { Agendamento } from "../tipos";
import EscolherHorario from "./EscolherHorario";
import { Erro, Modal, Selo, Vazio } from "./ui";

export default function ListaAgenda({ itens, recarregar, mostrarData }: { itens: Agendamento[]; recarregar: () => void; mostrarData?: boolean }) {
  const { pode } = useSessao();
  const [alvo, setAlvo] = useState<{ ag: Agendamento; acao: "cancelar" | "remarcar" } | null>(null);
  const [motivo, setMotivo] = useState("");
  const [nova, setNova] = useState({ data: "", horario: "" });
  const [erro, setErro] = useState<string | null>(null);
  const equipe = pode(...EQUIPE);

  async function acao(ag: Agendamento, rota: string, corpo: unknown = {}) {
    setErro(null);
    try { await api.post(`/agendamentos/${ag.id}/${rota}`, corpo); setAlvo(null); recarregar(); }
    catch (e) { setErro((e as Error).message); }
  }

  if (!itens.length) return <Vazio texto="Nenhum agendamento no período." />;
  return (
    <>
      <Erro texto={alvo ? null : erro} />
      <div className="overflow-x-auto">
        <table className="tabela">
          <thead><tr>{mostrarData && <th>Dia</th>}<th>Hora</th><th>Paciente</th><th>Empresa / tipo</th><th>Exames</th><th>Status</th>{equipe && <th></th>}</tr></thead>
          <tbody>
            {itens.map((a) => {
              const ativo = a.status === "AGENDADO" || a.status === "CONFIRMADO";
              return (
                <tr key={a.id}>
                  {mostrarData && <td className="whitespace-nowrap">{dataCurta(a.data)}</td>}
                  <td className="font-medium">{a.horario}</td>
                  <td>{a.paciente.nome}<div className="text-xs text-slate-400">{a.paciente.cpf} · {a.origem === "WHATSAPP" ? "WhatsApp" : a.origem === "PAINEL" ? "Painel" : "Importado"}</div></td>
                  <td>{a.empresa ?? <span className="text-slate-400">Particular</span>}<div className="text-xs text-slate-500">{a.tipo_aso}</div></td>
                  <td className="text-xs">{a.exames.map((e) => <div key={e.id}>{e.nome}{e.profissional && <span className="text-slate-400"> · {e.profissional}</span>}</div>)}</td>
                  <td><Selo valor={a.status} />{a.no_sistema_externo && <div className="mt-1 text-xs text-slate-500">no sistema externo</div>}</td>
                  {equipe && (
                    <td className="whitespace-nowrap text-right">
                      {ativo && <button className="botao-secundario mr-1" onClick={() => acao(a, "presenca")}>Chegou</button>}
                      {ativo && <button className="botao-secundario mr-1" onClick={() => acao(a, "falta")}>Faltou</button>}
                      {(ativo || a.status === "FALTOU") && <button className="botao-secundario mr-1" onClick={() => { setNova({ data: a.data, horario: "" }); setAlvo({ ag: a, acao: "remarcar" }); }}>Remarcar</button>}
                      {ativo && <button className="botao-secundario" onClick={() => { setMotivo(""); setAlvo({ ag: a, acao: "cancelar" }); }}>Cancelar</button>}
                      {ativo && <label className="ml-2 inline-flex items-center gap-1 text-xs text-slate-500"><input type="checkbox" checked={a.no_sistema_externo} onChange={(e) => acao(a, `externo?lancado=${e.target.checked}`)} />externo</label>}
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
          <div className="space-y-3">
            <p className="text-sm text-slate-600">{alvo.ag.paciente.nome} · {dataCurta(alvo.ag.data)} às {alvo.ag.horario}</p>
            <Erro texto={erro} />
            {alvo.acao === "cancelar" ? (
              <><label className="rotulo">Motivo</label><input className="campo" value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />
                <button className="botao-perigo" disabled={motivo.length < 2} onClick={() => acao(alvo.ag, "cancelar", { motivo })}>Cancelar agendamento</button></>
            ) : (
              <><EscolherHorario exames={alvo.ag.exames.map((e) => e.id)} data={nova.data} horario={nova.horario} mudar={(data, horario) => setNova({ data, horario })} />
                <button className="botao-primario" disabled={!nova.horario} onClick={() => acao(alvo.ag, "remarcar", nova)}>Remarcar para {nova.horario || "…"}</button></>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}
