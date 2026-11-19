import { useState } from "react";
import { api, qs } from "../api";
import { nomeEmpresa, useCatalogo } from "../componentes/catalogo";
import EscolherHorario from "../componentes/EscolherHorario";
import ListaAgenda from "../componentes/ListaAgenda";
import { Cabecalho, Carregando, Erro, Modal, useRecurso } from "../componentes/ui";
import { dataCurta, hojeIso, somarDias } from "../formato";
import { EQUIPE, useSessao } from "../sessao";
import type { Agendamento } from "../tipos";

interface Contagem { data: string; turno: string; exame: string; quantos: number }

/** Quantos de cada exame há no período, para avisar quem atende: no dia, manhã e tarde; na semana, cada dia. */
function ExamesDoPeriodo({ de, ate, versao }: { de: string; ate: string; versao: number }) {
  const [linhas] = useRecurso(() => api.get<Contagem[]>(`/agenda/exames${qs({ de, ate })}`), [de, ate, versao]);
  if (!linhas || linhas.length === 0) return null;
  const umDia = de === ate;
  const colunas = umDia ? ["MANHA", "TARDE"] : [...new Set(linhas.map((l) => l.data))].sort();
  const exames = [...new Set(linhas.map((l) => l.exame))];
  const soma = (exame: string | null, coluna: string | null) => linhas
    .filter((l) => (!exame || l.exame === exame) && (!coluna || (umDia ? l.turno : l.data) === coluna)).reduce((n, l) => n + l.quantos, 0);
  return (
    <div className="cartao mt-4">
      <h2 className="mb-2 font-semibold text-slate-700">Quantos de cada exame</h2>
      <div className="overflow-x-auto">
        <table className="tabela">
          <thead><tr><th>Exame</th>{colunas.map((c) => <th key={c} className="text-right">{umDia ? (c === "MANHA" ? "Manhã" : "Tarde") : dataCurta(c)}</th>)}<th className="text-right">Total</th></tr></thead>
          <tbody>
            {exames.map((e) => <tr key={e}><td>{e}</td>{colunas.map((c) => <td key={c} className="text-right">{soma(e, c) || "—"}</td>)}<td className="text-right font-medium">{soma(e, null)}</td></tr>)}
            <tr><td className="font-medium">Total</td>{colunas.map((c) => <td key={c} className="text-right font-medium">{soma(null, c)}</td>)}<td className="text-right font-semibold">{soma(null, null)}</td></tr>
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-xs text-slate-500">Conta o que está agendado, confirmado, atendido ou esperando aprovação. Cancelado, falta e agendamento de teste não entram.</p>
    </div>
  );
}

