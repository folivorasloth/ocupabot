"""permissão por pessoa, contato desativado e agendamento de teste

- usuarios.pode_externo: quem é da Recepção e pode remarcar e cancelar o que já está no sistema externo
  (nasce desligada);
- contatos.ativo: contato desativado sai das listas e o bot o trata como um número qualquer (nasce ativo);
- agendamentos.teste: agendamento de teste ocupa a vaga, mas não manda mensagem.

As três tabelas são apontadas por outras: só ADD COLUMN, sem recriar a tabela.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19 15:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pode_externo', sa.Boolean(), server_default=sa.false(), nullable=False))

    with op.batch_alter_table('contatos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ativo', sa.Boolean(), server_default=sa.true(), nullable=False))

    with op.batch_alter_table('agendamentos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('teste', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.execute("DELETE FROM agendamento_itens WHERE agendamento_id IN (SELECT id FROM agendamentos WHERE teste)")
    op.execute("DELETE FROM agendamentos WHERE teste")
    with op.batch_alter_table('agendamentos', schema=None) as batch_op:
        batch_op.drop_column('teste')

    with op.batch_alter_table('contatos', schema=None) as batch_op:
        batch_op.drop_column('ativo')

    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_column('pode_externo')
