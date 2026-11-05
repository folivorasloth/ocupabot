import { FormEvent, useState } from "react";
import { useSessao } from "../sessao";
import { Erro } from "../componentes/ui";

export default function Login() {
  const { entrar } = useSessao();
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    try { await entrar(login.trim().toLowerCase(), senha); } catch (err) { setErro((err as Error).message); } finally { setEnviando(false); }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={enviar} className="cartao w-full max-w-sm space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-marca-700">OcupaBot</h1>
          <p className="text-sm text-slate-500">Painel da recepção</p>
        </div>
        <Erro texto={erro} />
        <div><label className="rotulo" htmlFor="login">Login</label><input id="login" className="campo" value={login} onChange={(e) => setLogin(e.target.value)} autoFocus autoComplete="username" /></div>
        <div><label className="rotulo" htmlFor="senha">Senha</label><input id="senha" type="password" className="campo" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" /></div>
        <button className="botao-primario w-full justify-center" disabled={enviando || !login || !senha}>Entrar</button>
      </form>
    </div>
  );
}
