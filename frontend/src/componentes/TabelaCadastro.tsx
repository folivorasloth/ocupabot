import { useState } from "react";
import { api, qs } from "../api";
import { plural } from "../formato";
import type { Registro } from "../tipos";
import { Erro, Lista, Modal, useRecurso } from "./ui";

export interface Campo {
  chave: string; rotulo: string; tipo?: "texto" | "numero" | "bool" | "data" | "opcoes";
  opcoes?: { valor: string | number; rotulo: string }[]; naLista?: boolean; somenteCriar?: boolean;
  obrigatorio?: boolean; ajuda?: string; formato?: (v: unknown) => string;
}

interface Props {
  recurso: string; campos: Campo[]; podeEditar: boolean; busca?: boolean;
  /** "empresa" / "empresas": o contador da lista em português. */
  nome: [string, string];
  /** Caixa de marcar acima da lista que mostra só parte dos registros (ex.: "só PCMSO a cobrar"). */
  filtro?: { rotulo: string; teste: (r: Registro) => boolean };
}

function exibir(c: Campo, v: unknown): string {
  if (v === null || v === undefined || v === "") return c.chave.startsWith("nome") || c.chave === "razao_social" ? "(sem nome)" : "—";
  if (c.formato) return c.formato(v);
  if (c.tipo === "bool") return v ? "sim" : "não";
  if (c.tipo === "opcoes") return c.opcoes?.find((o) => String(o.valor) === String(v))?.rotulo ?? String(v);
  if (c.tipo === "data") return String(v).split("-").reverse().join("/");
  return String(v);
}

export default function TabelaCadastro({ recurso, campos, podeEditar, busca, nome, filtro }: Props) {
  const [q, setQ] = useState("");
  const [so, setSo] = useState(false);
  const [lista, erro, recarregar] = useRecurso(() => api.get<Registro[]>(`/${recurso}${qs({ q })}`), [recurso, q]);
  const [edicao, setEdicao] = useState<Registro | null>(null);
  const [falha, setFalha] = useState<string | null>(null);
  const visiveis = campos.filter((c) => c.naLista !== false);
  const mostrados = lista && filtro && so ? lista.filter(filtro.teste) : lista;
  const falta = edicao ? campos.filter((c) => c.obrigatorio && !(edicao.id && c.somenteCriar) && (edicao[c.chave] === undefined || edicao[c.chave] === null || String(edicao[c.chave]).trim() === "")) : [];

  async function salvar() {
    if (!edicao || falta.length) return;
    setFalha(null);
    const corpo: Registro = {};
    for (const c of campos) {
      if (edicao.id && c.somenteCriar) continue;
      let v = edicao[c.chave];
      if (v === "" || v === undefined) v = c.tipo === "bool" ? false : null;
      if ((c.tipo === "numero" || (c.tipo === "opcoes" && typeof c.opcoes?.[0]?.valor === "number")) && v !== null) v = Number(v);
      if (c.chave === "cpf" && typeof v === "string" && v.includes("*")) continue;
      corpo[c.chave] = v;
    }
    try {
      if (edicao.id) await api.patch(`/${recurso}/${edicao.id}`, corpo); else await api.post(`/${recurso}`, corpo);
      setEdicao(null);
      recarregar();
    } catch (e) { setFalha((e as Error).message); }
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {busca && <input className="campo max-w-xs" placeholder="Buscar…" aria-label="Buscar" value={q} onChange={(e) => setQ(e.target.value)} />}
        {filtro && <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={so} onChange={(e) => setSo(e.target.checked)} />{filtro.rotulo}</label>}
        {mostrados && !erro && <span className="text-xs text-slate-500">{plural(mostrados.length, nome[0], nome[1])}</span>}
        {podeEditar && <button className="botao-primario ml-auto" onClick={() => { setFalha(null); setEdicao({}); }}>+ Novo</button>}
      </div>
      <Lista dados={mostrados} erro={erro} vazio={q || so ? `Nada encontrado com esse filtro.` : `Nenhum registro ainda.`}>{(itens) => (
        <div className="overflow-x-auto">
          <table className="tabela tabela-cartao">
            <thead><tr>{visiveis.map((c) => <th key={c.chave}>{c.rotulo}</th>)}{podeEditar && <th></th>}</tr></thead>
            <tbody>{itens.map((r) => (
              <tr key={String(r.id ?? r.chave)}>
                {visiveis.map((c) => <td key={c.chave} data-rotulo={c.rotulo}>{exibir(c, r[c.chave])}</td>)}
                {podeEditar && <td className="text-right"><button className="botao-secundario" onClick={() => { setFalha(null); setEdicao({ ...r }); }}>Editar</button></td>}
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}</Lista>
      <Modal titulo={edicao?.id ? `Alterar ${nome[0]}` : `Cadastrar ${nome[0]}`} aberto={!!edicao} fechar={() => setEdicao(null)}>
        {edicao && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); salvar(); }}>
            <Erro texto={falha} />
            {campos.filter((c) => !(edicao.id && c.somenteCriar)).map((c) => {
              const v = edicao[c.chave];
              const mudar = (x: unknown) => setEdicao({ ...edicao, [c.chave]: x });
              const id = `campo-${c.chave}`;
              const ajuda = c.ajuda && <p id={`${id}-ajuda`} className="mt-1 text-xs text-slate-500">{c.ajuda}</p>;
              return (
                <div key={c.chave}>
                  {c.tipo === "bool" ? (
                    <><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!v} onChange={(e) => mudar(e.target.checked)} aria-describedby={c.ajuda ? `${id}-ajuda` : undefined} />{c.rotulo}</label>{ajuda}</>
                  ) : (
                    <>
                      <label className="rotulo" htmlFor={id}>{c.rotulo}{c.obrigatorio ? " *" : ""}</label>
                      {c.tipo === "opcoes" ? (
                        <select id={id} className="campo" value={v === null || v === undefined ? "" : String(v)} onChange={(e) => mudar(e.target.value)} aria-describedby={c.ajuda ? `${id}-ajuda` : undefined}>
                          <option value="">—</option>{c.opcoes?.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
                        </select>
                      ) : (
                        <input id={id} className="campo" type={c.tipo === "numero" ? "number" : c.tipo === "data" ? "date" : "text"} value={v === null || v === undefined ? "" : String(v)} onChange={(e) => mudar(e.target.value)} aria-describedby={c.ajuda ? `${id}-ajuda` : undefined} />
                      )}
                      {ajuda}
                    </>
                  )}
                </div>
              );
            })}
            {falta.length > 0 && <p className="text-xs text-slate-500">Falta preencher: {falta.map((c) => c.rotulo).join(", ")}. Os campos com * são obrigatórios.</p>}
            <div className="flex justify-end gap-2"><button type="button" className="botao-secundario" onClick={() => setEdicao(null)}>Cancelar</button><button className="botao-primario" disabled={falta.length > 0}>Salvar</button></div>
          </form>
        )}
      </Modal>
    </div>
  );
}
