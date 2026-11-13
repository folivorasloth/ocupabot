import { useEffect, useState } from "react";
import { HashRouter, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { Modal, useRecurso } from "./componentes/ui";
import { PERFIL, useSessao } from "./sessao";
import type { Contadores, Perfil } from "./tipos";
import Login from "./paginas/Login";
import Hoje from "./paginas/Hoje";
import AgendaPagina from "./paginas/Agenda";
import Aprovacoes from "./paginas/Aprovacoes";
import Conversas from "./paginas/Conversas";
import Simulador from "./paginas/Simulador";
import Cadastros from "./paginas/Cadastros";
import GradePagina from "./paginas/Grade";
import Configuracoes from "./paginas/Configuracoes";
import TrocarSenha from "./paginas/TrocarSenha";
import Usuarios from "./paginas/Usuarios";
import AuditoriaPagina from "./paginas/Auditoria";

interface Item { para: string; rotulo: string; curto?: string; perfis?: Perfil[]; conta?: keyof Contadores }

// Menu em seções, com os nomes que a recepção usa. `curto` é o rótulo do menu de baixo no celular.
const MENU: { secao: string; itens: Item[] }[] = [
  { secao: "Dia a dia", itens: [
    { para: "/", rotulo: "Hoje", curto: "Hoje" },
    { para: "/agenda", rotulo: "Agenda", curto: "Agenda" },
    { para: "/aprovacoes", rotulo: "Pedidos do bot", curto: "Pedidos", conta: "aprovacoes_pendentes" },
    { para: "/conversas", rotulo: "Conversas", curto: "Conversas", conta: "conversas_esperando" },
  ] },
  { secao: "Cadastros", itens: [
    { para: "/cadastros", rotulo: "Empresas e pacientes" },
    { para: "/grade", rotulo: "Grade, folgas e feriados" },
  ] },
  { secao: "Configuração", itens: [
    { para: "/simulador", rotulo: "Testar o bot", perfis: ["SUPERVISAO", "RECEPCAO"] },
    { para: "/configuracoes", rotulo: "Mensagens do bot e regras", perfis: ["SUPERVISAO"] },
    { para: "/usuarios", rotulo: "Usuários", perfis: [] },
    { para: "/auditoria", rotulo: "Auditoria", perfis: ["SUPERVISAO"] },
  ] },
];

function Selo({ n }: { n: number }) {
  if (!n) return null;
  return <span className="ml-auto rounded-full bg-rose-700 px-1.5 text-xs font-semibold text-white" aria-label={`${n} esperando`}>{n}</span>;
}

function Painel() {
  const { usuario, sair, pode } = useSessao();
  const [mais, setMais] = useState(false);
  const [conta, setConta] = useState(false);
  const [senha, setSenha] = useState(false);
  const local = useLocation();
  const [contadores, , recontar] = useRecurso(() => api.get<Contadores>("/painel/contadores"), [], 30000);
  // o selo do menu atualiza logo depois de aprovar, recusar ou assumir (as telas avisam com este evento)
  useEffect(() => {
    window.addEventListener("contadores", recontar);
    return () => window.removeEventListener("contadores", recontar);
  }, [recontar]);
  useEffect(() => { setMais(false); setConta(false); }, [local.pathname]);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { setMais(false); setConta(false); } };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);
  if (!usuario) return null;
  const secoes = MENU.map((s) => ({ ...s, itens: s.itens.filter((m) => !m.perfis || pode(...m.perfis)) })).filter((s) => s.itens.length);
  const embaixo = secoes.flatMap((s) => s.itens).filter((m) => m.curto);
  const link = (m: Item) => (
    <NavLink key={m.para} to={m.para} end={m.para === "/"}
      className={({ isActive }) => `flex min-h-[40px] items-center gap-2 rounded-md px-3 py-2 text-sm ${isActive ? "bg-marca-50 font-medium text-marca-700" : "text-slate-600 hover:bg-slate-100"}`}>
      {m.rotulo}<Selo n={m.conta && contadores ? contadores[m.conta] : 0} />
    </NavLink>
  );
  const menu = secoes.map((s) => (
    <div key={s.secao} className="mb-3">
      <div className="px-3 pb-1 text-[11px] font-semibold uppercase text-slate-400">{s.secao}</div>
      {s.itens.map(link)}
    </div>
  ));

  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden border-r border-slate-200 bg-white md:block md:w-60 md:shrink-0">
        <div className="px-4 py-5"><span className="text-lg font-bold text-marca-700">OcupaBot</span></div>
        <nav className="px-2 pb-4" aria-label="Menu principal">{menu}</nav>
      </aside>
      <div className="min-w-0 flex-1 pb-16 md:pb-0">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2.5">
          <span className="text-sm font-bold text-marca-700 md:hidden">OcupaBot</span>
          <div className="relative ml-auto">
            <button className="botao-secundario" aria-haspopup="menu" aria-expanded={conta} onClick={() => setConta(!conta)}>
              {usuario.nome} <span className="hidden text-slate-400 sm:inline">· {PERFIL[usuario.perfil]}</span> ▾
            </button>
            {conta && (
              <div role="menu" className="absolute right-0 z-30 mt-1 w-48 rounded-md border border-slate-200 bg-white py-1 shadow-lg">
                <div className="border-b border-slate-100 px-3 py-2 text-xs text-slate-500">{usuario.login} · {PERFIL[usuario.perfil]}</div>
                <button role="menuitem" className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => { setConta(false); setSenha(true); }}>Trocar senha</button>
                <button role="menuitem" className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={sair}>Sair</button>
              </div>
            )}
          </div>
        </header>
        <main className="mx-auto max-w-6xl p-4 md:p-6">
          <Routes>
            <Route path="/" element={<Hoje />} />
            <Route path="/agenda" element={<AgendaPagina />} />
            <Route path="/aprovacoes" element={<Aprovacoes />} />
            <Route path="/conversas" element={<Conversas />} />
            <Route path="/simulador" element={<Simulador />} />
            <Route path="/cadastros" element={<Cadastros />} />
            <Route path="/grade" element={<GradePagina />} />
            <Route path="/configuracoes" element={<Configuracoes />} />
            <Route path="/usuarios" element={<Usuarios />} />
            <Route path="/auditoria" element={<AuditoriaPagina />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
      {/* celular: menu de baixo com o dia a dia e "Mais" para o resto */}
      {mais && (
        <div className="fixed inset-0 z-30 bg-slate-900/40 md:hidden" onClick={() => setMais(false)}>
          <nav className="absolute inset-x-0 bottom-14 max-h-[70vh] overflow-y-auto rounded-t-xl bg-white p-3 shadow-xl" aria-label="Mais opções" onClick={(e) => e.stopPropagation()}>
            {menu.slice(1)}
            <button className="botao-secundario w-full justify-center" onClick={() => setMais(false)}>Fechar</button>
          </nav>
        </div>
      )}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] md:hidden" aria-label="Menu do celular">
        {embaixo.map((m) => (
          <NavLink key={m.para} to={m.para} end={m.para === "/"}
            className={({ isActive }) => `relative flex h-14 flex-col items-center justify-center text-xs ${isActive ? "font-semibold text-marca-700" : "text-slate-500"}`}>
            {m.curto}
            {!!(m.conta && contadores?.[m.conta]) && <span className="absolute right-3 top-1.5 rounded-full bg-rose-700 px-1.5 text-[10px] font-semibold text-white">{contadores![m.conta!]}</span>}
          </NavLink>
        ))}
        <button className={`h-14 text-xs ${mais ? "font-semibold text-marca-700" : "text-slate-500"}`} aria-expanded={mais} onClick={() => setMais(!mais)}>Mais</button>
      </nav>
      <Modal titulo="Trocar senha" aberto={senha} fechar={() => setSenha(false)}><TrocarSenha feito={() => setSenha(false)} /></Modal>
    </div>
  );
}

export default function App() {
  const { usuario, carregando, sair } = useSessao();
  if (carregando) return null;
  if (!usuario) return <Login />;
  if (usuario.trocar_senha) {
    // senha dada por outra pessoa (criada ou redefinida pelo admin): troca antes de qualquer coisa
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="cartao w-full max-w-sm space-y-3">
          <h1 className="text-xl font-bold text-marca-700">Crie a sua senha</h1>
          <p className="text-sm text-slate-600">Olá, {usuario.nome}. A senha que você recebeu é provisória: troque por uma que só você saiba para entrar no painel.</p>
          <TrocarSenha />
          <button className="text-sm text-slate-500 underline" onClick={sair}>Sair</button>
        </div>
      </div>
    );
  }
  return <HashRouter><Painel /></HashRouter>;
}
