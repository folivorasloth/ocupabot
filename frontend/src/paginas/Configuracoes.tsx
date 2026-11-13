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
      {!admin && <p className="mb-2 text-sm text-slate-500">Só a administração altera estas regras.</p>}
      <table className="tabela tabela-cartao"><thead><tr><th>Regra</th><th>Valor</th></tr></thead>
        <tbody>{lista.map((p) => {
          const chave = String(p.chave);
          const valor = String(p.valor);
          const booleano = valor === "true" || valor === "false";
          return (
            <tr key={chave}>
              <td><div className="text-sm">{String(p.descricao) || chave}</div>{admin && <div className="font-mono text-[11px] text-slate-400">{chave}</div>}</td>
              <td className="w-72">
                {booleano ? (
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={!admin} checked={valor === "true"} onChange={(e) => salvar(chave, String(e.target.checked))} />{valor === "true" ? "ligado" : "desligado"}</label>
                ) : (
                  <div className="flex gap-1">
                    <input className="campo" aria-label={chave} disabled={!admin} value={rascunho[chave] ?? valor} onChange={(e) => setRascunho({ ...rascunho, [chave]: e.target.value })}
                      onKeyDown={(e) => { if (e.key === "Enter" && rascunho[chave] !== undefined) salvar(chave, rascunho[chave]); }} />
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
  const [busca, setBusca] = useState("");
  if (!lista) return erro ? <Erro texto={erro} /> : <Carregando />;
  const termo = busca.trim().toLowerCase();
  const achados = lista.filter((t) => !termo || [t.chave, t.descricao, t.texto].some((x) => String(x ?? "").toLowerCase().includes(termo)));

  function abrir(t: Registro) { setAberto(String(t.chave)); setTexto(String(t.texto)); setPrevia(""); setFalha(null); }
  async function verPrevia() {
    setFalha(null);
    try { setPrevia((await api.post<{ texto: string }>("/textos/previa", { texto })).texto); } catch (e) { setFalha((e as Error).message); }
  }
  async function salvar() {
    setFalha(null);
    try { await api.put(`/textos/${aberto}`, { valor: texto }); setAberto(null); recarregar(); } catch (e) { setFalha((e as Error).message); }
  }
  async function voltar(original: boolean) {
    setFalha(null);
    try {
      const r = await api.post<Registro>(`/textos/${aberto}/voltar${original ? "?original=true" : ""}`);
      setTexto(String(r.texto));
      setPrevia("");
      recarregar();
    } catch (e) { setFalha((e as Error).message); }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-slate-600">O que o bot fala. Use as variáveis entre chaves, como <code>{"{paciente}"}</code>. Nunca coloque resultado de exame ou detalhe clínico.</p>
      <input className="campo max-w-sm" placeholder="Buscar pelo nome ou por um trecho da mensagem…" aria-label="Buscar mensagem" value={busca} onChange={(e) => setBusca(e.target.value)} />
      {achados.length === 0 && <p className="py-4 text-center text-sm text-slate-500">Nenhuma mensagem com “{busca}”.</p>}
      {achados.map((t) => (
        <div key={String(t.chave)} className="rounded-md border border-slate-200 p-2">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0"><span className="text-sm font-medium">{String(t.descricao) || String(t.chave)}</span> <span className="font-mono text-[11px] text-slate-400">{String(t.chave)}</span></div>
            {aberto !== t.chave && <button className="botao-secundario" onClick={() => abrir(t)}>Editar</button>}
          </div>
          {aberto === t.chave ? (
            <div className="mt-2 space-y-2">
              <Erro texto={falha} />
              <textarea className="campo font-mono" rows={5} value={texto} onChange={(e) => setTexto(e.target.value)} />
              <div className="text-xs text-slate-500">Variáveis: {String(t.variaveis) || "nenhuma"} (sempre disponíveis: clinica, horario_atendimento, orientacoes)</div>
              {previa && <div className="whitespace-pre-wrap rounded bg-[#d9fdd3] p-2 text-sm">{previa}</div>}
              <div className="flex flex-wrap gap-2">
                <button className="botao-secundario" onClick={verPrevia}>Pré-visualizar</button><button className="botao-primario" onClick={salvar}>Salvar</button>
                <button className="botao-secundario" onClick={() => setAberto(null)}>Fechar</button>
                <button className="botao-secundario" title="Desfaz a última alteração salva" onClick={() => voltar(false)}>Voltar à versão anterior</button>
                <button className="botao-secundario" title="O texto que veio com o sistema" onClick={() => voltar(true)}>Voltar ao texto original</button>
              </div>
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
      <Cabecalho titulo="Mensagens do bot e regras" sub="Comportamento do bot e do sistema. Tudo o que age sozinho nasce desligado." />
      <Abas abas={[["parametros", "Regras"], ["textos", "Mensagens do bot"]]} ativa={aba} mudar={setAba} />
      <div className="cartao">{aba === "parametros" ? <Parametros /> : <Textos />}</div>
    </>
  );
}
