import { useState } from "react";
import { nomeEmpresa, useCatalogo } from "../componentes/catalogo";
import TabelaCadastro, { Campo } from "../componentes/TabelaCadastro";
import { Abas, Cabecalho, Carregando } from "../componentes/ui";
import { EQUIPE, useSessao } from "../sessao";

export default function Cadastros() {
  const { pode } = useSessao();
  const [aba, setAba] = useState("empresas");
  const [cat] = useCatalogo();
  if (!cat) return <Carregando />;
  const empresas = cat.empresas.map((e) => ({ valor: e.id!, rotulo: nomeEmpresa(e) }));
  const funcoes = cat.funcoes.map((f) => ({ valor: f.id!, rotulo: String(f.nome) }));
  const tipoContato = ["RH", "PARTICULAR", "PACIENTE", "DESCONHECIDO"].map((t) => ({ valor: t, rotulo: t }));

  const config: Record<string, { campos: Campo[]; editar: boolean; busca?: boolean }> = {
    empresas: { editar: pode(...EQUIPE), busca: true, campos: [
      { chave: "razao_social", rotulo: "Razão social" }, { chave: "nome_fantasia", rotulo: "Nome fantasia" },
      { chave: "cnpj", rotulo: "CNPJ" }, { chave: "rh_nome", rotulo: "RH", naLista: false }, { chave: "rh_telefone", rotulo: "Telefone do RH", naLista: false },
      { chave: "usa_sistema_externo", rotulo: "Usa o sistema externo", tipo: "bool" }, { chave: "codigo_externo", rotulo: "Código externo", naLista: false },
      { chave: "ativa", rotulo: "Ativa", tipo: "bool" }] },
    pacientes: { editar: pode(...EQUIPE), busca: true, campos: [
      { chave: "nome", rotulo: "Nome" }, { chave: "cpf", rotulo: "CPF" }, { chave: "nascimento", rotulo: "Nascimento", tipo: "data" },
      { chave: "empresa_id", rotulo: "Empresa", tipo: "opcoes", opcoes: empresas }, { chave: "setor", rotulo: "Setor", naLista: false },
      { chave: "cargo", rotulo: "Cargo" }, { chave: "rg", rotulo: "RG", naLista: false }] },
    contatos: { editar: pode(...EQUIPE), busca: true, campos: [
      { chave: "telefone", rotulo: "Telefone" }, { chave: "nome", rotulo: "Nome" }, { chave: "tipo", rotulo: "Tipo", tipo: "opcoes", opcoes: tipoContato },
      { chave: "empresa_id", rotulo: "Empresa", tipo: "opcoes", opcoes: empresas }] },
    profissionais: { editar: pode("SUPERVISAO"), campos: [{ chave: "nome", rotulo: "Nome" }, { chave: "ativo", rotulo: "Ativo", tipo: "bool" }] },
    exames: { editar: pode(), campos: [
      { chave: "codigo", rotulo: "Código" }, { chave: "nome", rotulo: "Nome" }, { chave: "funcao_id", rotulo: "Função que executa", tipo: "opcoes", opcoes: funcoes },
      { chave: "ordem", rotulo: "Ordem no menu", tipo: "numero" }, { chave: "ativo", rotulo: "Ativo", tipo: "bool" }] },
    funcoes: { editar: pode(), campos: [
      { chave: "codigo", rotulo: "Código" }, { chave: "nome", rotulo: "Nome" }, { chave: "capacidade_por_hora", rotulo: "Pacientes/hora por profissional", tipo: "numero" },
      { chave: "requer_humano", rotulo: "Agenda própria (vai para a equipe)", tipo: "bool" }, { chave: "ativa", rotulo: "Ativa", tipo: "bool" }] },
    "tipos-aso": { editar: pode(), campos: [
      { chave: "codigo", rotulo: "Código" }, { chave: "nome", rotulo: "Nome" }, { chave: "ordem", rotulo: "Ordem", tipo: "numero" },
      { chave: "exige_cadastro_completo", rotulo: "Pede RG, setor e cargo", tipo: "bool" }] },
  };
  const atual = config[aba];
  return (
    <>
      <Cabecalho titulo="Cadastros" />
      <Abas ativa={aba} mudar={setAba} abas={[["empresas", "Empresas"], ["pacientes", "Pacientes"], ["contatos", "Contatos"], ["profissionais", "Profissionais"], ["exames", "Exames"], ["funcoes", "Funções"], ["tipos-aso", "Tipos de ASO"]]} />
      <div className="cartao"><TabelaCadastro key={aba} recurso={aba} campos={atual.campos} podeEditar={atual.editar} busca={atual.busca} /></div>
    </>
  );
}
