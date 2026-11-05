import { api } from "../api";
import type { Registro } from "../tipos";
import { useRecurso } from "./ui";

export interface Catalogo {
  exames: Registro[]; empresas: Registro[]; tipos: Registro[]; profissionais: Registro[]; funcoes: Registro[];
}

export function useCatalogo() {
  return useRecurso<Catalogo>(async () => {
    const [exames, empresas, tipos, profissionais, funcoes] = await Promise.all([
      api.get<Registro[]>("/exames"), api.get<Registro[]>("/empresas"), api.get<Registro[]>("/tipos-aso"),
      api.get<Registro[]>("/profissionais"), api.get<Registro[]>("/funcoes"),
    ]);
    return { exames: exames.filter((e) => e.ativo), empresas, tipos, profissionais, funcoes };
  });
}

export const nomeEmpresa = (e: Registro) => String(e.nome_fantasia || e.razao_social);
