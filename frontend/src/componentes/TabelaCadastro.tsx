import { useState } from "react";
import { api, qs } from "../api";
import type { Registro } from "../tipos";
import { Carregando, Erro, Modal, useRecurso, Vazio } from "./ui";

export interface Campo {
  chave: string; rotulo: string; tipo?: "texto" | "numero" | "bool" | "data" | "opcoes";
  opcoes?: { valor: string | number; rotulo: string }[]; naLista?: boolean; somenteCriar?: boolean;
}

interface Props { recurso: string; campos: Campo[]; podeEditar: boolean; busca?: boolean }

function exibir(c: Campo, v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (c.tipo === "bool") return v ? "sim" : "não";
  if (c.tipo === "opcoes") return c.opcoes?.find((o) => String(o.valor) === String(v))?.rotulo ?? String(v);
  return String(v);
}

export default function TabelaCadastro({ recurso, campos, podeEditar, busca }: Props) {
  const [q, setQ] = useState("");
  const [lista, erro, recarregar] = useRecurso(() => api.get<Registro[]>(`/${recurso}${qs({ q })}`), [recurso, q]);
  const [edicao, setEdicao] = useState<Registro | null>(null);
  const [falha, setFalha] = useState<string | null>(null);
  const visiveis = campos.filter((c) => c.naLista !== false);

  async function salvar() {
    if (!edicao) return;
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
      <div className="mb-3 flex flex-wrap gap-2">
        {busca && <input className="campo max-w-xs" placeholder="Buscar…" value={q} onChange={(e) => setQ(e.target.value)} />}
        {podeEditar && <button className="botao-primario ml-auto" onClick={() => setEdicao({})}>+ Novo</button>}
      </div>
      <Erro texto={erro} />
      {!lista ? <Carregando /> : lista.length === 0 ? <Vazio texto="Nenhum registro." /> : (
        <div className="overflow-x-auto">
          <table className="tabela">
            <thead><tr>{visiveis.map((c) => <th key={c.chave}>{c.rotulo}</th>)}{podeEditar && <th></th>}</tr></thead>
            <tbody>{lista.map((r) => (
              <tr key={String(r.id ?? r.chave)}>
                {visiveis.map((c) => <td key={c.chave}>{exibir(c, r[c.chave])}</td>)}
                {podeEditar && <td className="text-right"><button className="botao-secundario" onClick={() => setEdicao({ ...r })}>Editar</button></td>}
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <Modal titulo={edicao?.id ? "Editar" : "Novo"} aberto={!!edicao} fechar={() => setEdicao(null)}>
        {edicao && (
          <div className="space-y-3">
            <Erro texto={falha} />
            {campos.filter((c) => !(edicao.id && c.somenteCriar)).map((c) => {
              const v = edicao[c.chave];
              const mudar = (x: unknown) => setEdicao({ ...edicao, [c.chave]: x });
              return (
                <div key={c.chave}>
                  {c.tipo === "bool" ? (
                    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!v} onChange={(e) => mudar(e.target.checked)} />{c.rotulo}</label>
                  ) : (
                    <>
                      <label className="rotulo">{c.rotulo}</label>
                      {c.tipo === "opcoes" ? (
                        <select className="campo" value={v === null || v === undefined ? "" : String(v)} onChange={(e) => mudar(e.target.value)}>
                          <option value="">—</option>{c.opcoes?.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
                        </select>
                      ) : (
                        <input className="campo" type={c.tipo === "numero" ? "number" : c.tipo === "data" ? "date" : "text"} value={v === null || v === undefined ? "" : String(v)} onChange={(e) => mudar(e.target.value)} />
                      )}
                    </>
                  )}
                </div>
              );
            })}
            <div className="flex justify-end gap-2"><button className="botao-secundario" onClick={() => setEdicao(null)}>Cancelar</button><button className="botao-primario" onClick={salvar}>Salvar</button></div>
          </div>
        )}
      </Modal>
    </div>
  );
}