function NovoAgendamento({ fechar, criado }: { fechar: () => void; criado: (data: string) => void }) {
  const [cat] = useCatalogo();
  const [f, setF] = useState({ paciente_nome: "", paciente_cpf: "", paciente_nascimento: "", empresa_id: "", tipo_aso_id: "", contato_telefone: "", observacao: "" });
  const [exames, setExames] = useState<number[]>([]);
  const [quando, setQuando] = useState({ data: hojeIso(), horario: "" });
  const [erro, setErro] = useState<string | null>(null);
  const { pode } = useSessao();
  if (!cat) return <Carregando />;
  // nome começando com TESTE: agendamento de teste (ocupa a vaga, não manda WhatsApp nem conta nos números)
  const teste = /^\s*teste(\s|$)/i.test(f.paciente_nome);
  const noExterno = !!cat.empresas.find((e) => String(e.id) === f.empresa_id)?.usa_sistema_externo && !teste;
  const mudar = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function salvar() {
    setErro(null);
    try {
      await api.post("/agendamentos", {
        ...f, empresa_id: f.empresa_id ? Number(f.empresa_id) : null, tipo_aso_id: f.tipo_aso_id ? Number(f.tipo_aso_id) : null,
        paciente_nascimento: f.paciente_nascimento || null, paciente_cpf: f.paciente_cpf || null, contato_telefone: f.contato_telefone || null,
        exame_ids: exames, data: quando.data, horario: quando.horario,
      });
      criado(quando.data);
    } catch (e) { setErro((e as Error).message); }
  }

  return (
    <div className="space-y-3">
      <Erro texto={erro} />
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><label className="rotulo">Paciente *</label><input className="campo" value={f.paciente_nome} onChange={mudar("paciente_nome")} placeholder="Nome completo" />
          {teste && <p className={`mt-1 text-xs ${pode("SUPERVISAO") ? "text-violet-800" : "text-rose-600"}`}>{pode("SUPERVISAO") ? "Agendamento de teste: ocupa a vaga, mas não manda WhatsApp nem conta nos números. Depois dá para apagar na lista." : "Nome começando com TESTE cria um agendamento de teste, que é só com a Supervisão."}</p>}</div>
        <div><label className="rotulo">CPF{noExterno ? " *" : ""}</label><input className="campo" value={f.paciente_cpf} onChange={mudar("paciente_cpf")} inputMode="numeric" />
          {noExterno && <p className="mt-1 text-xs text-slate-500">Esta empresa é lançada no sistema de gestão, que acha o funcionário pelo CPF.</p>}</div>
        <div><label className="rotulo">Nascimento</label><input type="date" className="campo" value={f.paciente_nascimento} onChange={mudar("paciente_nascimento")} /></div>
        <div><label className="rotulo">Empresa</label><select className="campo" value={f.empresa_id} onChange={mudar("empresa_id")}><option value="">Particular</option>{cat.empresas.map((e) => <option key={e.id} value={e.id}>{nomeEmpresa(e)}</option>)}</select></div>
        <div><label className="rotulo">Tipo de ASO</label><select className="campo" value={f.tipo_aso_id} onChange={mudar("tipo_aso_id")}><option value="">—</option>{cat.tipos.map((t) => <option key={t.id} value={t.id}>{String(t.nome)}</option>)}</select></div>
        <div className="sm:col-span-2"><label className="rotulo">WhatsApp para avisos (opcional)</label><input className="campo" value={f.contato_telefone} onChange={mudar("contato_telefone")} placeholder="DDD + número" inputMode="tel" />
          {!f.contato_telefone && <p className="mt-1 text-xs text-amber-700">Sem WhatsApp, ninguém recebe confirmação nem lembrete deste agendamento.</p>}</div>
      </div>
      <div>
        <label className="rotulo">Exames *</label>
        <div className="grid grid-cols-2 gap-1">
          {cat.exames.map((e) => (
            <label key={e.id} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={exames.includes(e.id!)} onChange={(ev) => { setQuando({ ...quando, horario: "" }); setExames(ev.target.checked ? [...exames, e.id!] : exames.filter((x) => x !== e.id)); }} />{String(e.nome)}
            </label>
          ))}
        </div>
      </div>
      <EscolherHorario exames={exames} data={quando.data} horario={quando.horario} mudar={(data, horario) => setQuando({ data, horario })} />
      <div><label className="rotulo">Observação (sem CPF, RG nem dado de saúde)</label><textarea className="campo" rows={2} value={f.observacao} onChange={mudar("observacao")} maxLength={2000} /></div>
      {quando.horario && <p className="text-sm text-slate-700">Horário escolhido: <b>{dataCurta(quando.data)} às {quando.horario}</b></p>}
      <div className="flex justify-end gap-2">
        <button className="botao-secundario" onClick={fechar}>Fechar</button>
        <button className="botao-primario" disabled={!f.paciente_nome || !exames.length || !quando.horario || (noExterno && !f.paciente_cpf.trim())} onClick={salvar}>{teste ? "Agendar teste" : "Agendar"}</button>
      </div>
    </div>
  );
}

export default function AgendaPagina() {
  const { pode } = useSessao();
  const [de, setDe] = useState(hojeIso());
  const [dias, setDias] = useState(1);
  const [novo, setNovo] = useState(false);
  const [versao, setVersao] = useState(0);
  const ate = somarDias(de, dias - 1);
  const [itens, erro, recarregarLista] = useRecurso(() => api.get<Agendamento[]>(`/agenda${qs({ de, ate })}`), [de, ate]);
  const recarregar = () => { recarregarLista(); setVersao((v) => v + 1); };
  return (
    <>
      <Cabecalho titulo="Agenda">
        <button className="botao-secundario" aria-label="Período anterior" onClick={() => setDe(somarDias(de, -dias))}>←</button>
        <input type="date" className="campo w-40" aria-label="Dia" value={de} onChange={(e) => e.target.value && setDe(e.target.value)} />
        <button className="botao-secundario" aria-label="Próximo período" onClick={() => setDe(somarDias(de, dias))}>→</button>
        {de !== hojeIso() && <button className="botao-secundario" onClick={() => setDe(hojeIso())}>Hoje</button>}
        <select className="campo w-28" value={dias} onChange={(e) => setDias(Number(e.target.value))}><option value={1}>Dia</option><option value={7}>Semana</option><option value={31}>Mês</option></select>
        {pode(...EQUIPE) && <button className="botao-primario" onClick={() => setNovo(true)}>+ Novo agendamento</button>}
      </Cabecalho>
      <div className="cartao">{erro ? <Erro texto={erro} /> : itens ? <ListaAgenda itens={itens} recarregar={recarregar} mostrarData={dias > 1} /> : <Carregando />}</div>
      {dias <= 7 && <ExamesDoPeriodo de={de} ate={ate} versao={versao} />}
      <Modal titulo="Novo agendamento" aberto={novo} fechar={() => setNovo(false)} largo>
        <NovoAgendamento fechar={() => setNovo(false)} criado={(data) => { setNovo(false); setDias(1); setDe(data); recarregar(); }} />
      </Modal>
    </>
  );
}
