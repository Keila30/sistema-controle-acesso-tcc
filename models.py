from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash

from extensions import db


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    perfil: Mapped[str] = mapped_column(String(20), nullable=False)

    def verificar_senha(self, senha: str) -> bool:
        return check_password_hash(self.senha_hash, senha)


class Arquivo(db.Model):
    """Biblioteca de mapas: cada PDF é guardado uma única vez, dentro do banco."""

    __tablename__ = "arquivos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome_arquivo: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    tipo_arquivo: Mapped[str] = mapped_column(String(20), nullable=False, default="pdf")
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    enviado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=agora_utc
    )
    # Conteúdo do PDF. "deferred" = só é lido do banco quando realmente precisamos
    # (visualizar ou baixar), assim as listas do painel continuam rápidas.
    conteudo: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)


class Solicitacao(db.Model):
    __tablename__ = "solicitacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(db.ForeignKey("usuarios.id"), nullable=False)
    # arquivo da biblioteca que o operador escolheu
    arquivo_id: Mapped[int] = mapped_column(db.ForeignKey("arquivos.id"), nullable=False)
    # nome do mapa no momento do pedido
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    # status possíveis: "pendente", "aprovado" ou "negado"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    # quando o operador baixou o arquivo (vazio = ainda não baixou)
    baixado_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    usuario: Mapped["Usuario"] = db.relationship("Usuario", backref="solicitacoes")
    arquivo: Mapped["Arquivo"] = db.relationship("Arquivo", backref="solicitacoes")
