import { FormEvent, useState } from "react";
import { Erro } from "../componentes/ui";
import { useSessao } from "../sessao";

/** Troca da própria senha: obrigatória no primeiro acesso e disponível no menu da conta. */
export default function TrocarSenha({ feito }: { feito?: () => void }) {
  const { trocarSenha } = useSessao();
  const [f, setF] = useState({ atual: "", nova: "", repete: "" });
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const diferente = f.repete !== "" && f.nova !== f.repete;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try { await trocarSenha(f.atual, f.nova); feito?.(); } catch (err) { setErro((err as Error).message); } finally { setEnviando(false); }
  }

  return (
    <form onSubmit={enviar} className="space-y-3">
      <Erro texto={erro} />
      <div><label className="rotulo" htmlFor="atual">Senha atual *</label><input id="atual" type="password" className="campo" value={f.atual} onChange={(e) => setF({ ...f, atual: e.target.value })} autoComplete="current-password" autoFocus /></div>
      <div>
        <label className="rotulo" htmlFor="nova">Senha nova *</label>
        <input id="nova" type="password" className="campo" value={f.nova} onChange={(e) => setF({ ...f, nova: e.target.value })} autoComplete="new-password" aria-describedby="ajuda-senha" />
        <p id="ajuda-senha" className="mt-1 text-xs text-slate-500">Ao menos 10 caracteres. Não vale só números, senha muito comum nem o seu login dentro dela.</p>
      </div>
      <div><label className="rotulo" htmlFor="repete">Repita a senha nova *</label><input id="repete" type="password" className="campo" value={f.repete} onChange={(e) => setF({ ...f, repete: e.target.value })} autoComplete="new-password" />
        {diferente && <p className="mt-1 text-xs text-rose-600">As duas senhas novas estão diferentes.</p>}</div>
      <button className="botao-primario" disabled={enviando || !f.atual || f.nova.length < 10 || f.nova !== f.repete}>{enviando ? "Trocando…" : "Trocar senha"}</button>
    </form>
  );
}
