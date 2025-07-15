"""
Módulo de extração de conteúdo de PDFs com preservação de formatação.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pdfplumber
import PyPDF2
import spacy

from .models import Documento, Segmento, ConfiguracaoProcessamento
from .utils import setup_logging

logger = setup_logging(__name__)

# Carregar modelo spaCy para português (carregado uma vez)
_nlp_pt = spacy.load('pt_core_news_sm')


class ExtratorPDF:
    """Classe responsável pela extração estruturada de conteúdo de PDFs."""
    
    def __init__(self, config: ConfiguracaoProcessamento):
        self.config = config
        self.termos_tecnicos = self._carregar_termos_tecnicos()
        
    def _carregar_termos_tecnicos(self) -> set:
        """Carrega lista de termos técnicos jurídicos para preservação."""
        return {
            # Termos de seguros
            "cobertura", "garantia", "sinistro", "indenização", "prêmio", "apólice",
            "segurado", "seguradora", "corretor", "beneficiário", "risco", "exclusão",
            "franquia", "limite", "vigência", "rescisão", "renovação", "endosso",
            
            # Termos jurídicos
            "cláusula", "parágrafo", "inciso", "alínea", "artigo", "lei", "decreto",
            "contrato", "obrigação", "responsabilidade", "indenização", "compensação",
            "exclusão", "limitação", "renúncia", "arbitragem", "jurisdição", "foro",
            
            # Expressões específicas
            "condições gerais", "condições especiais", "cláusulas contratuais",
            "objeto do seguro", "riscos cobertos", "riscos excluídos",
            "obrigações do segurado", "obrigações da seguradora",
            "procedimento de sinistro", "pagamento de indenização"
        }
    
    def extrair_documento(self, caminho_pdf: str) -> Documento:
        """Extrai conteúdo estruturado de um PDF."""
        logger.info(f"Iniciando extração do documento: {caminho_pdf}")
        
        try:
            # Extrair metadados básicos
            metadados = self._extrair_metadados(caminho_pdf)
            
            # Extrair texto com formatação
            texto_formatado = self._extrair_texto_formatado(caminho_pdf)
            
            # Detectar estrutura do documento
            estrutura = self._detectar_estrutura(texto_formatado)
            
            # Segmentar conteúdo
            segmentos = self._segmentar_conteudo(texto_formatado, estrutura)
            
            # Criar objeto Documento
            documento = Documento(
                nome_arquivo=Path(caminho_pdf).name,
                seguradora=metadados.get("seguradora"),
                data_versao=metadados.get("data_versao"),
                ramo_seguro=metadados.get("ramo_seguro"),
                segmentos=segmentos,
                metadados=metadados
            )
            
            logger.info(f"Extração concluída: {len(segmentos)} segmentos encontrados")
            return documento
            
        except Exception as e:
            logger.error(f"Erro na extração do documento {caminho_pdf}: {str(e)}")
            raise
    
    def _extrair_metadados(self, caminho_pdf: str) -> Dict[str, Any]:
        """Extrai metadados do PDF."""
        metadados = {}
        
        try:
            with open(caminho_pdf, 'rb') as arquivo:
                leitor = PyPDF2.PdfReader(arquivo)
                
                # Informações básicas
                metadados["num_paginas"] = len(leitor.pages)
                metadados["tamanho_arquivo"] = arquivo.tell()
                
                # Tentar extrair informações do título
                if leitor.metadata:
                    metadados.update(leitor.metadata)
                
                # Detectar seguradora e ramo do nome do arquivo
                nome_arquivo = Path(caminho_pdf).name.lower()
                metadados.update(self._detectar_info_arquivo(nome_arquivo))
                
        except Exception as e:
            logger.warning(f"Erro ao extrair metadados: {str(e)}")
        
        return metadados
    
    def _detectar_info_arquivo(self, nome_arquivo: str) -> Dict[str, str]:
        """Detecta informações baseadas no nome do arquivo."""
        info = {}
        
        # Padrões comuns de seguradoras
        seguradoras = {
            "tokio": "Tokio Marine",
            "porto": "Porto Seguro", 
            "sul": "Sul América",
            "bradesco": "Bradesco Seguros",
            "itau": "Itaú Seguros",
            "allianz": "Allianz",
            "zurich": "Zurich",
            "mapfre": "Mapfre"
        }
        
        for padrao, seguradora in seguradoras.items():
            if padrao in nome_arquivo:
                info["seguradora"] = seguradora
                break
        
        # Detectar ramo do seguro
        ramos = {
            "auto": "Automóvel",
            "residencial": "Residencial", 
            "empresarial": "Empresarial",
            "vida": "Vida",
            "saude": "Saúde",
            "previdencia": "Previdência"
        }
        
        for padrao, ramo in ramos.items():
            if padrao in nome_arquivo:
                info["ramo_seguro"] = ramo
                break
        
        return info
    
    def _extrair_texto_formatado(self, caminho_pdf: str) -> List[Dict[str, Any]]:
        """Extrai texto preservando formatação e estrutura, removendo rodapés/cabeçalhos repetidos."""
        texto_formatado = []
        rodape_cabecalho_contagem = {}
        paginas_textos = []
        with pdfplumber.open(caminho_pdf) as pdf:
            for num_pagina, pagina in enumerate(pdf.pages, 1):
                logger.debug(f"Processando página {num_pagina}")
                texto_pagina = self._extrair_texto_pagina(pagina, num_pagina)
                paginas_textos.append([e["texto"] for e in texto_pagina])
                texto_formatado.extend(texto_pagina)
        # Detectar rodapés/cabeçalhos repetidos (presentes em 80%+ das páginas)
        total_paginas = len(paginas_textos)
        for pagina in paginas_textos:
            for linha in set(pagina):
                rodape_cabecalho_contagem[linha] = rodape_cabecalho_contagem.get(linha, 0) + 1
        rodapes_cabecalhos = {linha for linha, count in rodape_cabecalho_contagem.items() if count >= max(2, int(0.8 * total_paginas))}
        # Filtrar do texto_formatado
        texto_formatado_filtrado = [e for e in texto_formatado if e["texto"] not in rodapes_cabecalhos]
        return texto_formatado_filtrado
    
    def _extrair_texto_pagina(self, pagina, num_pagina: int) -> List[Dict[str, Any]]:
        """Extrai texto de uma página específica."""
        elementos = []
        
        # Extrair texto com coordenadas
        texto_completo = pagina.extract_text()
        if not texto_completo:
            return elementos
        
        # Dividir em linhas e processar
        linhas = texto_completo.split('\n')
        
        for pos, linha in enumerate(linhas):
            if linha.strip():
                # Detectar tipo de elemento
                tipo = self._detectar_tipo_elemento(linha)
                
                elemento = {
                    "texto": linha.strip(),
                    "pagina": num_pagina,
                    "posicao": pos,
                    "tipo": tipo,
                    "coordenadas": self._extrair_coordenadas(pagina, linha)
                }
                
                elementos.append(elemento)
        
        return elementos
    
    def _detectar_tipo_elemento(self, texto: str) -> str:
        """Detecta o tipo de elemento baseado no conteúdo."""
        texto_limpo = texto.strip().lower()
        
        # Padrões para detecção
        if re.match(r'^CLÁUSULA\s+\d+[ªº]?\s*[-–—]\s*', texto, re.IGNORECASE):
            return "titulo_clausula"
        elif re.match(r'^[IVX]+\.\s+', texto):
            return "titulo_secao"
        elif re.match(r'^\d+\.\s+', texto):
            return "item_numerado"
        elif re.match(r'^[a-z]\)\s+', texto):
            return "item_letra"
        elif re.match(r'^[A-Z]\.\s+', texto):
            return "item_maiuscula"
        elif re.match(r'^[A-Z\s]+$', texto) and len(texto.strip()) > 3:
            return "titulo"
        elif texto.isupper() and len(texto.strip()) > 10:
            return "titulo_destaque"
        else:
            return "texto"
    
    def _extrair_coordenadas(self, pagina, texto: str) -> Dict[str, float]:
        """Extrai coordenadas aproximadas do texto na página."""
        # Implementação simplificada - em produção seria mais precisa
        return {
            "x": 0.0,
            "y": 0.0,
            "width": 0.0,
            "height": 0.0
        }
    
    def _detectar_estrutura(self, texto_formatado: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detecta a estrutura geral do documento."""
        estrutura = {
            "clausulas": [],
            "secoes": [],
            "glossario": None,
            "anexos": []
        }
        
        for elemento in texto_formatado:
            if elemento["tipo"] == "titulo_clausula":
                estrutura["clausulas"].append({
                    "texto": elemento["texto"],
                    "pagina": elemento["pagina"],
                    "posicao": elemento["posicao"]
                })
            elif elemento["tipo"] == "titulo_secao":
                estrutura["secoes"].append({
                    "texto": elemento["texto"],
                    "pagina": elemento["pagina"],
                    "posicao": elemento["posicao"]
                })
        
        return estrutura
    
    def _segmentar_conteudo(self, texto_formatado: List[Dict[str, Any]], estrutura: Dict[str, Any]) -> List[Segmento]:
        """Segmentação aprimorada: cada segmento é uma frase completa, reconstruindo frases cortadas e separando listas item a item."""
        import re
        segmentos = []
        posicao_global = 0
        contexto_atual = None
        clausula_atual = None
        secao_atual = None
        bloco_atual = []
        conectores = {"que", "de", "para", "e", "ou", "mas", "porém", "contudo", "todavia", "enquanto", "quando", "como", "se", "com", "em", "por", "a", "o", "as", "os", "no", "na", "nos", "nas", "do", "da", "dos", "das"}
        def eh_titulo(tipo, texto):
            return tipo in ["titulo_clausula", "titulo_secao", "titulo", "titulo_destaque"] or (texto.isupper() and len(texto.split()) <= 8)
        def eh_lista(texto):
            return bool(re.match(r'^[\-\*\d]+[\).\-]', texto.strip())) or bool(re.match(r'^[a-z]\)\s+', texto.strip()))
        def termina_com_pontuacao_forte(linha):
            return bool(re.search(r'[.!?]$', linha.strip()))
        def termina_com_conector(linha):
            palavras = linha.strip().split()
            return palavras and palavras[-1].lower() in conectores
        i = 0
        while i < len(texto_formatado):
            elem = texto_formatado[i]
            tipo = elem["tipo"]
            texto = elem["texto"].strip()
            # Se for título, fecha bloco anterior e inicia novo contexto
            if eh_titulo(tipo, texto):
                if bloco_atual:
                    frase_reconstruida = " ".join(bloco_atual).strip()
                    if frase_reconstruida:
                        frases = self._dividir_em_frases(frase_reconstruida)
                        for frase in frases:
                            if frase.strip():
                                segmentos.append(Segmento(
                                    texto=frase.strip(),
                                    pagina=elem["pagina"],
                                    posicao=posicao_global,
                                    tipo=self._detectar_tipo_elemento(frase),
                                    contexto={
                                        "clausula": clausula_atual,
                                        "secao": secao_atual,
                                        "titulo": contexto_atual
                                    }
                                ))
                                posicao_global += 1
                    bloco_atual = []
                contexto_atual = texto
                if tipo == "titulo_clausula":
                    clausula_atual = texto
                if tipo == "titulo_secao":
                    secao_atual = texto
                i += 1
                continue
            # Se for item de lista, separar cada item
            if eh_lista(texto):
                itens = self._separar_itens_lista(texto)
                for item in itens:
                    if item:
                        segmentos.append(Segmento(
                            texto=item.strip(),
                            pagina=elem["pagina"],
                            posicao=posicao_global,
                            tipo="item_lista",
                            contexto={
                                "clausula": clausula_atual,
                                "secao": secao_atual,
                                "titulo": contexto_atual
                            }
                        ))
                        posicao_global += 1
                bloco_atual = []
                i += 1
                continue
            # Se for linha vazia, fecha bloco
            if not texto:
                if bloco_atual:
                    frase_reconstruida = " ".join(bloco_atual).strip()
                    if frase_reconstruida:
                        frases = self._dividir_em_frases(frase_reconstruida)
                        for frase in frases:
                            if frase.strip():
                                segmentos.append(Segmento(
                                    texto=frase.strip(),
                                    pagina=elem["pagina"],
                                    posicao=posicao_global,
                                    tipo=self._detectar_tipo_elemento(frase),
                                    contexto={
                                        "clausula": clausula_atual,
                                        "secao": secao_atual,
                                        "titulo": contexto_atual
                                    }
                                ))
                                posicao_global += 1
                    bloco_atual = []
                i += 1
                continue
            # Reconstrução de frases: juntar até pontuação forte e não terminar em conector
            bloco_atual.append(texto)
            if termina_com_pontuacao_forte(texto) and not termina_com_conector(texto):
                frase_reconstruida = " ".join(bloco_atual).strip()
                if frase_reconstruida:
                    frases = self._dividir_em_frases(frase_reconstruida)
                    for frase in frases:
                        if frase.strip():
                            segmentos.append(Segmento(
                                texto=frase.strip(),
                                pagina=elem["pagina"],
                                posicao=posicao_global,
                                tipo=self._detectar_tipo_elemento(frase),
                                contexto={
                                    "clausula": clausula_atual,
                                    "secao": secao_atual,
                                    "titulo": contexto_atual
                                }
                            ))
                            posicao_global += 1
                bloco_atual = []
            i += 1
        # Salva último bloco
        if bloco_atual:
            frase_reconstruida = " ".join(bloco_atual).strip()
            if frase_reconstruida:
                frases = self._dividir_em_frases(frase_reconstruida)
                for frase in frases:
                    if frase.strip():
                        segmentos.append(Segmento(
                            texto=frase.strip(),
                            pagina=elem["pagina"],
                            posicao=posicao_global,
                            tipo=self._detectar_tipo_elemento(frase),
                            contexto={
                                "clausula": clausula_atual,
                                "secao": secao_atual,
                                "titulo": contexto_atual
                            }
                        ))
                        posicao_global += 1
        return segmentos
    
    def _dividir_em_frases(self, texto: str) -> List[str]:
        """Divide o texto em frases completas, usando spaCy para máxima robustez."""
        doc = _nlp_pt(texto)
        return [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    
    def _separar_secoes_subsecoes(self, texto: str) -> List[str]:
        """Separa seções (XII, XIII), subseções (6.1, 6.2) e títulos em maiúsculas em segmentos distintos."""
        import re
        
        # Padrões para separação de seções e subseções (mais agressivos para títulos importantes)
        padroes = [
            # Seções com numerais romanos (apenas no início de linha)
            r'(?<!^)(?=\n\s*[IVX]+\.\s+)',
            # Subseções numeradas (6.1, 6.2, etc.) - apenas no início de linha
            r'(?<!^)(?=\n\s*\d+\.\s+\d+\.\s+)',
            # Títulos numerados (6. ACEITAÇÃO, etc.) - apenas no início de linha
            r'(?<!^)(?=\n\s*\d+\.\s+[A-Z][A-Z\s]{3,})',
            # Títulos em maiúsculas no início de linha
            r'(?<!^)(?=\n\s*[A-Z][A-Z\s]{4,}\s*$)',
            # Títulos em maiúsculas seguidos de texto - apenas no início de linha
            r'(?<!^)(?=\n\s*[A-Z][A-Z\s]{4,}\s+[A-Z])',
            # Títulos em maiúsculas seguidos de números - apenas no início de linha
            r'(?<!^)(?=\n\s*[A-Z][A-Z\s]{4,}\s+\d)',
            # Múltiplas palavras em maiúsculas - apenas no início de linha
            r'(?<!^)(?=\n\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}\s+){2,}[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,})',
            # Títulos importantes que podem estar no meio do texto (mais agressivo)
            r'(?<!^)(?=\s+[A-Z][A-Z\s]{6,}\s)',  # Palavras únicas em maiúsculas com 6+ chars
            r'(?<!^)(?=\s+[A-Z][A-Z\s]{4,}\s+[A-Z])',  # Títulos seguidos de maiúsculas
            r'(?<!^)(?=\s+[A-Z][A-Z\s]{4,}\s+\d)',  # Títulos seguidos de números
        ]
        
        partes = [texto]
        for padrao in padroes:
            novas_partes = []
            for parte in partes:
                if len(parte.strip()) > 150:  # Reduzir limite para ser mais agressivo
                    subpartes = re.split(padrao, parte)
                    novas_partes.extend(subpartes)
                else:
                    novas_partes.append(parte)
            partes = novas_partes
        
        # Limpar e filtrar partes
        partes_limpas = []
        for parte in partes:
            parte = parte.strip()
            if parte and len(parte) > 30:  # Reduzir tamanho mínimo
                partes_limpas.append(parte)
        
        return partes_limpas

    def _separar_itens_lista(self, texto: str) -> List[str]:
        """Separa itens de lista mesmo sem pontuação forte, mas só quando [a-z]) está no início de linha ou precedido por espaço/pontuação/quebra de linha."""
        import re
        # Separar apenas quando [a-z]) está no início ou precedido por espaço, pontuação ou quebra de linha
        partes = re.split(r'(?<!^)(?:(?<=\s)|(?<=[\.,;:!?\n\r]))(?=[a-z]\)\s+)', texto)
        return [parte.strip() for parte in partes if parte.strip()]
    
    def _extrair_clausulas(self, texto: str) -> List[str]:
        """Extrai cláusulas e segmenta em frases menores."""
        import re
        
        # Encontrar todas as posições onde começam cláusulas
        padrao_inicio = r'\d+\s+CLÁUSULA\s+\d+[ªº]?\s*[-–—]'
        matches = list(re.finditer(padrao_inicio, texto, re.IGNORECASE))
        
        if len(matches) < 2:
            return []
        
        frases_segmentadas = []
        
        # Para cada cláusula, capturar desde o início até o início da próxima
        for i, match in enumerate(matches):
            inicio = match.start()
            
            # Se é a última cláusula, vai até o fim do texto
            if i == len(matches) - 1:
                fim = len(texto)
            else:
                # Senão, vai até o início da próxima cláusula
                fim = matches[i + 1].start()
            
            # Extrair o conteúdo da cláusula
            clausula = texto[inicio:fim].strip()
            if clausula:
                # Segmentar a cláusula em frases menores
                frases_clausula = self._segmentar_clausula_em_frases(clausula)
                frases_segmentadas.extend(frases_clausula)
        
        return frases_segmentadas
    
    def _segmentar_clausula_em_frases(self, clausula: str) -> List[str]:
        """Segmenta uma cláusula em frases menores."""
        import re
        
        frases = []
        
        # Dividir por parágrafos primeiro
        paragrafos = re.split(r'\n\s*\n', clausula)
        
        for paragrafo in paragrafos:
            if not paragrafo.strip():
                continue
                
            # Dividir parágrafo em frases
            frases_paragrafo = re.split(r'(?<=[.!?])\s+', paragrafo.strip())
            
            for frase in frases_paragrafo:
                frase = frase.strip()
                if frase and len(frase) > 10:  # Filtrar frases muito pequenas
                    # Verificar se é um item numerado ou com letra
                    if re.match(r'^\d+\.\s+', frase) or re.match(r'^[a-z]\)\s+', frase):
                        frases.append(frase)
                    else:
                        # Dividir frases muito longas
                        if len(frase) > 200:
                            subfrases = self._dividir_frase_longa(frase)
                            frases.extend(subfrases)
                        else:
                            frases.append(frase)
        
        return frases
    
    def _dividir_frase_longa(self, frase: str) -> List[str]:
        """Divide frases muito longas em partes menores."""
        import re
        
        # Dividir por vírgulas e pontos e vírgulas
        partes = re.split(r'[,;]\s+', frase)
        
        if len(partes) <= 1:
            # Se não conseguiu dividir, tentar por conectores
            partes = re.split(r'\s+(e|ou|mas|porém|contudo|entretanto|todavia)\s+', frase)
        
        frases_divididas = []
        for parte in partes:
            parte = parte.strip()
            if parte and len(parte) > 10:
                frases_divididas.append(parte)
        
        return frases_divididas if frases_divididas else [frase]
    
    def _juntar_fragmentos(self, frases: List[str]) -> List[str]:
        """Une fragmentos curtos ou frases cortadas ao próximo segmento."""
        unidas = []
        buffer = ''
        for frase in frases:
            f = frase.strip()
            if not f:
                continue
            if buffer:
                f = buffer + ' ' + f
                buffer = ''
            if len(f) < 40 and not re.search(r'[.!?]$', f):
                buffer = f
                continue
            unidas.append(f)
        if buffer:
            unidas.append(buffer)
        return unidas
    
    def _deve_juntar(self, frase1: str, frase2: str) -> bool:
        import re
        
        # URLs fragmentadas
        if re.search(r'https?://[^\s]*$', frase1.strip()) and not frase2.strip().startswith('http'):
            return True
        
        # Frases que terminam com vírgula, "e", "ou", ou conectores
        if frase1.strip().endswith(',') or frase1.strip().endswith(' e') or frase1.strip().endswith(' ou'):
            return True
        
        # Frases que terminam com "..." ou "…"
        if frase1.strip().endswith('...') or frase1.strip().endswith('…'):
            return True
        
        # Listas numeradas fragmentadas
        match1 = re.match(r'^[a-z]\)\s+', frase1.strip())
        match2 = re.match(r'^[a-z]\)\s+', frase2.strip())
        if match1 and match2:
            letra1 = re.match(r'^([a-z])\)', frase1.strip())
            letra2 = re.match(r'^([a-z])\)', frase2.strip())
            if letra1 and letra2:
                if ord(letra2.group(1)) - ord(letra1.group(1)) <= 3:
                    return True
        
        # Frases que começam com conectores (ex: "a) No momento da formalização")
        if re.match(r'^[a-z]\)\s+', frase2.strip()) and not re.match(r'^[a-z]\)\s+', frase1.strip()):
            if not re.search(r'[.!?]$', frase1.strip()):
                return True
        
        # Frases que começam com minúscula e a anterior não termina com pontuação forte
        if frase2 and frase2[0].islower() and not re.search(r'[.!?]$', frase1.strip()):
            return True
        
        # NÃO juntar se a segunda frase for um título importante
        if self._eh_titulo_importante(frase2):
            return False
        
        # NÃO juntar se a segunda frase for um item numerado
        if re.match(r'^\d+\.', frase2.strip()):
            return False
        
        # NÃO juntar se a segunda frase for um item com letra
        if re.match(r'^[a-z]\)\s+', frase2.strip()):
            return False
        
        # NÃO juntar se a segunda frase for um item com letra maiúscula
        if re.match(r'^[A-Z]\.\s+', frase2.strip()):
            return False
        
        # NÃO juntar se a segunda frase for um título em maiúsculas
        if re.match(r'^[A-Z][A-Z\s]{4,}$', frase2.strip()):
            return False
        
        # NÃO juntar se a segunda frase for uma seção com numerais romanos
        if re.match(r'^[IVX]+\.\s+', frase2.strip()):
            return False
        
        # Evitar juntar cláusulas diferentes
        if 'CLÁUSULA' in frase1.upper() and 'CLÁUSULA' in frase2.upper():
            num1 = re.search(r'CLÁUSULA\s+(\d+)[ªº]?', frase1.upper())
            num2 = re.search(r'CLÁUSULA\s+(\d+)[ªº]?', frase2.upper())
            if num1 and num2 and num1.group(1) != num2.group(1):
                return False
        
        # Verificar se são fragmentos de uma mesma cláusula
        if 'CLÁUSULA' in frase1.upper() and not 'CLÁUSULA' in frase2.upper():
            return True
        
        return False
    
    def _eh_titulo_importante(self, frase: str) -> bool:
        """Verifica se a frase é um título importante que deve ficar separado."""
        import re
        
        frase_limpa = frase.strip()
        
        # Padrões de títulos importantes (mais específicos)
        padroes_titulos = [
            r'^[IVX]+\.\s+',  # Seções com numerais romanos
            r'^\d+\.\s+[A-Z][A-Z\s]{3,}',  # Títulos numerados
            r'^[A-Z][A-Z\s]{4,}\s*$',  # Títulos em maiúsculas no final
            r'^[A-Z][A-Z\s]{3,}:$',  # Títulos que terminam com dois pontos
            r'^[A-Z][A-Z\s]{3,}\s+\d+',  # Títulos seguidos de números
            r'^[A-Z][A-Z\s]{3,}\s+[A-Z]',  # Títulos seguidos de maiúsculas
        ]
        
        for padrao in padroes_titulos:
            if re.match(padrao, frase_limpa):
                return True
        
        # Verificar se é uma palavra única em maiúsculas com significado
        if re.match(r'^[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{8,}$', frase_limpa):  # Aumentar para 8+ caracteres
            # Verificar se não é apenas uma sequência de letras sem sentido
            if len(frase_limpa) <= 20:  # Palavras únicas com até 20 caracteres
                return True
        
        return False
    
    def _determinar_pagina_frase(self, frase: str, texto_formatado: List[Dict[str, Any]]) -> int:
        """Determina a página de uma frase baseada no texto original."""
        # Buscar a frase no texto formatado para encontrar a página
        for elemento in texto_formatado:
            if frase in elemento["texto"]:
                return elemento["pagina"]
        
        # Se não encontrar, retornar página 1 como padrão
        return 1
    
    def _detectar_tipo_frase(self, frase: str) -> str:
        """Detecta o tipo da frase baseado no conteúdo."""
        frase_upper = frase.upper()
        
        # Padrões para detecção
        if re.match(r'^CLÁUSULA\s+\d+[ªº]?\s*[-–—]\s*', frase, re.IGNORECASE):
            return "titulo_clausula"
        elif re.match(r'^SEÇÃO\s+[IVX]+\s*[-–—]', frase, re.IGNORECASE):
            return "titulo_secao"
        elif re.match(r'^[IVX]+\.\s+', frase):
            return "titulo_subsecao"
        elif re.match(r'^\d+\.\s+', frase):
            return "item_numerado"
        elif re.match(r'^[a-z]\)\s+', frase):
            return "item_letra"
        elif re.match(r'^[A-Z]\.\s+', frase):
            return "item_maiuscula"
        elif frase.isupper() and len(frase.strip()) > 10:
            return "titulo_destaque"
        elif "PÁGINA" in frase_upper or "PAGE" in frase_upper:
            return "numero_pagina"
        elif "VIGENTE" in frase_upper or "VERSÃO" in frase_upper:
            return "informacao_rodape"
        else:
            return "texto"
    
    def _gerar_contexto_frase(self, frase: str, estrutura: Dict[str, Any]) -> Optional[str]:
        """Gera contexto para uma frase."""
        if not self.config.incluir_contexto:
            return None
        
        contexto = []
        
        # Adicionar informação da cláusula atual
        clausula_atual = self._encontrar_clausula_atual_frase(frase, estrutura)
        if clausula_atual:
            contexto.append(f"Cláusula: {clausula_atual}")
        
        # Adicionar informação da seção atual
        secao_atual = self._encontrar_secao_atual_frase(frase, estrutura)
        if secao_atual:
            contexto.append(f"Seção: {secao_atual}")
        
        return " | ".join(contexto) if contexto else None
    
    def _encontrar_clausula_atual_frase(self, frase: str, estrutura: Dict[str, Any]) -> Optional[str]:
        """Encontra a cláusula atual baseada na frase."""
        for clausula in reversed(estrutura["clausulas"]):
            if clausula["texto"] in frase or frase in clausula["texto"]:
                return clausula["texto"]
        return None
    
    def _encontrar_secao_atual_frase(self, frase: str, estrutura: Dict[str, Any]) -> Optional[str]:
        """Encontra a seção atual baseada na frase."""
        for secao in reversed(estrutura["secoes"]):
            if secao["texto"] in frase or frase in secao["texto"]:
                return secao["texto"]
        return None
    
    def _gerar_contexto(self, elemento: Dict[str, Any], 
                        estrutura: Dict[str, Any]) -> Optional[str]:
        """Gera contexto para o segmento."""
        if not self.config.incluir_contexto:
            return None
        
        contexto = []
        
        # Adicionar informação da cláusula atual
        clausula_atual = self._encontrar_clausula_atual(elemento, estrutura)
        if clausula_atual:
            contexto.append(f"Cláusula: {clausula_atual}")
        
        # Adicionar informação da seção atual
        secao_atual = self._encontrar_secao_atual(elemento, estrutura)
        if secao_atual:
            contexto.append(f"Seção: {secao_atual}")
        
        return " | ".join(contexto) if contexto else None
    
    def _encontrar_clausula_atual(self, elemento: Dict[str, Any], 
                                  estrutura: Dict[str, Any]) -> Optional[str]:
        """Encontra a cláusula atual baseada na posição."""
        for clausula in reversed(estrutura["clausulas"]):
            if (clausula["pagina"] < elemento["pagina"] or 
                (clausula["pagina"] == elemento["pagina"] and 
                 clausula["posicao"] <= elemento["posicao"])):
                return clausula["texto"]
        return None
    
    def _encontrar_secao_atual(self, elemento: Dict[str, Any], 
                               estrutura: Dict[str, Any]) -> Optional[str]:
        """Encontra a seção atual baseada na posição."""
        for secao in reversed(estrutura["secoes"]):
            if (secao["pagina"] < elemento["pagina"] or 
                (secao["pagina"] == elemento["pagina"] and 
                 secao["posicao"] <= elemento["posicao"])):
                return secao["texto"]
        return None 