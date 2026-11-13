import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { Perfil, Usuario } from "./tipos";

interface Sessao {
  usuario: Usuario | null;
  carregando: boolean;
  /** "Você saiu" na tela de login depois de sair. */
  saiu: boolean;
  entrar: (login: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
  trocarSenha: (atual: string, nova: string) => Promise<void>;
  pode: (...perfis: Perfil[]) => boolean;
}

const Ctx = createContext<Sessao | null>(null);

export function ProvedorSessao({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [saiu, setSaiu] = useState(false);

  useEffect(() => {
    api.get<Usuario>("/auth/eu").then(setUsuario).catch(() => setUsuario(null)).finally(() => setCarregando(false));
    const expirou = () => setUsuario(null);
    window.addEventListener("sessao-expirada", expirou);
    return () => window.removeEventListener("sessao-expirada", expirou);
  }, []);

  const entrar = useCallback(async (login: string, senha: string) => {
    setUsuario(await api.post<Usuario>("/auth/login", { login, senha }));
    setSaiu(false);
  }, []);
  const sair = useCallback(async () => {
    await api.post("/auth/sair");
    setUsuario(null);
    setSaiu(true);
  }, []);
  const trocarSenha = useCallback(async (atual: string, nova: string) => {
    setUsuario(await api.post<Usuario>("/auth/senha", { atual, nova }));
  }, []);
  const pode = useCallback((...perfis: Perfil[]) => !!usuario && (usuario.perfil === "ADMIN" || perfis.includes(usuario.perfil)), [usuario]);

  return <Ctx.Provider value={{ usuario, carregando, saiu, entrar, sair, trocarSenha, pode }}>{children}</Ctx.Provider>;
}

export function useSessao(): Sessao {
  const s = useContext(Ctx);
  if (!s) throw new Error("fora do ProvedorSessao");
  return s;
}

export const EQUIPE: Perfil[] = ["SUPERVISAO", "RECEPCAO"];
export const PERFIL: Record<Perfil, string> = { ADMIN: "Administração", SUPERVISAO: "Supervisão", RECEPCAO: "Recepção" };
