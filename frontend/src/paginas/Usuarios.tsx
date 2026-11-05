import { useState } from "react";
import { api } from "../api";
import { Cabecalho, Carregando, Erro, Modal, useRecurso } from "../componentes/ui";
import type { Perfil, Usuario } from "../tipos";

const PERFIS: Perfil[] = ["ADMIN", "SUPERVISAO", "RECEPCAO", "LEITURA"];

export default function Usuarios() {
  const [lista, erro, recarregar] = useRecurso(() => api.get<Usuario[]>("/usuarios"));
  const [novo, setNovo] = useState<{ nome: string; login: string; senha: string; perfil: Perfil } | null>(null);
  const [falha, setFalha] = useState<string | null>(null);

  async function enviar(fn: () => Promise<unknown>) {
    setFalha(null);
    try { await fn(); setNovo(null); recarregar(); } catch (e) { setFalha((e as Error).message); }
  }

  return (
    <>
      <Cabecalho titulo="Usuários"><button className="botao-primario" onClick={() => setNovo({ nome: "", login: "", senha: "", perfil: "RECEPCAO" })}>+ Novo usuário</button></Cabecalho>
      <Erro texto={erro || (novo ? null : falha)} />
      <div className="cartao">{!lista ? <Carregando /> : (
        <table className="tabela"><thead><tr><th>Nome</th><th>Login</th><th>Perfil</th><th>Ativo</th><th></th></tr></thead>
          <tbody>{lista.map((u) => (
            <tr key={u.id}>
              <td>{u.nome}</td><td className="font-mono text-xs">{u.login}</td>
              <td><select className="campo w-36" value={u.perfil} onChange={(e) => enviar(() => api.patch(`/usuarios/${u.id}`, { perfil: e.target.value }))}>{PERFIS.map((p) => <option key={p}>{p}</option>)}</select></td>
              <td><input type="checkbox" checked={u.ativo} onChange={(e) => enviar(() => api.patch(`/usuarios/${u.id}`, { ativo: e.target.checked }))} /></td>
              <td><button className="botao-secundario" onClick={() => { const senha = window.prompt("Nova senha (mín. 8)"); if (senha) enviar(() => api.patch(`/usuarios/${u.id}`, { senha })); }}>Trocar senha</button></td>
            </tr>
          ))}</tbody></table>
      )}</div>
      <Modal titulo="Novo usuário" aberto={!!novo} fechar={() => setNovo(null)}>
        {novo && (
          <div className="space-y-3">
            <Erro texto={falha} />
            <div><label className="rotulo">Nome</label><input className="campo" value={novo.nome} onChange={(e) => setNovo({ ...novo, nome: e.target.value })} /></div>
            <div><label className="rotulo">Login (minúsculas)</label><input className="campo" value={novo.login} onChange={(e) => setNovo({ ...novo, login: e.target.value.toLowerCase() })} /></div>
            <div><label className="rotulo">Senha (mín. 8)</label><input type="password" className="campo" value={novo.senha} onChange={(e) => setNovo({ ...novo, senha: e.target.value })} /></div>
            <div><label className="rotulo">Perfil</label><select className="campo" value={novo.perfil} onChange={(e) => setNovo({ ...novo, perfil: e.target.value as Perfil })}>{PERFIS.map((p) => <option key={p}>{p}</option>)}</select></div>
            <button className="botao-primario" onClick={() => enviar(() => api.post("/usuarios", novo))}>Criar</button>
          </div>
        )}
      </Modal>
    </>
  );
}
