import { useState } from "react";
import { api } from "../api";
import { Aviso, Erro, Lista, useRecurso } from "../componentes/ui";
import { cnpj, dataCurta, plural } from "../formato";

interface Linha {
  id: number; nome: string; cnpj: string | null; elaborado_por: "CLINICA" | "TERCEIRO" | null; vence_em: string | null;
  recebido: boolean; situacao: string; a_cobrar: boolean; sem_documento: boolean;
}

const SITUACAO: Record<string, { rotulo: string; cor: string }> = {
  EM_DIA: { rotulo: "Em dia", cor: "bg-emerald-100 text-emerald-800" },
  VENCE: { rotulo: "Vence em breve", cor: "bg-amber-100 text-amber-800" },
  VENCIDO: { rotulo: "Vencido", cor: "bg-rose-100 text-rose-800" },
  NAO_RECEBIDO: { rotulo: "Documento não recebido", cor: "bg-amber-100 text-amber-800" },
  NAO_ACOMPANHADO: { rotulo: "Não acompanhado", cor: "bg-slate-100 text-slate-600" },
};
const FILTROS: [string, string, (l: Linha) => boolean][] = [
  ["cobrar", "A cobrar", (l) => l.a_cobrar],
  ["acompanhadas", "Acompanhadas", (l) => l.elaborado_por !== null],
  ["sem", "Não acompanhadas", (l) => l.elaborado_por === null],
  ["todas", "Todas", () => true],
];

/** Situação do PCMSO de todas as empresas ativas, com "marcar recebido" na linha. */
export default function Pcmso({ podeEditar }: { podeEditar: boolean }) {
  const [dados, erro, recarregar] = useRecurso(() => api.get<{ alerta_dias: number; empresas: Linha[] }>("/painel/pcmso"));
  const [filtro, setFiltro] = useState("cobrar");
  const [falha, setFalha] = useState<string | null>(null);
  const [feito, setFeito] = useState<string | null>(null);
  const teste = FILTROS.find((f) => f[0] === filtro)![2];

  async function recebido(l: Linha) {
    setFalha(null);
    try {
      await api.patch(`/empresas/${l.id}`, { pcmso_recebido: true });
      setFeito(`PCMSO de ${l.nome} marcado como recebido.`);
      recarregar();
    } catch (e) { setFalha((e as Error).message); }
  }

  return (
    <div>
      <p className="mb-3 text-sm text-slate-600">Quem fez o PCMSO de cada empresa, até quando vale e se o documento em vigor chegou. Para mudar, edite a empresa na aba Empresas. A cobrar: vencido, vencendo em {dados?.alerta_dias ?? 30} dias ou documento que ainda não chegou.</p>
      <div className="mb-3 flex flex-wrap gap-1">
        {FILTROS.map(([id, rotulo, t]) => (
          <button key={id} onClick={() => setFiltro(id)} className={`rounded-full border px-3 py-1 text-sm ${filtro === id ? "border-marca-600 bg-marca-50 font-medium text-marca-700" : "border-slate-300 text-slate-600"}`}>
            {rotulo}{dados ? ` (${dados.empresas.filter(t).length})` : ""}
          </button>
        ))}
      </div>
      <Erro texto={falha} />
      <Aviso texto={feito} />
      <Lista dados={dados ? dados.empresas.filter(teste) : null} erro={erro} vazio={filtro === "cobrar" ? "Nenhum PCMSO a cobrar." : "Nenhuma empresa neste filtro."}>{(itens) => (
        <>
          <p className="mb-2 text-xs text-slate-500">{plural(itens.length, "empresa", "empresas")}</p>
          <div className="overflow-x-auto">
            <table className="tabela tabela-cartao"><thead><tr><th>Empresa</th><th>Situação</th><th>Quem fez</th><th>Vale até</th><th>Documento</th><th></th></tr></thead>
              <tbody>{itens.map((l) => (
                <tr key={l.id}>
                  <td>{l.nome || "(sem nome)"}<div className="whitespace-nowrap text-xs text-slate-500">{cnpj(l.cnpj)}</div></td>
                  <td><span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${SITUACAO[l.situacao]?.cor}`}>{SITUACAO[l.situacao]?.rotulo ?? l.situacao}</span></td>
                  <td>{l.elaborado_por === "CLINICA" ? "A clínica" : l.elaborado_por === "TERCEIRO" ? "Outra empresa" : "—"}</td>
                  <td className="whitespace-nowrap">{l.vence_em ? dataCurta(l.vence_em) : "—"}</td>
                  <td>{l.elaborado_por === "TERCEIRO" ? (l.recebido ? "recebido" : "não chegou") : "—"}</td>
                  <td className="text-right">{podeEditar && l.sem_documento && <button className="botao-secundario" onClick={() => recebido(l)}>Marcar recebido</button>}</td>
                </tr>
              ))}</tbody></table>
          </div>
        </>
      )}</Lista>
    </div>
  );
}
