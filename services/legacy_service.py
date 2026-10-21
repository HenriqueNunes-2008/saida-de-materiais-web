"""Mantem os imports antigos enquanto os servicos ficam separados por funcao."""

# Compatibilidade para codigo que ainda importe funcoes deste modulo historico.
from services.excel_service import gerar_excel, obter_nome_arquivo_excel
from services.saida_service import (
    get_nomes,
    get_projetos,
    get_report_suggestions,
    registrar_saida,
)

__all__ = [
    "gerar_excel",
    "get_nomes",
    "get_projetos",
    "get_report_suggestions",
    "obter_nome_arquivo_excel",
    "registrar_saida",
]
