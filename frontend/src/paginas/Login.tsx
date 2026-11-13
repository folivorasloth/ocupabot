import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { useSessao } from "../sessao";
import { Erro } from "../componentes/ui";

export default function Login() {
  const { entrar, saiu } = useSessao();
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [ambiente, setAmbiente] = useState<{ clinica: string; teste: boolean } | null>(null);
  useEffect(() => { api.get<{ clinica: string; teste: boolean }>("/ambiente").then(setAmbiente).catch(() => setAmbiente(null)); }, []);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try { await entrar(login.trim().toLowerCase(), senha); } catch (err) { setErro((err as Error).message); } finally { setEnviando(false); }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={enviar} className="cartao w-full max-w-sm space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-marca-700">OcupaBot</h1>
          <p className="text-sm text-slate-500">Painel da recepção{ambiente ? ` · ${ambiente.clinica}` : ""}</p>
        </div>
        {ambiente?.teste && <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">Ambiente de teste: o bot só conversa com os números de teste.</p>}
        {saiu && !erro && <p className="rounded-md bg-marca-50 px-3 py-2 text-sm text-marca-700">Você saiu.</p>}
        <Erro texto={erro} />
        <div><label className="rotulo" htmlFor="login">Login *</label><input id="login" className="campo" value={login} onChange={(e) => setLogin(e.target.value)} autoFocus autoComplete="username" autoCapitalize="none" /></div>
        <div><label className="rotulo" htmlFor="senha">Senha *</label><input id="senha" type="password" className="campo" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" /></div>
        <button className="botao-primario w-full justify-center" disabled={enviando || !login || !senha}>{enviando ? "Entrando…" : "Entrar"}</button>
      </form>
    </div>
  );
}
