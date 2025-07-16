"""
Modelos de dados para o sistema de comparação de documentos jurídicos.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


class TipoDiferenca(str, Enum):
    """Tipos de diferenças entre segmentos."""
    SEM_DIFERENCA = "sem_diferenca"
    MODIFICADO = "modificado"
    ADICIONADO = "adicionado"
    REMOVIDO = "removido"


class SignificanciaJuridica(str, Enum):
    """Classificação da significância jurídica das alterações."""
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"
    NENHUMA = "nenhuma"

@dataclass
class Segmento:
    """Representa um segmento de texto do documento."""
    texto: str
    pagina: int
    posicao: int
    tipo: str = "texto"
    contexto: Optional[Any] = None

@dataclass
class ComparacaoSegmento:
    """Resultado da comparação entre dois segmentos."""
    segmento_pdf1: Optional[Segmento] = None
    segmento_pdf2: Optional[Segmento] = None
    tipo_diferenca: TipoDiferenca = TipoDiferenca.SEM_DIFERENCA
    significativo: bool = False
    significancia_juridica: SignificanciaJuridica = SignificanciaJuridica.NENHUMA
    confianca: float = 1.0
    detalhes: Optional[str] = None

@dataclass
class Documento:
    """Representa um documento processado."""
    nome_arquivo: str
    seguradora: Optional[str] = None
    data_versao: Optional[datetime] = None
    ramo_seguro: Optional[str] = None
    segmentos: List[Segmento] = field(default_factory=list)
    metadados: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResultadoComparacao:
    """Resultado completo da comparação entre dois documentos."""
    documento1: Documento
    documento2: Documento
    comparacoes: List[ComparacaoSegmento] = field(default_factory=list)
    estatisticas: Dict[str, Any] = field(default_factory=dict)
    data_comparacao: datetime = field(default_factory=datetime.now)

@dataclass
class RespostaComparacao:
    """Resposta da API contendo apenas comparações e estatísticas."""
    comparacoes: List[ComparacaoSegmento] = field(default_factory=list)
    estatisticas: Dict[str, Any] = field(default_factory=dict)
    data_comparacao: datetime = field(default_factory=datetime.now)

@dataclass
class ConfiguracaoProcessamento:
    """Configurações para o processamento de documentos."""
    # Configurações de extração
    preservar_formatacao: bool = True
    detectar_quebras_linha: bool = True
    
    # Configurações de normalização
    corrigir_hifenacao: bool = True
    remover_espacos_duplicados: bool = True
    preservar_termos_tecnicos: bool = True
    
    # Configurações de segmentação
    tamanho_minimo_segmento: int = 30
    incluir_contexto: bool = True
    
    # Configurações de comparação
    threshold_similaridade: float = 0.85
    detectar_significancia: bool = True 