import { useState } from "react";
import { Link } from "react-router-dom";
import { api, qs } from "../api";
import ListaAgenda from "../componentes/ListaAgenda";
import { Abas, Cabecalho, Carregando, Erro, useRecurso } from "../componentes/ui";
import { dataCurta, plural } from "../formato";
import type { Agendamento, Contadores } from "../tipos";

interface Resumo extends Contadores {
  data: string; agendamentos: Record<string, number>; proximos_7_dias: number;
  alertas: { nivel: string; texto: string; para?: string }[];
}

const COR = { erro: "bg-rose-50 text-rose-800 border-rose-200", aviso: "bg-amber-50 text-amber-800 border-amber-200", info: "bg-sky-50 text-sky-800 border-sky-200" };

// A lista do dia em abas: quem ainda vem, quem já chegou, quem faltou e o que foi cancelado
const ABAS: { id: string; rotulo: string; status: string[]; vazio: string }[] = [
  { id: "chegar", rotulo: "A chegar", status: ["AGENDADO", "CONFIRMADO", "AGUARDANDO_APROVACAO"], vazio: "Ninguém mais para chegar hoje." },
  { id: "chegaram", rotulo: "Já chegaram", status: ["COMPARECEU"], vazio: "Ninguém com presença marcada ainda." },
  { id: "faltas", rotulo: "Faltas", status: ["FALTOU"], vazio: "Nenhuma falta marcada hoje." },
  { id: "cancelados", rotulo: "Cancelados", status: ["CANCELADO", "REMARCADO"], vazio: "Nada cancelado nem remarcado hoje." },
];

function Numero({ rotulo, valor, para, dica }: { rotulo: string; valor: number; para?: string; dica?: string }) {
  const corpo = (<div className="cartao h-full"><div className="text-2xl font-semibold text-slate-800">{valor}</div><div className="text-xs text-slate-500">{rotulo}</div>{dica && <div className="mt-1 text-[11px] text-slate-400">{dica}</div>}</div>);
  return para ? <Link to={para} className="block hover:opacity-80">{corpo}</Link> : corpo;
}

export default function Hoje() {
  const [r, erro, recarregar] = useRecurso(() => api.get<Resumo>("/painel/hoje"), [], 30000);
  const [agenda, erroAgenda, recarregarAgenda] = useRecurso(() => api.get<Agendamento[]>(`/agenda${qs({})}`), [], 30000);
  const [aba, setAba] = useState("chegar");
  if (!r) return erro ? <Erro texto={erro} /> : <Carregando />;
  const ativos = (r.agendamentos.AGENDADO ?? 0) + (r.agendamentos.CONFIRMADO ?? 0);
  const conta = (status: string[]) => (agenda ?? []).filter((a) => status.includes(a.status)).length;
  const atual = ABAS.find((a) => a.id === aba)!;
  const alertas = (
    <div className="mb-4 space-y-2">
      {r.alertas.map((a, i) => {
        const cor = `block rounded-md border px-3 py-2 text-sm ${COR[a.nivel as keyof typeof COR] ?? COR.info}`;
        return a.para ? <Link key={i} to={a.para} className={`${cor} underline-offset-2 hover:underline`}>{a.texto}</Link> : <div key={i} className={cor}>{a.texto}</div>;
      })}
    </div>
  );
  return (
    <>
      <Cabecalho titulo="Hoje" sub={dataCurta(r.data)} />
      {alertas}
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Numero rotulo="a chegar hoje" valor={ativos} />
        <Numero rotulo="compareceram hoje" valor={r.agendamentos.COMPARECEU ?? 0} />
        <Numero rotulo="pedidos do bot esperando" valor={r.aprovacoes_pendentes} para="/aprovacoes" dica={r.esperando_cliente ? `${plural(r.esperando_cliente, "proposta espera", "propostas esperam")} o cliente` : "conta todos os dias, não só hoje"} />
        <Numero rotulo="conversas esperando a equipe" valor={r.conversas_esperando} para="/conversas" />
        <Numero rotulo="agendados nos próximos 7 dias" valor={r.proximos_7_dias} para="/agenda" />
      </div>
      <div className="cartao">
        <h2 className="mb-2 font-semibold text-slate-700">Agenda do dia</h2>
        <Erro texto={erroAgenda} />
        {!agenda ? (erroAgenda ? null : <Carregando />) : (
          <>
            <Abas abas={ABAS.map((a) => [a.id, `${a.rotulo} (${conta(a.status)})`])} ativa={aba} mudar={setAba} />
            <ListaAgenda itens={agenda.filter((a) => atual.status.includes(a.status))} vazio={atual.vazio} recarregar={() => { recarregar(); recarregarAgenda(); }} />
          </>
        )}
      </div>
    </>
  );
}
