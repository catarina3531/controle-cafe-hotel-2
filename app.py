import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# Configuração da Página
st.set_page_config(page_title="Controle de Café da Manhã", layout="wide")

# Conectando com o Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Variáveis de Sessão
if "logado" not in st.session_state:
    st.session_state["logado"] = False
if "usuario_logado" not in st.session_state:
    st.session_state["usuario_logado"] = ""

# --- TELA DE LOGIN DINÂMICA ---
def tela_login():
    st.title("☕ Controle de Café da Manhã")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            usuario = st.text_input("Usuário").strip()
            senha = st.text_input("Senha", type="password").strip()
            submit = st.form_submit_button("Entrar no Sistema", use_container_width=True)
            
            if submit:
                try:
                    df_usuarios = conn.read(worksheet="Usuarios", ttl=0).dropna(how="all")
                    usuario_valido = df_usuarios[(df_usuarios["Usuario"].astype(str) == usuario) & (df_usuarios["Senha"].astype(str) == senha)]
                    
                    if not usuario_valido.empty:
                        st.session_state["logado"] = True
                        st.session_state["usuario_logado"] = usuario
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")
                except Exception as e:
                    st.warning("⚠️ Aba 'Usuarios' não encontrada na planilha. Login de emergência ativado.")
                    if usuario == "admin" and senha == "123":
                        st.session_state["logado"] = True
                        st.session_state["usuario_logado"] = "admin (Emergência)"
                        st.rerun()

