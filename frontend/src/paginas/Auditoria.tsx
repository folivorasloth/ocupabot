import { useState } from "react";
import { api, qs } from "../api";
import { Cabecalho, Carregando, Erro, useRecurso, Vazio } from "../componentes/ui";
import { dataHora } from "../formato";

interface Registro { id: number; em: string; usuario_id: number | null; ator: string; entidade: string; entidade_id: string; acao: string; antes: Record<string, unknown> | null; depois: Record<string, unknown> | null }

export default function AuditoriaPagina() {
  const [entidade, setEntidade] = useState("");
  const [lista, erro] = useRecurso(() => api.get<Registro[]>(`/auditoria${qs({ entidade })}`), [entidade]);
  return (
    <>
      <Cabecalho titulo="Auditoria" sub="Toda alteração feita pelo painel, pelo bot ou pelo sistema.">
        <select className="campo w-48" value={entidade} onChange={(e) => setEntidade(e.target.value)}>
          <option value="">Tudo</option>{["agendamento", "aprovacao", "conversa", "usuario", "parametro", "texto", "grade", "excecao", "empresa", "paciente"].map((x) => <option key={x}>{x}</option>)}
        </select>
      </Cabecalho>
      <Erro texto={erro} />
      <div className="cartao">{!lista ? <Carregando /> : lista.length === 0 ? <Vazio texto="Sem registros." /> : (
        <table className="tabela"><thead><tr><th>Quando</th><th>Quem</th><th>O quê</th><th>Mudança</th></tr></thead>
          <tbody>{lista.map((r) => (
            <tr key={r.id}>
              <td className="whitespace-nowrap">{dataHora(r.em)}</td>
              <td>{r.ator}{r.usuario_id ? ` #${r.usuario_id}` : ""}</td>
              <td>{r.entidade} #{r.entidade_id}<div className="text-xs text-slate-500">{r.acao}</div></td>
              <td className="font-mono text-[11px] text-slate-600">
                {Object.keys(r.depois ?? r.antes ?? {}).slice(0, 8).map((k) => (
                  <div key={k}>{k}: {r.antes && k in r.antes ? <><span className="text-rose-600 line-through">{String(r.antes[k])}</span> → </> : null}<span className="text-emerald-700">{String(r.depois?.[k] ?? "")}</span></div>
                ))}
              </td>
            </tr>
          ))}</tbody></table>
      )}</div>
    </>
  );
}
