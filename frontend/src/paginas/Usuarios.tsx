import { useState } from "react";
import { api } from "../api";
import { Aviso, Cabecalho, Erro, Lista, Modal, useRecurso } from "../componentes/ui";
import { telefone } from "../formato";
import { PERFIL, useSessao } from "../sessao";
import type { Perfil, Usuario } from "../tipos";

const PERFIS: Perfil[] = ["ADMIN", "SUPERVISAO", "RECEPCAO"];
const EXPLICA: Record<Perfil, string> = {
  ADMIN: "Faz tudo, inclusive criar usuários e mudar as regras do sistema.",
  SUPERVISAO: "Tudo da recepção, mais a grade, as mensagens do bot e o que já está no sistema de gestão.",
  RECEPCAO: "Agenda, pedidos do bot, conversas, cadastros, folgas e feriados.",
};
const SENHA = "Ao menos 10 caracteres; não vale só números, senha muito comum nem o login dentro dela. A pessoa troca no primeiro acesso.";

interface Ficha { id?: number; nome: string; login: string; senha: string; perfil: Perfil; whatsapp: string; ativo: boolean }

export default function Usuarios() {
  const { usuario } = useSessao();
  const [lista, erro, recarregar] = useRecurso(() => api.get<Usuario[]>("/usuarios"));
  const [ficha, setFicha] = useState<Ficha | null>(null);
  const [falha, setFalha] = useState<string | null>(null);
  const [feito, setFeito] = useState<string | null>(null);
  const eu = ficha?.id === usuario?.id;

  async function salvar() {
    if (!ficha) return;
    setFalha(null);
    try {
      if (ficha.id) {
        await api.patch(`/usuarios/${ficha.id}`, { nome: ficha.nome, perfil: ficha.perfil, ativo: ficha.ativo, whatsapp: ficha.whatsapp || null, ...(ficha.senha ? { senha: ficha.senha } : {}) });
        setFeito(ficha.senha ? `Senha de ${ficha.nome} redefinida: ela troca no próximo acesso.` : "Usuário alterado.");
      } else {
        await api.post("/usuarios", { nome: ficha.nome, login: ficha.login, senha: ficha.senha, perfil: ficha.perfil, whatsapp: ficha.whatsapp || null });
        setFeito(`Usuário ${ficha.login} criado. Passe a senha provisória: a pessoa cria a dela no primeiro acesso.`);
      }
      setFicha(null);
      recarregar();
    } catch (e) { setFalha((e as Error).message); }
  }

  return (
    <>
      <Cabecalho titulo="Usuários" sub="Quem entra no painel e o que cada um pode fazer.">
        <button className="botao-primario" onClick={() => { setFalha(null); setFicha({ nome: "", login: "", senha: "", perfil: "RECEPCAO", whatsapp: "", ativo: true }); }}>+ Novo usuário</button>
      </Cabecalho>
      <Aviso texto={feito} />
      <div className="cartao">
        <Lista dados={lista} erro={erro} vazio="Nenhum usuário.">{(itens) => (
          <div className="overflow-x-auto">
            <table className="tabela tabela-cartao"><thead><tr><th>Nome</th><th>Login</th><th>Perfil</th><th>WhatsApp</th><th>Situação</th><th></th></tr></thead>
              <tbody>{itens.map((u) => (
                <tr key={u.id}>
                  <td>{u.nome}</td><td className="font-mono text-xs">{u.login}</td><td>{PERFIL[u.perfil] ?? u.perfil}</td>
                  <td className="whitespace-nowrap">{u.whatsapp ? telefone(u.whatsapp) : "—"}</td>
                  <td>{u.ativo ? "Ativo" : "Desativado"}{u.trocar_senha && <div className="text-xs text-amber-700">ainda não criou a própria senha</div>}</td>
                  <td className="text-right"><button className="botao-secundario" onClick={() => { setFalha(null); setFicha({ id: u.id, nome: u.nome, login: u.login, senha: "", perfil: u.perfil, whatsapp: u.whatsapp ?? "", ativo: u.ativo }); }}>Alterar</button></td>
                </tr>
              ))}</tbody></table>
          </div>
        )}</Lista>
      </div>
      <Modal titulo={ficha?.id ? `Alterar ${ficha.nome}` : "Novo usuário"} aberto={!!ficha} fechar={() => setFicha(null)}>
        {ficha && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); salvar(); }}>
            <Erro texto={falha} />
            <div><label className="rotulo" htmlFor="u-nome">Nome *</label><input id="u-nome" className="campo" value={ficha.nome} onChange={(e) => setFicha({ ...ficha, nome: e.target.value })} autoFocus /></div>
            {!ficha.id && <div><label className="rotulo" htmlFor="u-login">Login * (letras minúsculas, números, ponto ou traço)</label><input id="u-login" className="campo" value={ficha.login} onChange={(e) => setFicha({ ...ficha, login: e.target.value.toLowerCase().trim() })} autoCapitalize="none" /></div>}
            <div>
              <label className="rotulo" htmlFor="u-perfil">Perfil *</label>
              <select id="u-perfil" className="campo" value={ficha.perfil} onChange={(e) => setFicha({ ...ficha, perfil: e.target.value as Perfil })} aria-describedby="u-perfil-ajuda">{PERFIS.map((p) => <option key={p} value={p}>{PERFIL[p]}</option>)}</select>
              <p id="u-perfil-ajuda" className="mt-1 text-xs text-slate-500">{EXPLICA[ficha.perfil]}</p>
            </div>
            <div>
              <label className="rotulo" htmlFor="u-zap">WhatsApp (opcional)</label>
              <input id="u-zap" className="campo" value={ficha.whatsapp} onChange={(e) => setFicha({ ...ficha, whatsapp: e.target.value })} placeholder="DDD + número" inputMode="tel" aria-describedby="u-zap-ajuda" />
              <p id="u-zap-ajuda" className="mt-1 text-xs text-slate-500">Com o número cadastrado, a pessoa manda comandos ao bot: “agenda”, “das 14h compareceu”, “das 14h faltou”. Nada muda sem ela confirmar com SIM.</p>
            </div>
            {!eu && (
              <div>
                <label className="rotulo" htmlFor="u-senha">{ficha.id ? "Nova senha provisória (deixe em branco para não mudar)" : "Senha provisória *"}</label>
                <input id="u-senha" type="password" className="campo" value={ficha.senha} onChange={(e) => setFicha({ ...ficha, senha: e.target.value })} autoComplete="new-password" aria-describedby="u-senha-ajuda" />
                <p id="u-senha-ajuda" className="mt-1 text-xs text-slate-500">{SENHA}</p>
              </div>
            )}
            {eu && <p className="text-xs text-slate-500">Para trocar a sua própria senha, use “Trocar senha” no menu da conta, no alto da tela.</p>}
            {ficha.id && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ficha.ativo} onChange={(e) => setFicha({ ...ficha, ativo: e.target.checked })} />Ativo (desmarcado, a pessoa não entra mais)</label>}
            <div className="flex justify-end gap-2">
              <button type="button" className="botao-secundario" onClick={() => setFicha(null)}>Cancelar</button>
              <button className="botao-primario" disabled={ficha.nome.trim().length < 2 || (!ficha.id && (ficha.login.length < 3 || ficha.senha.length < 10))}>{ficha.id ? "Salvar" : "Criar usuário"}</button>
            </div>
          </form>
        )}
      </Modal>
    </>
  );
}