# --- TELA PRINCIPAL ---
def tela_principal():
    st.sidebar.title(f"Olá, {st.session_state['usuario_logado']}")
    st.sidebar.markdown("---")
    
    data_operacao = st.sidebar.date_input("📅 Data de Operação", datetime.today())
    data_str = data_operacao.strftime("%Y-%m-%d")
    
    try:
        df_controle = conn.read(worksheet="Controle_Dias", ttl=0).dropna(how="all")
        dia_encerrado = data_str in df_controle["Data"].astype(str).values
    except:
        df_controle = pd.DataFrame(columns=["Data", "Status"])
        dia_encerrado = False

    st.sidebar.markdown("---")
    menu = st.sidebar.radio("Navegação", [
        "1. Abertura do Dia (PDF)", 
        "2. Portaria do Café", 
        "3. Dashboard Diário", 
        "4. Relatórios Gerenciais",
        "5. Trocar Senha"
    ])
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    # ==========================================
    # MENU 1: UPLOAD DO PDF
    # ==========================================
    if menu == "1. Abertura do Dia (PDF)":
        st.header(f"📂 Abertura do Dia ({data_operacao.strftime('%d/%m/%Y')})")
        
        if dia_encerrado:
            st.error("🔒 Este dia já foi encerrado. Não é possível alterar ou inserir novos relatórios.")
        else:
            try:
                df_prev_check = conn.read(worksheet="Previsao", ttl=0).dropna(how="all")
                relatorio_ja_inserido = data_str in df_prev_check["Data"].astype(str).values
            except:
                relatorio_ja_inserido = False

            if relatorio_ja_inserido:
                st.success("✅ O relatório de hóspedes para esta data já foi inserido. A portaria está liberada.")
            else:
                st.write("Suba o arquivo PDF do Opera para carregar a lista de hóspedes do dia.")
                arquivo_pdf = st.file_uploader("Relatório de Hóspedes (PDF)", type=["pdf"])
                
                if arquivo_pdf is not None:
                    with st.spinner('Extraindo dados do PDF...'):
                        padrao = re.compile(r"^(.*?)\s+(\d{3,5})\s+(\d+)\s+(\d+)\s+(?:(Included)\s+)?([YN])\s+([A-Z0-9]+)\s+(\d{2}-[A-Z]{3}-\d{2})\s+(\d{2}-[A-Z]{3}-\d{2})(?:\s+(.*))?$")
                        linhas_extraidas = []
                        
                        with pdfplumber.open(arquivo_pdf) as pdf:
                            for pagina in pdf.pages:
                                texto = pagina.extract_text()
                                if texto:
                                    for linha in texto.split('\n'):
                                        match = padrao.match(linha.strip())
                                        if match:
                                            linhas_extraidas.append({
                                                "Data": data_str,
                                                "Hospede": match.group(1),
                                                "Quarto": match.group(2),
                                                "Adultos": int(match.group(3)),
                                                "Criancas": int(match.group(4)),
                                                "Incluso": "Sim" if match.group(5) == "Included" else "Não"
                                            })
                        
                        df_pdf = pd.DataFrame(linhas_extraidas)
                        
                    if not df_pdf.empty:
                        st.success(f"Sucesso! {len(df_pdf)} apartamentos encontrados no PDF.")
                        st.dataframe(df_pdf, use_container_width=True)
                        
                        if st.button("Gravar Previsão no Banco de Dados", type="primary"):
                            try:
                                df_previsao_atual = conn.read(worksheet="Previsao", ttl=0).dropna(how="all")
                                df_previsao_atual = df_previsao_atual[df_previsao_atual["Data"] != data_str]
                                df_atualizado = pd.concat([df_previsao_atual, df_pdf], ignore_index=True)
                            except:
                                df_atualizado = df_pdf
                                
                            conn.update(worksheet="Previsao", data=df_atualizado)
                            st.success("Dados salvos no Google Sheets! A Portaria já pode iniciar.")
                            st.rerun()
                    else:
                        st.error("Nenhum hóspede encontrado. Verifique se é o PDF correto.")

    # ==========================================
    # MENU 2: LANÇAR CONSUMO
    # ==========================================
    elif menu == "2. Portaria do Café":
        st.header(f"☕ Portaria - {data_operacao.strftime('%d/%m/%Y')}")
        
        if dia_encerrado:
            st.error("🔒 Este dia já foi encerrado. A portaria está bloqueada para novos lançamentos nesta data.")
        else:
            aba1, aba2 = st.tabs(["🏨 Lançar Hóspedes (Lista)", "🚶 Lançar Passantes (Avulsos)"])
            
            # --- ABA 1: HÓSPEDES REGULARES ---
            with aba1:
                try:
                    df_previsao = conn.read(worksheet="Previsao", ttl=0).dropna(how="all")
                    df_previsao = df_previsao[df_previsao["Data"] == data_str]
                except:
                    st.warning("Erro ao ler o banco de dados de Previsão.")
                    df_previsao = pd.DataFrame()

                if df_previsao.empty:
                    st.warning("Nenhuma previsão carregada para esta data. Faça o Upload do PDF primeiro.")
                else:
                    busca = st.text_input("🔍 Digite o número do Quarto ou Nome/Sobrenome do Hóspede:")
                    
                    if busca:
                        busca_limpa = busca.strip().lower()
                        df_previsao["Quarto_Limpo"] = df_previsao["Quarto"].astype(str).str.lstrip("0").str.replace(".0", "", regex=False)
                        
                        condicao_quarto = df_previsao["Quarto_Limpo"] == busca_limpa.lstrip("0")
                        condicao_nome = df_previsao["Hospede"].astype(str).str.lower().str.contains(busca_limpa, na=False)
                        
                        hospedes_encontrados = df_previsao[condicao_quarto | condicao_nome]
                        
                        if hospedes_encontrados.empty:
                            st.error(f"Nenhum hóspede encontrado para '{busca}' hoje.")
                        else:
                            st.subheader("Hóspedes Encontrados")
                            
                            with st.form("form_busca"):
                                consumos_pendentes = []
                                
                                for index, row in hospedes_encontrados.iterrows():
                                    nome = row["Hospede"]
                                    quarto_real = row["Quarto"]
                                    incluso = row["Incluso"]
                                    prev_adt = int(row["Adultos"])
                                    prev_chd = int(row["Criancas"])
                                    
                                    marcador = "✅ INCLUSO" if incluso == "Sim" else "❌ NÃO INCLUSO (Cobrar Extras)"
                                    
                                    st.markdown(f"**Quarto: {quarto_real}** | **Hóspede:** {nome} | **Reserva:** {prev_adt} Adulto(s), {prev_chd} Criança(s) | {marcador}")
                                    
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        qtd_adultos = st.number_input(f"Adultos ({nome})", min_value=0, max_value=10, value=0, key=f"adt_{index}")
                                    with col2:
                                        qtd_chd_0_6 = st.number_input(f"Crianças 0-6 anos", min_value=0, max_value=10, value=0, key=f"chd1_{index}")
                                    with col3:
                                        qtd_chd_7_11 = st.number_input(f"Crianças 7-11 anos", min_value=0, max_value=10, value=0, key=f"chd2_{index}")
                                        
                                    consumos_pendentes.append({
                                        "Quarto": quarto_real,
                                        "Hospede": nome,
                                        "Incluso": incluso,
                                        "Adulto": qtd_adultos,
                                        "Criança 0 a 6 anos": qtd_chd_0_6,
                                        "Criança 7 a 11 anos": qtd_chd_7_11
                                    })
                                    st.markdown("---")
                                
                                submit_consumo = st.form_submit_button("Registrar Entradas Selecionadas", type="primary", use_container_width=True)
                                
                                if submit_consumo:
                                    linhas_para_inserir = []
                                    for item in consumos_pendentes:
                                        categorias = ["Adulto", "Criança 0 a 6 anos", "Criança 7 a 11 anos"]
                                        for cat in categorias:
                                            for _ in range(item[cat]):
                                                linhas_para_inserir.append({
                                                    "Data": data_str,
                                                    "Quarto": item["Quarto"],
                                                    "Hospede": item["Hospede"],
                                                    "Categoria": cat,
                                                    "Incluso": item["Incluso"],
                                                    "Registrado_Por": st.session_state["usuario_logado"]
                                                })
                                    
                                    if linhas_para_inserir:
                                        df_novos_consumos = pd.DataFrame(linhas_para_inserir)
                                        try:
                                            df_consumo_atual = conn.read(worksheet="Consumo", ttl=0).dropna(how="all")
                                            df_atualizado = pd.concat([df_consumo_atual, df_novos_consumos], ignore_index=True)
                                        except:
                                            df_atualizado = df_novos_consumos
                                            
                                        conn.update(worksheet="Consumo", data=df_atualizado)
                                        st.success(f"{len(linhas_para_inserir)} café(s) registrado(s) com sucesso!")
                                    else:
                                        st.warning("Insira pelo menos 1 hóspede para registrar.")
            
            # --- ABA 2: PASSANTES AVULSOS ---
            with aba2:
                st.subheader("Registro de Passantes (Avulsos)")
                st.info("Passantes serão registrados sempre como NÃO INCLUSOS (Extras).")
                
                with st.form("form_passante"):
                    nome_passante = st.text_input("Nome do Responsável (Opcional):", value="Passante")
                    
                    col_p1, col_p2, col_p3 = st.columns(3)
                    with col_p1:
                        pass_adt = st.number_input("Qtd Adultos", min_value=0, max_value=20, value=1)
                    with col_p2:
                        pass_chd_0_6 = st.number_input("Qtd Crianças 0-6", min_value=0, max_value=20, value=0)
                    with col_p3:
                        pass_chd_7_11 = st.number_input("Qtd Crianças 7-11", min_value=0, max_value=20, value=0)
                        
                    submit_passante = st.form_submit_button("Registrar Passantes", type="primary", use_container_width=True)
                    
                    if submit_passante:
                        linhas_passantes = []
                        quantidades = {
                            "Adulto": pass_adt,
                            "Criança 0 a 6 anos": pass_chd_0_6,
                            "Criança 7 a 11 anos": pass_chd_7_11
                        }
                        
                        for cat, qtd in quantidades.items():
                            for _ in range(qtd):
                                linhas_passantes.append({
                                    "Data": data_str,
                                    "Quarto": "Passante",
                                    "Hospede": nome_passante,
                                    "Categoria": cat,
                                    "Incluso": "Não",
                                    "Registrado_Por": st.session_state["usuario_logado"]
                                })
                        
                        if linhas_passantes:
                            df_novos_passantes = pd.DataFrame(linhas_passantes)
                            try:
                                df_consumo_atual = conn.read(worksheet="Consumo", ttl=0).dropna(how="all")
                                df_atualizado = pd.concat([df_consumo_atual, df_novos_passantes], ignore_index=True)
                            except:
                                df_atualizado = df_novos_passantes
                                
                            conn.update(worksheet="Consumo", data=df_atualizado)
                            st.success(f"{len(linhas_passantes)} passante(s) registrado(s) com sucesso!")
                        else:
                            st.warning("Insira pelo menos 1 passante para registrar.")

    # ==========================================
    # MENU 3: DASHBOARD DIÁRIO
    # ==========================================
    elif menu == "3. Dashboard Diário":
        st.header(f"📊 Dashboard - {data_operacao.strftime('%d/%m/%Y')}")
        
        try:
            df_previsao = conn.read(worksheet="Previsao", ttl=0).dropna(how="all")
            df_consumo = conn.read(worksheet="Consumo", ttl=0).dropna(how="all")
            
            df_prev_hoje = df_previsao[df_previsao["Data"] == data_str] if not df_previsao.empty else pd.DataFrame()
            df_cons_hoje = df_consumo[df_consumo["Data"] == data_str] if not df_consumo.empty else pd.DataFrame()
            
            # --- CÁLCULOS DE PREVISÃO DETALHADA ---
            if not df_prev_hoje.empty:
                df_prev_incluso = df_prev_hoje[df_prev_hoje["Incluso"] == "Sim"]
                df_prev_nao_incluso = df_prev_hoje[df_prev_hoje["Incluso"] == "Não"]
                
                prev_total_incluso = df_prev_incluso["Adultos"].sum() + df_prev_incluso["Criancas"].sum()
                prev_total_nao_incluso = df_prev_nao_incluso["Adultos"].sum() + df_prev_nao_incluso["Criancas"].sum()
            else:
                prev_total_incluso = 0
                prev_total_nao_incluso = 0
                
            total_previsto = prev_total_incluso + prev_total_nao_incluso
            
            # --- CÁLCULOS DE CONSUMO ---
            cons_total = len(df_cons_hoje)
            cons_inclusos = len(df_cons_hoje[df_cons_hoje["Incluso"] == "Sim"]) if not df_cons_hoje.empty else 0
            cons_extras = len(df_cons_hoje[df_cons_hoje["Incluso"] == "Não"]) if not df_cons_hoje.empty else 0
            
            cons_adt = len(df_cons_hoje[df_cons_hoje["Categoria"] == "Adulto"]) if not df_cons_hoje.empty else 0
            cons_chd_0_6 = len(df_cons_hoje[df_cons_hoje["Categoria"] == "Criança 0 a 6 anos"]) if not df_cons_hoje.empty else 0
            cons_chd_7_11 = len(df_cons_hoje[df_cons_hoje["Categoria"] == "Criança 7 a 11 anos"]) if not df_cons_hoje.empty else 0

            # --- CÁLCULOS DE FALTANTES ---
            falta_incluso = max(0, prev_total_incluso - cons_inclusos)
            falta_nao_incluso = max(0, prev_total_nao_incluso - cons_extras)

            # --- EXIBIÇÃO DASHBOARD ---
            st.subheader("Balanço de Hóspedes (Previsão vs Realizado)")
            col1, col2, col3 = st.columns(3)
            
            # Inclusos
            with col1:
                st.markdown("### 🟢 Inclusos")
                st.metric("Total Previsto", prev_total_incluso)
                st.metric("Consumidos", cons_inclusos)
                st.metric("Falta Descer", falta_incluso)
            
            # Não Inclusos (Extras da lista)
            with col2:
                st.markdown("### 🔴 Extras / Não Inclusos")
                st.metric("Total Previsto", prev_total_nao_incluso)
                st.metric("Consumidos (Inclui Passantes)", cons_extras)
                st.metric("Falta Descer (Da Lista)", falta_nao_incluso)
                
            # Totais Gerais
            with col3:
                st.markdown("### 📊 Total Geral")
                st.metric("Previsão Total", total_previsto)
                st.metric("Consumo Total", cons_total)
            
            st.markdown("---")
            st.subheader("Consumo por Categoria")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Adultos", cons_adt)
            col_b.metric("Crianças (0 a 6 anos)", cons_chd_0_6)
            col_c.metric("Crianças (7 a 11 anos)", cons_chd_7_11)
            
            st.markdown("---")
            st.subheader("Lista de Entradas do Dia")
            if not df_cons_hoje.empty:
                st.dataframe(df_cons_hoje, use_container_width=True)
            else:
                st.info("Nenhum consumo registrado hoje ainda.")
                
            # BOTÃO DE ENCERRAR O DIA
            st.markdown("---")
            if dia_encerrado:
                st.success("🔒 Este dia foi encerrado com sucesso. Nenhuma alteração pode ser feita.")
            else:
                st.warning("⚠️ Ao encerrar o dia, a portaria e o upload de arquivos serão bloqueados para esta data.")
                if st.button("🔴 Encerrar Dia", type="primary"):
                    novo_status = pd.DataFrame([{"Data": data_str, "Status": "Encerrado"}])
                    df_atualizado_ctrl = pd.concat([df_controle, novo_status], ignore_index=True)
                    conn.update(worksheet="Controle_Dias", data=df_atualizado_ctrl)
                    st.success("Dia encerrado com sucesso! Recarregando...")
                    st.rerun()
                    
        except Exception as e:
            st.error("Erro ao carregar Dashboard. O banco de dados pode estar vazio.")

    # ==========================================
    # MENU 4: RELATÓRIOS GERENCIAIS
    # ==========================================
    elif menu == "4. Relatórios Gerenciais":
        st.header("📈 Relatório Mensal / Consolidado")
        
        try:
            df_consumo = conn.read(worksheet="Consumo", ttl=0).dropna(how="all")
            if df_consumo.empty:
                st.warning("Não há dados de consumo registrados no sistema.")
            else:
                df_consumo["Data"] = pd.to_datetime(df_consumo["Data"])
                df_consumo["Mes_Ano"] = df_consumo["Data"].dt.strftime("%m/%Y")
                
                meses_disponiveis = df_consumo["Mes_Ano"].unique()
                mes_selecionado = st.selectbox("Selecione o Mês para Análise:", meses_disponiveis)
                
                df_mes = df_consumo[df_consumo["Mes_Ano"] == mes_selecionado]
                
                st.subheader(f"Resumo de {mes_selecionado}")
                col1, col2 = st.columns(2)
                col1.metric("Total de Cafés Servidos", len(df_mes))
                col2.metric("Receita de Extras (Cafés Não Inclusos)", len(df_mes[df_mes["Incluso"] == "Não"]))
                
                st.markdown("**Consolidado por Categoria:**")
                resumo_categoria = df_mes["Categoria"].value_counts().reset_index()
                resumo_categoria.columns = ["Categoria", "Quantidade"]
                st.table(resumo_categoria)
                
                st.markdown("**Exportar Dados:**")
                csv = df_mes.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Baixar Relatório em Excel/CSV",
                    data=csv,
                    file_name=f"Relatorio_Cafe_{mes_selecionado.replace('/','-')}.csv",
                    mime="text/csv",
                )
        except Exception as e:
            st.error(f"Erro ao gerar relatórios.")

    # ==========================================
    # MENU 5: TROCAR SENHA
    # ==========================================
    elif menu == "5. Trocar Senha":
        st.header("🔑 Trocar Senha de Acesso")
        
        if st.session_state["usuario_logado"] == "admin (Emergência)":
            st.warning("⚠️ O login de emergência não pode alterar a senha por aqui. Acesse a planilha do Google e crie a aba 'Usuarios'.")
        else:
            with st.form("form_troca_senha"):
                st.write(f"Alterando senha do usuário: **{st.session_state['usuario_logado']}**")
                
                senha_atual = st.text_input("Senha Atual", type="password")
                nova_senha = st.text_input("Nova Senha", type="password")
                confirma_senha = st.text_input("Confirme a Nova Senha", type="password")
                
                submit_senha = st.form_submit_button("Atualizar Senha", type="primary")
                
                if submit_senha:
                    if nova_senha != confirma_senha:
                        st.error("As novas senhas digitadas não coincidem. Tente novamente.")
                    elif len(nova_senha) < 4:
                        st.error("A nova senha deve ter no mínimo 4 caracteres.")
                    else:
                        try:
                            # Carrega a tabela de usuários
                            df_usuarios = conn.read(worksheet="Usuarios", ttl=0).dropna(how="all")
                            usuario_logado = st.session_state["usuario_logado"]
                            
                            # Encontra a linha do usuário logado
                            filtro_usuario = df_usuarios["Usuario"].astype(str) == usuario_logado
                            senha_salva = str(df_usuarios.loc[filtro_usuario, "Senha"].values[0])
                            
                            if senha_atual != senha_salva:
                                st.error("A senha atual está incorreta.")
                            else:
                                # Atualiza a senha na tabela
                                df_usuarios.loc[filtro_usuario, "Senha"] = nova_senha
                                
                                # Grava na planilha do Google
                                conn.update(worksheet="Usuarios", data=df_usuarios)
                                st.success("Senha alterada com sucesso! Na próxima vez, utilize a sua nova senha.")
                        except Exception as e:
                            st.error("Erro ao alterar a senha. Verifique a planilha.")

if not st.session_state["logado"]:
    tela_login()
else:
    tela_principal()
