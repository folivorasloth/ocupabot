import { useState } from "react";
import { api } from "../api";
import { nomeEmpresa, useCatalogo } from "../componentes/catalogo";
import TabelaCadastro, { Campo } from "../componentes/TabelaCadastro";
import { Abas, Cabecalho, Carregando, Erro, Lista, useRecurso } from "../componentes/ui";
import { cnpj, hojeIso, plural, somarDias, telefone, TIPO_CONTATO } from "../formato";
import { EQUIPE, useSessao } from "../sessao";
import type { QuemAgenda, Registro } from "../tipos";

const tipoContato = Object.entries(TIPO_CONTATO).map(([valor, rotulo]) => ({ valor, rotulo }));
const PCMSO = [{ valor: "CLINICA", rotulo: "A clínica elaborou" }, { valor: "TERCEIRO", rotulo: "Outra empresa elaborou" }];

/** PCMSO a cobrar: vencido, vencendo em 30 dias ou, feito por outra empresa, documento que ainda não chegou. */
function pcmsoACobrar(e: Registro): boolean {
  if (!e.pcmso_elaborado_por || !e.ativa) return false;
  const vence = e.pcmso_vence_em ? String(e.pcmso_vence_em) : null;
  return (vence !== null && vence <= somarDias(hojeIso(), 30)) || (e.pcmso_elaborado_por === "TERCEIRO" && !e.pcmso_recebido);
}

