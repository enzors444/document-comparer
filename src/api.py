from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pathlib import Path
import shutil
import uuid
import os
import json

from .models import ConfiguracaoProcessamento, RespostaComparacao
from .processador import ProcessadorDocumentos

UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("resultados/api")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
RESULTS_DIR.mkdir(exist_ok=True, parents=True)

app = FastAPI(title="API de Comparação de Documentos Jurídicos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def save_upload(file: UploadFile, dest: Path) -> Path:
    with dest.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return dest

@app.post("/api/upload")
def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser PDF")
    dest = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    save_upload(file, dest)
    return {"filename": dest.name, "path": str(dest)}

@app.post("/api/comparar")
def comparar_pdfs(
    pdf1: UploadFile = File(...),
    pdf2: UploadFile = File(...),
    threshold: float = Form(0.8),
    min_segmento: int = Form(10),
):
    # Salvar arquivos
    path1 = UPLOAD_DIR / f"{uuid.uuid4()}_{pdf1.filename}"
    path2 = UPLOAD_DIR / f"{uuid.uuid4()}_{pdf2.filename}"
    save_upload(pdf1, path1)
    save_upload(pdf2, path2)
    # Processar
    config = ConfiguracaoProcessamento(
        threshold_similaridade=threshold,
        tamanho_minimo_segmento=min_segmento
    )
    processador = ProcessadorDocumentos(config)
    resultado = processador.processar_documentos(str(path1), str(path2))
    # Criar resposta apenas com comparações e estatísticas
    resposta = RespostaComparacao(
        comparacoes=resultado.comparacoes,
        estatisticas=resultado.estatisticas,
        data_comparacao=resultado.data_comparacao
    )
    
    # Salvar resultado (apenas comparações e estatísticas)
    result_id = str(uuid.uuid4())
    result_path = RESULTS_DIR / f"{result_id}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(resposta.model_dump_json(indent=2))
    
    return {"id": result_id, "resultado": resposta.model_dump()}

@app.post("/api/analisar")
def analisar_pdf(
    pdf: UploadFile = File(...),
    min_segmento: int = Form(10),
):
    path = UPLOAD_DIR / f"{uuid.uuid4()}_{pdf.filename}"
    save_upload(pdf, path)
    config = ConfiguracaoProcessamento(tamanho_minimo_segmento=min_segmento)
    processador = ProcessadorDocumentos(config)
    documento = processador.analisar_documento_unico(str(path))
    result_id = str(uuid.uuid4())
    result_path = RESULTS_DIR / f"{result_id}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(documento.model_dump_json(indent=2))
    return {"id": result_id, "documento": documento.model_dump(exclude={"segmentos"})}

@app.get("/api/resultado/{result_id}")
def get_resultado(result_id: str):
    result_path = RESULTS_DIR / f"{result_id}.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Resultado não encontrado")
    with open(result_path, "r", encoding="utf-8") as f:
        data = f.read()
    return JSONResponse(content=data)

@app.get("/api/filtrar-alterados/{result_id}")
def filtrar_alterados(result_id: str):
    """
    Retorna apenas os segmentos removidos, modificados ou adicionados de um resultado salvo.
    """
    result_path = RESULTS_DIR / f"{result_id}.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Resultado não encontrado")
    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    comparacoes = data.get("comparacoes", [])
    alterados = [
        c for c in comparacoes
        if c.get("tipo_diferenca") in ["removido", "modificado", "adicionado"]
    ]
    return {"id": result_id, "alterados": alterados}

@app.get("/api/lista_uploads")
def lista_uploads():
    files = [f.name for f in UPLOAD_DIR.glob("*.pdf")]
    return {"arquivos": files}

@app.get("/api/download/{filename}")
def download_pdf(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(str(file_path), media_type="application/pdf", filename=filename) 