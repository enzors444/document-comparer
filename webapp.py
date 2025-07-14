import streamlit as st
import requests
from pathlib import Path
import json

API_URL = "http://localhost:8000/api"

st.set_page_config(page_title="Comparador Jurídico", layout="wide")
st.title("🔍 Comparador de Documentos Jurídicos Contratuais")

st.sidebar.header("Ações")
menu = st.sidebar.radio("Escolha uma ação:", ["Comparar PDFs", "Analisar PDF", "Resultados Recentes"]) 

if menu == "Comparar PDFs":
    st.header("Comparação entre dois documentos PDF")
    pdf1 = st.file_uploader("PDF 1", type="pdf", key="pdf1")
    pdf2 = st.file_uploader("PDF 2", type="pdf", key="pdf2")
    threshold = st.slider("Threshold de similaridade", 0.5, 1.0, 0.8, 0.01)
    min_segmento = st.number_input("Tamanho mínimo de segmento", 5, 100, 30)
    if st.button("Comparar", disabled=not (pdf1 and pdf2)):
        with st.spinner("Enviando arquivos e processando..."):
            if pdf1 and pdf2:  # Type guard
                files = {"pdf1": (pdf1.name, pdf1.getvalue(), "application/pdf"), "pdf2": (pdf2.name, pdf2.getvalue(), "application/pdf")}
                data = {"threshold": threshold, "min_segmento": min_segmento}
                resp = requests.post(f"{API_URL}/comparar", files=files, data=data)
            if resp.status_code == 200:
                result = resp.json()
                st.success("Comparação realizada!")
                st.session_state["last_result_id"] = result["id"]
                st.json(result["resultado"])
            else:
                st.error(f"Erro: {resp.text}")

elif menu == "Analisar PDF":
    st.header("Análise de um documento PDF")
    pdf = st.file_uploader("PDF para análise", type="pdf", key="pdf_analise")
    min_segmento = st.number_input("Tamanho mínimo de segmento", 5, 100, 30, key="min_seg_analise")
    if st.button("Analisar", disabled=not pdf):
        with st.spinner("Enviando arquivo e processando..."):
            if pdf:  # Type guard
                files = {"pdf": (pdf.name, pdf.getvalue(), "application/pdf")}
                data = {"min_segmento": min_segmento}
                resp = requests.post(f"{API_URL}/analisar", files=files, data=data)
            if resp.status_code == 200:
                result = resp.json()
                st.success("Análise realizada!")
                st.session_state["last_result_id"] = result["id"]
                st.json(result["documento"])
            else:
                st.error(f"Erro: {resp.text}")

elif menu == "Resultados Recentes":
    st.header("Resultados Recentes")
    import os
    # Listar todos os arquivos de resultados disponíveis
    resultados_dir = Path("resultados/api")
    ids_disponiveis = [f.stem for f in resultados_dir.glob("*.json")]
    if ids_disponiveis:
        selected_id = st.selectbox("Selecione um ID de resultado para ver segmentos alterados:", ids_disponiveis)
        if st.button("Ver segmentos alterados"):
            with st.spinner("Buscando segmentos alterados..."):
                resp = requests.get(f"{API_URL}/filtrar-alterados/{selected_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    st.success(f"Segmentos alterados do resultado {selected_id}:")
                    st.json(data)
                else:
                    st.error(f"Erro: {resp.text}")
    else:
        st.info("Nenhum resultado disponível para filtrar.")
    # Exibir resultado recente como antes
    if "last_result_id" in st.session_state:
        result_id = st.session_state["last_result_id"]
        st.write(f"Último resultado: {result_id}")
        if st.button("Ver resultado completo"):
            resp = requests.get(f"{API_URL}/resultado/{result_id}")
            if resp.status_code == 200:
                try:
                    data = json.loads(resp.json())
                except Exception:
                    data = resp.json()
                st.json(data)
            else:
                st.error(f"Erro: {resp.text}")

st.sidebar.markdown("---")
st.sidebar.info("Desenvolvido para análise jurídica precisa e eficiente.") 