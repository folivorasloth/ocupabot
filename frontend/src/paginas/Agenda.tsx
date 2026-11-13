import { useState } from "react";
import { api, qs } from "../api";
import { nomeEmpresa, useCatalogo } from "../componentes/catalogo";
import EscolherHorario from "../componentes/EscolherHorario";
import ListaAgenda from "../componentes/ListaAgenda";
import { Cabecalho, Carregando, Erro, Modal, useRecurso } from "../componentes/ui";
import { dataCurta, hojeIso, somarDias } from "../formato";
import { EQUIPE, useSessao } from "../sessao";
import type { Agendamento } from "../tipos";

function NovoAgendamento({ fechar, criado }: { fechar: () => void; criado: (data: string) => void }) {
  const [cat] = useCatalogo();
  const [f, setF] = useState({ paciente_nome: "", paciente_cpf: "", paciente_nascimento: "", empresa_id: "", tipo_aso_id: "", contato_telefone: "", observacao: "" });
  const [exames, setExames] = useState<number[]>([]);
  const [quando, setQuando] = useState({ data: hojeIso(), horario: "" });
  const [erro, setErro] = useState<string | null>(null);
  if (!cat) return <Carregando />;
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
        <div className="sm:col-span-2"><label className="rotulo">Paciente *</label><input className="campo" value={f.paciente_nome} onChange={mudar("paciente_nome")} placeholder="Nome completo" /></div>
        <div><label className="rotulo">CPF</label><input className="campo" value={f.paciente_cpf} onChange={mudar("paciente_cpf")} inputMode="numeric" /></div>
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
        <button className="botao-primario" disabled={!f.paciente_nome || !exames.length || !quando.horario} onClick={salvar}>Agendar</button>
      </div>
    </div>
  );
}

export default function AgendaPagina() {
  const { pode } = useSessao();
  const [de, setDe] = useState(hojeIso());
  const [dias, setDias] = useState(1);
  const [novo, setNovo] = useState(false);
  const ate = somarDias(de, dias - 1);
  const [itens, erro, recarregar] = useRecurso(() => api.get<Agendamento[]>(`/agenda${qs({ de, ate })}`), [de, ate]);
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
      <Modal titulo="Novo agendamento" aberto={novo} fechar={() => setNovo(false)} largo>
        <NovoAgendamento fechar={() => setNovo(false)} criado={(data) => { setNovo(false); setDias(1); setDe(data); recarregar(); }} />
      </Modal>
    </>
  );
}
