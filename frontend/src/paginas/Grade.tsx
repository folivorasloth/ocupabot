import { useState } from "react";
import { api } from "../api";
import { useCatalogo } from "../componentes/catalogo";
import ListaAgenda from "../componentes/ListaAgenda";
import { Abas, Cabecalho, Carregando, Erro, useRecurso, Vazio } from "../componentes/ui";
import { dataCurta, DIAS_SEMANA, hojeIso, plural } from "../formato";
import { EQUIPE, useSessao } from "../sessao";
import type { Agendamento, Registro } from "../tipos";

const TIPO_EXCECAO: Record<string, string> = { FERIAS: "Férias", FOLGA: "Folga", AUSENCIA: "Ausência", FERIADO: "Feriado" };

function GradeSemanal() {
  const { pode } = useSessao();
  const [cat] = useCatalogo();
  const [grade, erro, recarregar] = useRecurso(() => api.get<Registro[]>("/grade"));
  const [novo, setNovo] = useState({ profissional_id: "", funcao_id: "", dia_semana: "0", turno: "MANHA" });
  const [falha, setFalha] = useState<string | null>(null);
  if (!cat || !grade) return erro ? <Erro texto={erro} /> : <Carregando />;
  const edita = pode("SUPERVISAO");
  const nomeProf = (id: unknown) => String(cat.profissionais.find((p) => p.id === id)?.nome ?? id);
  const funcoes = cat.funcoes.filter((f) => !f.requer_humano);

  async function adicionar() {
    setFalha(null);
    try {
      await api.post("/grade", { profissional_id: Number(novo.profissional_id), funcao_id: Number(novo.funcao_id), dia_semana: Number(novo.dia_semana), turno: novo.turno, confirmada: true });
      recarregar();
    } catch (e) { setFalha((e as Error).message); }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">Quem atende cada função em cada dia e turno. Um profissional em duas funções é um recurso só: ocupado numa, fica ocupado na outra.</p>
      <div className="overflow-x-auto">
        <table className="tabela">
          <thead><tr><th>Função</th>{DIAS_SEMANA.slice(0, 5).map((d) => <th key={d}>{d}</th>)}</tr></thead>
          <tbody>{funcoes.map((f) => (
            <tr key={f.id}>
              <td className="font-medium">{String(f.nome)}</td>
              {[0, 1, 2, 3, 4].map((dia) => (
                <td key={dia} className="text-xs">
                  {(["MANHA", "TARDE"] as const).map((turno) => {
                    const linhas = grade.filter((g) => g.funcao_id === f.id && g.dia_semana === dia && g.turno === turno);
                    return (
                      <div key={turno} className="mb-1">
                        <span className="text-slate-400">{turno === "MANHA" ? "M" : "T"}: </span>
                        {linhas.length === 0 ? <span className="text-slate-300">—</span> : linhas.map((g) => (
                          <span key={g.id} className={`mr-1 inline-flex items-center gap-1 rounded px-1 ${g.confirmada ? "bg-marca-50" : "bg-amber-50"}`}>
                            {nomeProf(g.profissional_id)}
                            {edita && <button className="text-slate-400 hover:text-rose-600" title="Remover" onClick={() => api.del(`/grade/${g.id}`).then(recarregar)}>×</button>}
                          </span>
                        ))}
                      </div>
                    );
                  })}
                </td>
              ))}
            </tr>
          ))}</tbody>
        </table>
      </div>
      {edita && (
        <div className="flex flex-wrap items-end gap-2 border-t border-slate-100 pt-3">
          <Erro texto={falha} />
          <div><label className="rotulo">Profissional</label><select className="campo" value={novo.profissional_id} onChange={(e) => setNovo({ ...novo, profissional_id: e.target.value })}><option value="">—</option>{cat.profissionais.filter((p) => p.ativo).map((p) => <option key={p.id} value={p.id}>{String(p.nome)}</option>)}</select></div>
          <div><label className="rotulo">Função</label><select className="campo" value={novo.funcao_id} onChange={(e) => setNovo({ ...novo, funcao_id: e.target.value })}><option value="">—</option>{funcoes.map((f) => <option key={f.id} value={f.id}>{String(f.nome)}</option>)}</select></div>
          <div><label className="rotulo">Dia</label><select className="campo" value={novo.dia_semana} onChange={(e) => setNovo({ ...novo, dia_semana: e.target.value })}>{DIAS_SEMANA.map((d, i) => <option key={d} value={i}>{d}</option>)}</select></div>
          <div><label className="rotulo">Turno</label><select className="campo" value={novo.turno} onChange={(e) => setNovo({ ...novo, turno: e.target.value })}><option value="MANHA">Manhã</option><option value="TARDE">Tarde</option></select></div>
          <button className="botao-primario" disabled={!novo.profissional_id || !novo.funcao_id} onClick={adicionar}>Adicionar</button>
        </div>
      )}
    </div>
  );
}