/** Quem agenda pelas empresas: RH, credenciadora e contabilidade, cada um com as suas empresas. */
function QuemAgendaAba({ empresas, podeEditar }: { empresas: Registro[]; podeEditar: boolean }) {
  const [lista, erro, recarregar] = useRecurso(() => api.get<QuemAgenda[]>("/quem-agenda"));
  const [nova, setNova] = useState<Record<number, string>>({});
  const [falha, setFalha] = useState<string | null>(null);

  async function mudar(chamada: Promise<unknown>) {
    setFalha(null);
    try { await chamada; recarregar(); } catch (e) { setFalha((e as Error).message); }
  }

  return (
    <div>
      <p className="mb-3 text-sm text-slate-600">Quem agenda em nome das empresas pelo WhatsApp. Um escritório de contabilidade ou uma credenciadora pode agendar por várias: o bot pergunta para qual empresa é o exame. Para incluir um número novo, cadastre em Contatos com o tipo RH, Credenciadora ou Contabilidade.</p>
      <Erro texto={falha} />
      <Lista dados={lista} erro={erro} vazio="Ninguém cadastrado como RH, credenciadora ou contabilidade ainda.">{(itens) => (
        <>
          <p className="mb-2 text-xs text-slate-500">{plural(itens.length, "contato", "contatos")}</p>
          <div className="space-y-2">
            {itens.map((c) => (
              <div key={c.id} className="rounded-md border border-slate-200 p-3">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-medium">{c.nome || "(sem nome)"}</span>
                  <span className="whitespace-nowrap text-xs text-slate-500">{telefone(c.telefone)} · {TIPO_CONTATO[c.tipo] ?? c.tipo}</span>
                  {c.optout && <span className="whitespace-nowrap rounded bg-rose-100 px-1.5 text-xs text-rose-800">pediu SAIR</span>}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-1">
                  {c.empresas.length === 0 && <span className="text-xs text-amber-700">Sem empresa ligada: o bot pede o CNPJ a cada pedido.</span>}
                  {c.empresas.map((e, i) => (
                    <span key={e.id} className="inline-flex items-center gap-1 rounded bg-marca-50 px-2 py-1 text-xs text-marca-900">
                      {e.nome}{i === 0 && c.empresas.length > 1 ? " (principal)" : ""}
                      {podeEditar && <button className="px-1 text-slate-500 hover:text-rose-600" aria-label={`Tirar ${e.nome}`} title="Tirar esta empresa" onClick={() => mudar(api.del(`/contatos/${c.id}/empresas/${e.id}`))}>×</button>}
                    </span>
                  ))}
                </div>
                {podeEditar && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <select className="campo max-w-xs" aria-label="Empresa para ligar" value={nova[c.id] ?? ""} onChange={(e) => setNova({ ...nova, [c.id]: e.target.value })}>
                      <option value="">Ligar a outra empresa…</option>
                      {empresas.filter((e) => e.ativa && !c.empresas.some((x) => x.id === e.id)).map((e) => <option key={e.id} value={e.id}>{nomeEmpresa(e)}</option>)}
                    </select>
                    <button className="botao-secundario" disabled={!nova[c.id]} onClick={() => mudar(api.put(`/contatos/${c.id}/empresas/${nova[c.id]}`, {}).then(() => setNova({ ...nova, [c.id]: "" })))}>Ligar</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}</Lista>
    </div>
  );
}

export default function Cadastros() {
  const { pode } = useSessao();
  const [aba, setAba] = useState("empresas");
  const [cat, erro] = useCatalogo();
  if (!cat) return erro ? <Erro texto={erro} /> : <Carregando />;
  const empresas = cat.empresas.map((e) => ({ valor: e.id!, rotulo: nomeEmpresa(e) }));
  const funcoes = cat.funcoes.map((f) => ({ valor: f.id!, rotulo: String(f.nome) }));
  const fone = (v: unknown) => telefone(String(v));

  const config: Record<string, { campos: Campo[]; editar: boolean; busca?: boolean; nome: [string, string]; filtro?: { rotulo: string; teste: (r: Registro) => boolean } }> = {
    empresas: { editar: pode(...EQUIPE), busca: true, nome: ["empresa", "empresas"], filtro: { rotulo: "Só PCMSO a cobrar", teste: pcmsoACobrar }, campos: [
      { chave: "razao_social", rotulo: "Razão social", obrigatorio: true }, { chave: "nome_fantasia", rotulo: "Nome fantasia" },
      { chave: "cnpj", rotulo: "CNPJ", formato: cnpj }, { chave: "rh_nome", rotulo: "Nome do RH", naLista: false },
      { chave: "rh_telefone", rotulo: "Telefone do RH", naLista: false, ajuda: "Com DDD. Só para consulta: quem agenda pelo WhatsApp fica em “Quem agenda”." },
      { chave: "usa_sistema_externo", rotulo: "Lançada também no sistema de gestão da clínica", tipo: "bool", naLista: false },
      { chave: "codigo_externo", rotulo: "Código no sistema de gestão", naLista: false },
      { chave: "pcmso_elaborado_por", rotulo: "PCMSO", tipo: "opcoes", opcoes: PCMSO, ajuda: "Deixe em branco se a clínica não acompanha o PCMSO desta empresa." },
      { chave: "pcmso_vence_em", rotulo: "PCMSO vale até", tipo: "data", ajuda: "A tela Hoje avisa quando está vencido ou perto de vencer." },
      { chave: "pcmso_recebido", rotulo: "Documento do PCMSO em vigor recebido", tipo: "bool", ajuda: "Para PCMSO feito por outra empresa: marque quando a cliente mandar o documento." },
      { chave: "ativa", rotulo: "Ativa", tipo: "bool" }] },
    pacientes: { editar: pode(...EQUIPE), busca: true, nome: ["paciente", "pacientes"], campos: [
      { chave: "nome", rotulo: "Nome", obrigatorio: true }, { chave: "cpf", rotulo: "CPF" }, { chave: "nascimento", rotulo: "Nascimento", tipo: "data" },
      { chave: "empresa_id", rotulo: "Empresa", tipo: "opcoes", opcoes: empresas, ajuda: "Em branco = particular." },
      { chave: "telefone", rotulo: "Telefone", formato: fone, naLista: false, ajuda: "Com DDD. Particular com telefone passa a receber confirmação e lembrete por este número." },
      { chave: "setor", rotulo: "Setor", naLista: false }, { chave: "cargo", rotulo: "Cargo" }, { chave: "rg", rotulo: "RG", naLista: false }] },
    contatos: { editar: pode(...EQUIPE), busca: true, nome: ["contato", "contatos"], campos: [
      { chave: "telefone", rotulo: "WhatsApp", formato: fone, obrigatorio: true, ajuda: "Com DDD." }, { chave: "nome", rotulo: "Nome" },
      { chave: "tipo", rotulo: "Tipo", tipo: "opcoes", opcoes: tipoContato, obrigatorio: true },
      { chave: "empresa_id", rotulo: "Empresa principal", tipo: "opcoes", opcoes: empresas, ajuda: "Para ligar a mais empresas, use a aba “Quem agenda”." }] },
    profissionais: { editar: pode("SUPERVISAO"), nome: ["profissional", "profissionais"], campos: [{ chave: "nome", rotulo: "Nome", obrigatorio: true }, { chave: "ativo", rotulo: "Ativo", tipo: "bool" }] },
    exames: { editar: pode(), nome: ["exame", "exames"], campos: [
      { chave: "codigo", rotulo: "Código", obrigatorio: true }, { chave: "nome", rotulo: "Nome", obrigatorio: true }, { chave: "funcao_id", rotulo: "Função que executa", tipo: "opcoes", opcoes: funcoes },
      { chave: "ordem", rotulo: "Ordem no menu", tipo: "numero" }, { chave: "ativo", rotulo: "Ativo", tipo: "bool" }] },
    funcoes: { editar: pode(), nome: ["função", "funções"], campos: [
      { chave: "codigo", rotulo: "Código", obrigatorio: true }, { chave: "nome", rotulo: "Nome", obrigatorio: true }, { chave: "capacidade_por_hora", rotulo: "Pacientes/hora por profissional", tipo: "numero" },
      { chave: "requer_humano", rotulo: "Agenda própria (vai para a equipe)", tipo: "bool" }, { chave: "ativa", rotulo: "Ativa", tipo: "bool" }] },
    "tipos-aso": { editar: pode(), nome: ["tipo de ASO", "tipos de ASO"], campos: [
      { chave: "codigo", rotulo: "Código", obrigatorio: true }, { chave: "nome", rotulo: "Nome", obrigatorio: true }, { chave: "ordem", rotulo: "Ordem", tipo: "numero" },
      { chave: "exige_cadastro_completo", rotulo: "Pede RG, setor e cargo", tipo: "bool" }] },
  };
  const atual = config[aba];
  return (
    <>
      <Cabecalho titulo="Cadastros" />
      <Abas ativa={aba} mudar={setAba} abas={[["empresas", "Empresas"], ["pacientes", "Pacientes"], ["quem", "Quem agenda"], ["contatos", "Contatos"], ["profissionais", "Profissionais"], ["exames", "Exames"], ["funcoes", "Funções"], ["tipos-aso", "Tipos de ASO"]]} />
      <div className="cartao">
        {aba === "quem" ? <QuemAgendaAba empresas={cat.empresas} podeEditar={pode(...EQUIPE)} />
          : <TabelaCadastro key={aba} recurso={aba} campos={atual.campos} podeEditar={atual.editar} busca={atual.busca} nome={atual.nome} filtro={atual.filtro} />}
      </div>
    </>
  );
}
