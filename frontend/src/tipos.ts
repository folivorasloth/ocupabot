export type Perfil = "ADMIN" | "SUPERVISAO" | "RECEPCAO" | "LEITURA";

export interface Usuario { id: number; nome: string; login: string; perfil: Perfil; ativo: boolean }

export interface ExameItem { id: number; nome: string; profissional: string | null }

export interface Agendamento {
  id: number; data: string; horario: string; turno: string; status: string; origem: string;
  paciente: { id: number; nome: string; cpf: string }; empresa: string | null; empresa_id: number | null;
  tipo_aso: string | null; contato: string | null; exames: ExameItem[]; remarcado_de_id: number | null;
  motivo_cancelamento: string | null; observacao: string | null; no_sistema_externo: boolean;
}

export interface Aprovacao {
  id: number; tipo: "NOVO" | "REMARCACAO" | "CANCELAMENTO"; status: string; pedida_em: string | null;
  decidida_em: string | null; motivo: string | null; alterada: boolean; agendamento: Agendamento;
  original: Agendamento | null; exige_supervisao: boolean;
}

export interface Mensagem { id: number; autor: string; texto: string; status: string; em: string; erro: string | null }

export interface Conversa {
  id: number; estado: "BOT" | "AGUARDANDO_HUMANO" | "HUMANO"; fluxo: string | null; etapa: string | null;
  motivo_humano: string | null; atendente_id: number | null; ultima_entrada_em: string | null;
  contato: { id: number; nome: string | null; tipo: string; telefone: string; empresa: string | null; optout: boolean };
  ultima_mensagem: string | null; empresa_informada: number | null; mensagens?: Mensagem[];
}

export type Registro = Record<string, unknown> & { id?: number };
