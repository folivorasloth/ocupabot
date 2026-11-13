export type Perfil = "ADMIN" | "SUPERVISAO" | "RECEPCAO";

export interface Usuario {
  id: number; nome: string; login: string; perfil: Perfil; ativo: boolean; trocar_senha: boolean; whatsapp: string | null;
}

export interface ExameItem { id: number; nome: string; profissional: string | null }

export interface Agendamento {
  id: number; data: string; horario: string; turno: string; status: string; origem: string;
  paciente: { id: number; nome: string; cpf: string }; empresa: string | null; empresa_id: number | null;
  tipo_aso: string | null; contato: string | null; contato_nome: string | null; sem_aviso: boolean;
  exames: ExameItem[]; remarcado_de_id: number | null;
  motivo_cancelamento: string | null; observacao: string | null; no_sistema_externo: boolean;
}

export type StatusAprovacao = "PENDENTE" | "AGUARDANDO_CLIENTE" | "APROVADA" | "RECUSADA" | "EXPIRADA";

export interface Aprovacao {
  id: number; tipo: "NOVO" | "REMARCACAO" | "CANCELAMENTO"; status: StatusAprovacao; pedida_em: string | null;
  decidida_em: string | null; motivo: string | null; alterada: boolean; agendamento: Agendamento;
  original: Agendamento | null; exige_supervisao: boolean; contato_id: number | null;
  proposta_em: string | null; proposta_ate: string | null; marcadores: string[];
}

export interface Mensagem { id: number; autor: string; texto: string; status: string; em: string; erro: string | null }

export type EstadoConversa = "BOT" | "AGUARDANDO_HUMANO" | "HUMANO";

export interface Conversa {
  id: number; estado: EstadoConversa; fluxo: string | null; etapa: string | null;
  motivo_humano: string | null; atendente_id: number | null; ultima_entrada_em: string | null; simulada: boolean;
  contato: { id: number; nome: string | null; tipo: string; telefone: string; empresa: string | null; empresas_ids: number[]; optout: boolean };
  ultima_mensagem: string | null; empresa_informada: number | null; mensagens?: Mensagem[];
}

export interface QuemAgenda {
  id: number; telefone: string; nome: string | null; tipo: string; empresa_id: number | null; optout: boolean;
  empresas: { id: number; nome: string }[];
}

export interface Contadores {
  aprovacoes_pendentes: number; esperando_cliente: number; conversas_esperando: number; conversas_com_equipe: number;
}

export type Registro = Record<string, unknown> & { id?: number };
