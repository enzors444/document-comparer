"""
Modelos de dados para o sistema de comparação de documentos jurídicos.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
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


class Segmento(BaseModel):
    """Representa um segmento de texto do documento."""
    texto: str = Field(..., description="Texto do segmento")
    pagina: int = Field(..., description="Número da página")
    posicao: int = Field(..., description="Posição relativa no documento")
    tipo: str = Field(default="texto", description="Tipo do segmento (título, cláusula, etc.)")
    contexto: Optional[Any] = Field(default=None, description="Contexto adicional (pode ser string ou dict)")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ComparacaoSegmento(BaseModel):
    """Resultado da comparação entre dois segmentos."""
    segmento_pdf1: Optional[Segmento] = Field(default=None, description="Segmento do primeiro PDF")
    segmento_pdf2: Optional[Segmento] = Field(default=None, description="Segmento do segundo PDF")
    tipo_diferenca: TipoDiferenca = Field(..., description="Tipo de diferença identificada")
    significativo: bool = Field(..., description="Se a alteração é juridicamente significativa")
    significancia_juridica: SignificanciaJuridica = Field(..., description="Nível de significância")
    confianca: float = Field(..., ge=0.0, le=1.0, description="Confiança na comparação (0-1)")
    detalhes: Optional[str] = Field(default=None, description="Detalhes adicionais da comparação")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Documento(BaseModel):
    """Representa um documento processado."""
    nome_arquivo: str = Field(..., description="Nome do arquivo original")
    seguradora: Optional[str] = Field(default=None, description="Nome da seguradora")
    data_versao: Optional[datetime] = Field(default=None, description="Data da versão")
    ramo_seguro: Optional[str] = Field(default=None, description="Ramo do seguro")
    segmentos: List[Segmento] = Field(default_factory=list, description="Segmentos do documento")
    metadados: Dict[str, Any] = Field(default_factory=dict, description="Metadados adicionais")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ResultadoComparacao(BaseModel):
    """Resultado completo da comparação entre dois documentos."""
    documento1: Documento = Field(..., description="Primeiro documento")
    documento2: Documento = Field(..., description="Segundo documento")
    comparacoes: List[ComparacaoSegmento] = Field(default_factory=list, description="Lista de comparações")
    estatisticas: Dict[str, Any] = Field(default_factory=dict, description="Estatísticas da comparação")
    data_comparacao: datetime = Field(default_factory=datetime.now, description="Data da comparação")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RespostaComparacao(BaseModel):
    """Resposta da API contendo apenas comparações e estatísticas."""
    comparacoes: List[ComparacaoSegmento] = Field(default_factory=list, description="Lista de comparações")
    estatisticas: Dict[str, Any] = Field(default_factory=dict, description="Estatísticas da comparação")
    data_comparacao: datetime = Field(default_factory=datetime.now, description="Data da comparação")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConfiguracaoProcessamento(BaseModel):
    """Configurações para o processamento de documentos."""
    # Configurações de extração
    preservar_formatacao: bool = Field(default=True, description="Preservar formatação original")
    detectar_quebras_linha: bool = Field(default=True, description="Detectar quebras de linha incorretas")
    
    # Configurações de normalização
    corrigir_hifenacao: bool = Field(default=True, description="Corrigir hifenização")
    remover_espacos_duplicados: bool = Field(default=True, description="Remover espaços duplicados")
    preservar_termos_tecnicos: bool = Field(default=True, description="Preservar termos técnicos")
    
    # Configurações de segmentação
    tamanho_minimo_segmento: int = Field(default=30, description="Tamanho mínimo do segmento")
    incluir_contexto: bool = Field(default=True, description="Incluir contexto nos segmentos")
    
    # Configurações de comparação
    threshold_similaridade: float = Field(default=0.85, ge=0.0, le=1.0, description="Threshold de similaridade")
    detectar_significancia: bool = Field(default=True, description="Detectar significância jurídica")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 