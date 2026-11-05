import { useState } from "react";
import { HashRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useSessao } from "./sessao";
import type { Perfil } from "./tipos";
import Login from "./paginas/Login";
import Hoje from "./paginas/Hoje";
import AgendaPagina from "./paginas/Agenda";
import Aprovacoes from "./paginas/Aprovacoes";
import Conversas from "./paginas/Conversas";
import Simulador from "./paginas/Simulador";
import Cadastros from "./paginas/Cadastros";
import GradePagina from "./paginas/Grade";
import Configuracoes from "./paginas/Configuracoes";
import Usuarios from "./paginas/Usuarios";
import AuditoriaPagina from "./paginas/Auditoria";

const MENU: { para: string; rotulo: string; perfis?: Perfil[] }[] = [
  { para: "/", rotulo: "Hoje" },
  { para: "/agenda", rotulo: "Agenda" },
  { para: "/aprovacoes", rotulo: "Aprovações" },
  { para: "/conversas", rotulo: "Conversas" },
  { para: "/simulador", rotulo: "Simulador do bot", perfis: ["SUPERVISAO", "RECEPCAO"] },
  { para: "/cadastros", rotulo: "Cadastros" },
  { para: "/grade", rotulo: "Grade e exceções" },
  { para: "/configuracoes", rotulo: "Bot e parâmetros", perfis: ["SUPERVISAO"] },
  { para: "/usuarios", rotulo: "Usuários", perfis: [] },
  { para: "/auditoria", rotulo: "Auditoria", perfis: ["SUPERVISAO"] },
];

export default function App() {
  const { usuario, carregando, sair, pode } = useSessao();
  const [menuAberto, setMenuAberto] = useState(false);
  if (carregando) return null;
  if (!usuario) return <Login />;
  const itens = MENU.filter((m) => !m.perfis || pode(...m.perfis));
  return (
    <HashRouter>
      <div className="min-h-screen md:flex">
        <aside className={`${menuAberto ? "block" : "hidden"} border-r border-slate-200 bg-white md:block md:w-56 md:shrink-0`}>
          <div className="hidden px-4 py-5 md:block">
            <span className="text-lg font-bold text-marca-700">OcupaBot</span>
          </div>
          <nav className="flex flex-col gap-0.5 px-2 pb-4">
            {itens.map((m) => (
              <NavLink key={m.para} to={m.para} end={m.para === "/"} onClick={() => setMenuAberto(false)}
                className={({ isActive }) => `rounded-md px-3 py-2 text-sm ${isActive ? "bg-marca-50 font-medium text-marca-700" : "text-slate-600 hover:bg-slate-100"}`}>
                {m.rotulo}
              </NavLink>
            ))}
          </nav>
        </aside>
        <div className="min-w-0 flex-1">
          <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2.5">
            <button className="botao-secundario md:hidden" onClick={() => setMenuAberto(!menuAberto)}>☰ Menu</button>
            <span className="text-sm font-bold text-marca-700 md:hidden">OcupaBot</span>
            <div className="ml-auto flex items-center gap-3 text-sm text-slate-600">
              <span className="hidden sm:inline">{usuario.nome} · <span className="text-slate-400">{usuario.perfil}</span></span>
              <button className="botao-secundario" onClick={sair}>Sair</button>
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
      </div>
    </HashRouter>
  );
}
