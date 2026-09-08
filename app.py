# ==========================================
    # MENU 4: RELATÓRIOS GERENCIAIS (ATUALIZADO)
    # ==========================================
    elif menu == "4. Relatórios Gerenciais":
        st.header("📈 Relatórios Gerenciais e Inteligência")
        
        try:
            df_consumo = conn.read(worksheet="Consumo", ttl=0).dropna(how="all")
            if df_consumo.empty:
                st.warning("Não há dados de consumo registrados no sistema.")
            else:
                # Prepara as datas e horas
                df_consumo["Data"] = pd.to_datetime(df_consumo["Data"], errors='coerce')
                df_consumo["Mes_Ano"] = df_consumo["Data"].dt.strftime("%m/%Y")
                df_consumo["Ano"] = df_consumo["Data"].dt.strftime("%Y")
                
                # Se for dado antigo que não tinha hora, preenche com 08:00
                if "Hora" not in df_consumo.columns:
                    df_consumo["Hora"] = "08:00"
                df_consumo["Hora"] = df_consumo["Hora"].fillna("08:00")
                
                df_consumo["Faixa_Horario"] = df_consumo["Hora"].astype(str).str[:2] + "h"
                dias_semana = {0: '1-Segunda', 1: '2-Terça', 2: '3-Quarta', 3: '4-Quinta', 4: '5-Sexta', 5: '6-Sábado', 6: '7-Domingo'}
                df_consumo["Dia_Semana"] = df_consumo["Data"].dt.dayofweek.map(dias_semana)

                # Troca das Abas por Botões (Isso resolve o bug de atropelamento das variáveis)
                tipo_visao = st.radio("Selecione o tipo de visão:", ["Visão Diária", "Visão Mensal", "Visão Anual"], horizontal=True)
                st.markdown("---")
                
                df_filtrado = pd.DataFrame()
                titulo_filtro = ""

                if tipo_visao == "Visão Diária":
                    datas_disp = df_consumo["Data"].dt.strftime("%d/%m/%Y").unique()
                    data_sel = st.selectbox("Selecione o Dia:", datas_disp)
                    if data_sel:
                        df_filtrado = df_consumo[df_consumo["Data"].dt.strftime("%d/%m/%Y") == data_sel]
                        titulo_filtro = f"Resumo do Dia: {data_sel}"
                
                elif tipo_visao == "Visão Mensal":
                    meses_disp = df_consumo["Mes_Ano"].dropna().unique()
                    mes_sel = st.selectbox("Selecione o Mês:", meses_disp)
                    if mes_sel:
                        df_filtrado = df_consumo[df_consumo["Mes_Ano"] == mes_sel]
                        titulo_filtro = f"Resumo do Mês: {mes_sel}"
                
                elif tipo_visao == "Visão Anual":
                    anos_disp = df_consumo["Ano"].dropna().unique()
                    ano_sel = st.selectbox("Selecione o Ano:", anos_disp)
                    if ano_sel:
                        df_filtrado = df_consumo[df_consumo["Ano"] == ano_sel]
                        titulo_filtro = f"Resumo do Ano: {ano_sel}"

                if not df_filtrado.empty:
                    st.subheader(titulo_filtro)
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total de Cafés Servidos", len(df_filtrado))
                    col2.metric("Inclusos Consumidos", len(df_filtrado[df_filtrado["Incluso"] == "Sim"]))
                    col3.metric("Receita de Extras (Não Inclusos)", len(df_filtrado[df_filtrado["Incluso"] == "Não"]))
                    
                    st.markdown("---")
                    st.subheader("🔥 Mapa de Calor: Horários de Maior Consumo")
                    st.write("Descubra os picos de lotação do salão por horário e dia da semana neste período.")
                    
                    contagem_horas = df_filtrado.groupby(["Dia_Semana", "Faixa_Horario"]).size().reset_index(name="Cafés Servidos")
                    
                    if not contagem_horas.empty:
                        contagem_horas = contagem_horas.sort_values(["Dia_Semana", "Faixa_Horario"])
                        fig = px.density_heatmap(
                            contagem_horas, 
                            x="Faixa_Horario", 
                            y="Dia_Semana", 
                            z="Cafés Servidos",
                            color_continuous_scale="Oranges", 
                            text_auto=True
                        )
                        fig.update_layout(yaxis=dict(ticktext=[d.split("-")[1] for d in sorted(contagem_horas["Dia_Semana"].unique())], 
                                                     tickvals=sorted(contagem_horas["Dia_Semana"].unique())))
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Não há dados de horário suficientes para gerar o gráfico neste período.")

                    st.markdown("---")
                    st.markdown("**Exportar Dados Deste Período:**")
                    csv = df_filtrado.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Baixar Relatório em Excel/CSV",
                        data=csv,
                        file_name=f"Relatorio_Cafe_{titulo_filtro.replace(' ', '_').replace('/', '-')}.csv",
                        mime="text/csv",
                    )
        except Exception as e:
            st.error(f"Erro ao carregar relatórios. Detalhe: {e}")
