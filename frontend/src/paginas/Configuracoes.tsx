import { useState } from "react";
import { api } from "../api";
import { Abas, Cabecalho, Carregando, Erro, useRecurso } from "../componentes/ui";
import { useSessao } from "../sessao";
import type { Registro } from "../tipos";

function Parametros() {
  const { pode } = useSessao();
  const [lista, erro, recarregar] = useRecurso(() => api.get<Registro[]>("/parametros"));
  const [falha, setFalha] = useState<string | null>(null);
  const [rascunho, setRascunho] = useState<Record<string, string>>({});
  if (!lista) return erro ? <Erro texto={erro} /> : <Carregando />;
  const admin = pode();

  async function salvar(chave: string, valor: string) {
    setFalha(null);
    try { await api.put(`/parametros/${chave}`, { valor }); setRascunho(({ [chave]: _, ...r }) => r); recarregar(); }
    catch (e) { setFalha((e as Error).message); }
  }

  return (
    <div>
      <Erro texto={falha} />
      {!admin && <p className="mb-2 text-sm text-slate-500">Só o admin altera parâmetros.</p>}
      <table className="tabela"><thead><tr><th>Parâmetro</th><th>Valor</th></tr></thead>
        <tbody>{lista.map((p) => {
          const chave = String(p.chave);
          const valor = String(p.valor);
          const booleano = valor === "true" || valor === "false";
          return (
            <tr key={chave}>
              <td><div className="font-mono text-xs">{chave}</div><div className="text-xs text-slate-500">{String(p.descricao)}</div></td>
              <td className="w-72">
                {booleano ? (
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={!admin} checked={valor === "true"} onChange={(e) => salvar(chave, String(e.target.checked))} />{valor === "true" ? "ligado" : "desligado"}</label>
                ) : (
                  <div className="flex gap-1">
                    <input className="campo" disabled={!admin} value={rascunho[chave] ?? valor} onChange={(e) => setRascunho({ ...rascunho, [chave]: e.target.value })} />
                    {rascunho[chave] !== undefined && <button className="botao-primario" onClick={() => salvar(chave, rascunho[chave])}>OK</button>}
                  </div>
                )}
              </td>
            </tr>
          );
        })}</tbody></table>
    </div>
  );
}

function Textos() {
  const [lista, erro, recarregar] = useRecurso(() => api.get<Registro[]>("/textos"));
  const [aberto, setAberto] = useState<string | null>(null);
  const [texto, setTexto] = useState("");
  const [previa, setPrevia] = useState("");
  const [falha, setFalha] = useState<string | null>(null);
  if (!lista) return erro ? <Erro texto={erro} /> : <Carregando />;

  function abrir(t: Registro) { setAberto(String(t.chave)); setTexto(String(t.texto)); setPrevia(""); setFalha(null); }
  async function verPrevia() { setPrevia((await api.post<{ texto: string }>("/textos/previa", { texto })).texto); }
  async function salvar() {
    setFalha(null);
    try { await api.put(`/textos/${aberto}`, { valor: texto }); setAberto(null); recarregar(); } catch (e) { setFalha((e as Error).message); }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-slate-600">O que o bot fala. Use as variáveis entre chaves, como <code>{"{paciente}"}</code>. Nunca coloque resultado de exame ou detalhe clínico.</p>
      {lista.map((t) => (
        <div key={String(t.chave)} className="rounded-md border border-slate-200 p-2">
          <div className="flex items-center justify-between gap-2">
            <div><span className="font-mono text-xs">{String(t.chave)}</span> <span className="text-xs text-slate-400">{String(t.descricao)}</span></div>
            {aberto !== t.chave && <button className="botao-secundario" onClick={() => abrir(t)}>Editar</button>}
          </div>
          {aberto === t.chave ? (
            <div className="mt-2 space-y-2">
              <Erro texto={falha} />
              <textarea className="campo font-mono" rows={5} value={texto} onChange={(e) => setTexto(e.target.value)} />
              <div className="text-xs text-slate-500">Variáveis: {String(t.variaveis) || "nenhuma"} (sempre disponíveis: clinica, horario_atendimento, orientacoes)</div>
              {previa && <div className="whitespace-pre-wrap rounded bg-[#d9fdd3] p-2 text-sm">{previa}</div>}
              <div className="flex gap-2"><button className="botao-secundario" onClick={verPrevia}>Pré-visualizar</button><button className="botao-primario" onClick={salvar}>Salvar</button><button className="botao-secundario" onClick={() => setAberto(null)}>Cancelar</button></div>
            </div>
          ) : <div className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{String(t.texto)}</div>}
        </div>
      ))}
    </div>
  );
}

export default function Configuracoes() {
  const [aba, setAba] = useState("parametros");
  return (
    <>
      <Cabecalho titulo="Bot e parâmetros" sub="Comportamento do bot e do sistema. Tudo o que age sozinho nasce desligado." />
      <Abas abas={[["parametros", "Parâmetros"], ["textos", "Textos do bot"]]} ativa={aba} mudar={setAba} />
      <div className="cartao">{aba === "parametros" ? <Parametros /> : <Textos />}</div>
    </>
  );
}