function Excecoes() {
  const { pode } = useSessao();
  const [cat] = useCatalogo();
  const [passadas, setPassadas] = useState(false);
  const [lista, erro, recarregar] = useRecurso(() => api.get<Registro[]>(`/excecoes?${passadas ? "ate" : "desde"}=${hojeIso()}`), [passadas]);
  const [f, setF] = useState({ profissional_id: "", tipo: "FERIAS", data_inicio: hojeIso(), data_fim: hojeIso(), turno: "", motivo: "", avisar_afetados: true });
  const [previa, setPrevia] = useState<Agendamento[] | null>(null);
  const [falha, setFalha] = useState<string | null>(null);
  const [resultado, setResultado] = useState<string | null>(null);
  if (!cat || !lista) return erro ? <Erro texto={erro} /> : <Carregando />;
  const corpo = () => ({ ...f, profissional_id: f.profissional_id ? Number(f.profissional_id) : null, turno: f.turno || null, motivo: f.motivo || null });

  async function verPrevia() {
    setFalha(null);
    try { setPrevia(await api.post<Agendamento[]>("/excecoes/previa", corpo())); } catch (e) { setFalha((e as Error).message); }
  }
  async function salvar() {
    setFalha(null);
    try {
      const r = await api.post<{ afetados: number; avisos: number }>("/excecoes", corpo());
      setResultado(`Salvo: ${plural(r.afetados, "agendamento afetado", "agendamentos afetados")}, ${plural(r.avisos, "aviso", "avisos")} na fila de envio.`);
      setPrevia(null);
      recarregar();
    } catch (e) { setFalha((e as Error).message); }
  }

  return (
    <div className="space-y-4">
      {pode(...EQUIPE) && (
        <div className="grid gap-2 sm:grid-cols-3">
          <div><label className="rotulo">Profissional (vazio = clínica toda)</label><select className="campo" value={f.profissional_id} onChange={(e) => setF({ ...f, profissional_id: e.target.value })}><option value="">Clínica toda</option>{cat.profissionais.map((p) => <option key={p.id} value={p.id}>{String(p.nome)}</option>)}</select></div>
          <div><label className="rotulo">Tipo</label><select className="campo" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}>{Object.entries(TIPO_EXCECAO).map(([t, r]) => <option key={t} value={t}>{r}</option>)}</select></div>
          <div><label className="rotulo">Turno</label><select className="campo" value={f.turno} onChange={(e) => setF({ ...f, turno: e.target.value })}><option value="">Dia todo</option><option value="MANHA">Manhã</option><option value="TARDE">Tarde</option></select></div>
          <div><label className="rotulo">De</label><input type="date" className="campo" value={f.data_inicio} onChange={(e) => setF({ ...f, data_inicio: e.target.value })} /></div>
          <div><label className="rotulo">Até</label><input type="date" className="campo" value={f.data_fim} onChange={(e) => setF({ ...f, data_fim: e.target.value })} /></div>
          <div><label className="rotulo">Motivo (opcional, sem CPF nem RG)</label><input className="campo" value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} maxLength={200} /></div>
          <label className="flex items-center gap-2 text-sm sm:col-span-3"><input type="checkbox" checked={f.avisar_afetados} onChange={(e) => setF({ ...f, avisar_afetados: e.target.checked })} />Avisar os afetados pelo WhatsApp oferecendo remarcação</label>
          <div className="flex gap-2 sm:col-span-3"><button className="botao-secundario" onClick={verPrevia}>Ver quem é afetado</button><button className="botao-primario" disabled={f.data_fim < f.data_inicio} onClick={salvar}>Salvar</button>{f.data_fim < f.data_inicio && <span className="self-center text-xs text-rose-600">A data final é antes da inicial.</span>}</div>
        </div>
      )}
      <Erro texto={falha} />
      {resultado && <p className="rounded-md bg-marca-50 px-3 py-2 text-sm text-marca-700">{resultado}</p>}
      {previa && <div><h3 className="mb-1 text-sm font-semibold">Quem precisa remarcar ({previa.length})</h3><ListaAgenda itens={previa} recarregar={verPrevia} mostrarData vazio="Ninguém marcado nesse período (quem já passou do horário não entra)." /></div>}
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-slate-700">{passadas ? "Já passadas" : "Atuais e futuras"}</h3>
        <button className="botao-secundario" onClick={() => setPassadas(!passadas)}>{passadas ? "Ver atuais e futuras" : "Ver as que já passaram"}</button>
      </div>
      {lista.length === 0 ? <Vazio texto={passadas ? "Nenhuma folga, férias ou feriado no passado." : "Nenhuma folga, férias ou feriado daqui para a frente."} /> : (
        <table className="tabela tabela-cartao"><thead><tr><th>Quem</th><th>Tipo</th><th>Período</th><th>Turno</th><th>Motivo</th><th></th></tr></thead>
          <tbody>{lista.map((e) => (
            <tr key={e.id}>
              <td>{e.profissional_id ? String(cat.profissionais.find((p) => p.id === e.profissional_id)?.nome ?? "(sem nome)") : "Clínica toda"}</td>
              <td>{TIPO_EXCECAO[String(e.tipo)] ?? String(e.tipo)}</td><td className="whitespace-nowrap">{e.data_inicio === e.data_fim ? dataCurta(String(e.data_inicio)) : `${dataCurta(String(e.data_inicio))} a ${dataCurta(String(e.data_fim))}`}</td>
              <td>{e.turno ? (e.turno === "MANHA" ? "manhã" : "tarde") : "dia todo"}</td><td>{String(e.motivo ?? "—")}</td>
              <td>{pode(...EQUIPE) && !passadas && <button className="botao-secundario" onClick={() => api.del(`/excecoes/${e.id}`).then(recarregar)}>Excluir</button>}</td>
            </tr>
          ))}</tbody></table>
      )}
    </div>
  );
}

export default function GradePagina() {
  const [aba, setAba] = useState("grade");
  return (
    <>
      <Cabecalho titulo="Grade, folgas e feriados" />
      <Abas abas={[["grade", "Grade semanal"], ["excecoes", "Férias, folgas e feriados"]]} ativa={aba} mudar={setAba} />
      <div className="cartao">{aba === "grade" ? <GradeSemanal /> : <Excecoes />}</div>
    </>
  );
}
