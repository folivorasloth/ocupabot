import { Link } from "react-router-dom";
import { api, qs } from "../api";
import ListaAgenda from "../componentes/ListaAgenda";
import { Cabecalho, Carregando, Erro, useRecurso } from "../componentes/ui";
import { dataCurta } from "../formato";
import type { Agendamento } from "../tipos";

interface Resumo {
  data: string; agendamentos: Record<string, number>; aprovacoes_pendentes: number; conversas_esperando: number;
  conversas_com_equipe: number; proximos_7_dias: number; alertas: { nivel: string; texto: string }[];
}

const COR = { erro: "bg-rose-50 text-rose-800 border-rose-200", aviso: "bg-amber-50 text-amber-800 border-amber-200", info: "bg-sky-50 text-sky-800 border-sky-200" };

function Numero({ rotulo, valor, para }: { rotulo: string; valor: number; para?: string }) {
  const corpo = (<div className="cartao"><div className="text-2xl font-semibold text-slate-800">{valor}</div><div className="text-xs text-slate-500">{rotulo}</div></div>);
  return para ? <Link to={para} className="block hover:opacity-80">{corpo}</Link> : corpo;
}

export default function Hoje() {
  const [r, erro, recarregar] = useRecurso(() => api.get<Resumo>("/painel/hoje"), [], 30000);
  const [agenda, , recarregarAgenda] = useRecurso(() => api.get<Agendamento[]>(`/agenda${qs({})}`), [], 30000);
  if (!r) return erro ? <Erro texto={erro} /> : <Carregando />;
  const total = Object.values(r.agendamentos).reduce((a, b) => a + b, 0);
  return (
    <>
      <Cabecalho titulo="Hoje" sub={dataCurta(r.data)} />
      <div className="mb-4 space-y-2">
        {r.alertas.map((a, i) => <div key={i} className={`rounded-md border px-3 py-2 text-sm ${COR[a.nivel as keyof typeof COR] ?? COR.info}`}>{a.texto}</div>)}
      </div>
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Numero rotulo="agendamentos hoje" valor={total} />
        <Numero rotulo="compareceram" valor={r.agendamentos.COMPARECEU ?? 0} />
        <Numero rotulo="aprovações pendentes" valor={r.aprovacoes_pendentes} para="/aprovacoes" />
        <Numero rotulo="conversas esperando a equipe" valor={r.conversas_esperando} para="/conversas" />
        <Numero rotulo="agendados nos próximos 7 dias" valor={r.proximos_7_dias} para="/agenda" />
      </div>
      <div className="cartao">
        <h2 className="mb-2 font-semibold text-slate-700">Agenda do dia</h2>
        {agenda ? <ListaAgenda itens={agenda} recarregar={() => { recarregar(); recarregarAgenda(); }} /> : <Carregando />}
      </div>
    </>
  );
}
