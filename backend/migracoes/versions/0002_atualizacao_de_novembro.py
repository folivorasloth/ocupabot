"""proposta de horário, contato com várias empresas, mensagens seguidas, PCMSO e acesso

- aprovacoes: proposta de outro horário (quando, até quando, quem propôs) e marcador de cadastro divergente;
- contato_empresas: um contato (contabilidade, credenciadora, RH) agenda por várias empresas;
- entradas_pendentes: mensagens seguidas do mesmo número esperam para virar uma resposta só;
- empresas: PCMSO (quem fez, vale até, documento recebido);
- usuarios: troca de senha obrigatória no primeiro acesso e WhatsApp de quem é da equipe;
- conversas: quando a pessoa foi avisada de que a conversa está com a equipe;
- o perfil LEITURA deixou de existir: quem o tinha fica desativado (não ganha permissão de escrita sozinho).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13 10:37:31
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('entradas_pendentes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('telefone', sa.String(length=20), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('id_externo', sa.String(length=120), nullable=True),
    sa.Column('recebida_em', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id_externo')
    )
    with op.batch_alter_table('entradas_pendentes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_entradas_pendentes_telefone'), ['telefone'], unique=False)

    op.create_table('contato_empresas',
    sa.Column('contato_id', sa.Integer(), nullable=False),
    sa.Column('empresa_id', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['contato_id'], ['contatos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('contato_id', 'empresa_id')
    )
    with op.batch_alter_table('contato_empresas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_contato_empresas_empresa_id'), ['empresa_id'], unique=False)

    # nada aponta para aprovacoes: o batch pode recriar a tabela para incluir a chave estrangeira
    with op.batch_alter_table('aprovacoes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('proposta_em', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('proposta_ate', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('proposta_por_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('divergencia_cadastro', sa.Boolean(), server_default=sa.false(),
                                      nullable=False))
        batch_op.create_foreign_key('fk_aprovacoes_proposta_por_id_usuarios', 'usuarios', ['proposta_por_id'],
                                    ['id'])

    # conversas, empresas e usuarios são apontadas por outras tabelas: só acrescentam coluna e índice,
    # sem recriar a tabela (com foreign_keys=ON o SQLite recusaria o DROP)
    with op.batch_alter_table('conversas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('aviso_equipe_em', sa.DateTime(), nullable=True))

    with op.batch_alter_table('empresas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pcmso_elaborado_por', sa.Enum('CLINICA', 'TERCEIRO', name='pcmsoelaboradopor', native_enum=False, length=30), nullable=True))
        batch_op.add_column(sa.Column('pcmso_vence_em', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('pcmso_recebido', sa.Boolean(), server_default=sa.false(), nullable=False))

    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trocar_senha', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('whatsapp', sa.String(length=20), nullable=True))
        batch_op.create_index(batch_op.f('ix_usuarios_whatsapp'), ['whatsapp'], unique=True)

    op.execute("UPDATE usuarios SET perfil = 'RECEPCAO', ativo = 0, versao_sessao = versao_sessao + 1 "
               "WHERE perfil = 'LEITURA'")
    # o vínculo principal (contatos.empresa_id) continua valendo; nada a copiar para contato_empresas


def downgrade() -> None:
    # proposta em aberto volta a ser pedido pendente (a vaga continua segura); a vencida vira recusada
    op.execute("UPDATE aprovacoes SET status = 'PENDENTE' WHERE status = 'AGUARDANDO_CLIENTE'")
    op.execute("UPDATE aprovacoes SET status = 'RECUSADA' WHERE status = 'EXPIRADA'")
    op.execute("UPDATE contatos SET tipo = 'RH' WHERE tipo IN ('CREDENCIADORA', 'CONTABILIDADE')")

    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usuarios_whatsapp'))
        batch_op.drop_column('whatsapp')
        batch_op.drop_column('trocar_senha')

    with op.batch_alter_table('empresas', schema=None) as batch_op:
        batch_op.drop_column('pcmso_recebido')
        batch_op.drop_column('pcmso_vence_em')
        batch_op.drop_column('pcmso_elaborado_por')

    with op.batch_alter_table('conversas', schema=None) as batch_op:
        batch_op.drop_column('aviso_equipe_em')

    with op.batch_alter_table('aprovacoes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_aprovacoes_proposta_por_id_usuarios', type_='foreignkey')
        batch_op.drop_column('divergencia_cadastro')
        batch_op.drop_column('proposta_por_id')
        batch_op.drop_column('proposta_ate')
        batch_op.drop_column('proposta_em')

    with op.batch_alter_table('contato_empresas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_contato_empresas_empresa_id'))

    op.drop_table('contato_empresas')
    with op.batch_alter_table('entradas_pendentes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_entradas_pendentes_telefone'))

    op.drop_table('entradas_pendentes')
