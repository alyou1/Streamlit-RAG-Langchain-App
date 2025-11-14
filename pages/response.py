# === 2. TEMPS DE RÉPONSE (SECTION PRIORITAIRE) ===
st.subheader("⚡ Performance - Temps de réponse")

tab1, tab2, tab3 = st.tabs(["📈 Évolution", "📊 Distribution", "👥 Par utilisateur"])

with tab1:
    if response_time_by_day:
        df_response = pd.DataFrame(response_time_by_day, columns=['Date', 'Temps moyen (s)', 'Nombre réponses'])
        df_response['Date'] = pd.to_datetime(df_response['Date'])

        # Ajouter le jour de la semaine et formater la date
        df_response['Jour_semaine'] = df_response['Date'].dt.day_name(locale='fr_FR.UTF-8')
        df_response['Date_formatee'] = df_response['Date'].dt.strftime('%d/%m')

        # Créer l'axe X : "Jour JJ/MM"
        df_response['Label_X'] = df_response.apply(
            lambda row: f"{row['Date_formatee']}",
            axis=1
        )

        fig = go.Figure()

        # Ligne du temps de réponse
        fig.add_trace(go.Scatter(
            x=df_response['Label_X'],
            y=df_response['Temps moyen (s)'],
            mode='lines+markers',
            name='Temps de réponse',
            line=dict(color='#e74c3c', width=3),
            marker=dict(size=10, symbol='circle'),
            fill='tozeroy',
            fillcolor='rgba(231, 76, 60, 0.2)',
            hovertemplate='<b>%{customdata[0]}</b><br>Temps: %{y:.2f}s<br>Réponses: %{customdata[1]}<extra></extra>',
            customdata=df_response[['Date_formatee', 'Nombre réponses']].values
        ))

        # Ligne objectif (5 secondes)
        fig.add_trace(go.Scatter(
            x=df_response['Label_X'],
            y=[5] * len(df_response),
            mode='lines',
            name='Objectif (5s)',
            line=dict(color='#2ecc71', width=2, dash='dash'),
            hoverinfo='skip'
        ))

        fig.update_layout(
            height=450,
            xaxis=dict(
                title="Date",
                tickangle=-45,
                tickfont=dict(size=11)
            ),
            yaxis=dict(
                title="Temps de réponse moyen (secondes)",
                gridcolor='rgba(0,0,0,0.1)'
            ),
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            plot_bgcolor='white'
        )

        st.plotly_chart(fig, use_container_width=True)

        # Statistiques
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("⚡ Temps moyen global", f"{df_response['Temps moyen (s)'].mean():.2f}s")
        with col2:
            st.metric("📈 Jour le plus lent", f"{df_response['Temps moyen (s)'].max():.2f}s")
        with col3:
            st.metric("📉 Jour le plus rapide", f"{df_response['Temps moyen (s)'].min():.2f}s")
        with col4:
            # Tendance (comparaison derniers 7j vs 7j précédents)
            if len(df_response) >= 14:
                recent_avg = df_response.tail(7)['Temps moyen (s)'].mean()
                previous_avg = df_response.iloc[-14:-7]['Temps moyen (s)'].mean()
                trend = recent_avg - previous_avg
                trend_emoji = "📉" if trend < 0 else "📈"
                st.metric("📊 Tendance (7j)", f"{trend:+.2f}s", delta=f"{trend_emoji}")
            else:
                st.metric("📊 Total réponses", f"{df_response['Nombre réponses'].sum()}")
    else:
        st.info(
            "Aucune donnée de temps de réponse disponible. Posez quelques questions dans le chat pour générer des données.")

with tab2:
    if response_time_distribution:
        # Ordre des tranches
        order = ['< 3s', '3-5s', '5-10s', '10-15s', '> 15s']
        labels = [label for label in order if label in response_time_distribution]
        values = [response_time_distribution[label] for label in labels]

        # Couleurs par tranche
        colors_map = {
            '< 3s': '#2ecc71',
            '3-5s': '#3498db',
            '5-10s': '#f39c12',
            '10-15s': '#e67e22',
            '> 15s': '#e74c3c'
        }
        bar_colors = [colors_map.get(label, '#95a5a6') for label in labels]

        fig = go.Figure(data=[
            go.Bar(
                x=labels,
                y=values,
                marker=dict(
                    color=bar_colors,
                    line=dict(color='rgba(0,0,0,0.5)', width=2)
                ),
                text=values,
                textposition='outside',
                textfont=dict(size=14, weight='bold'),
                hovertemplate='<b>%{x}</b><br>Réponses: %{y}<extra></extra>'
            )
        ])

        fig.update_layout(
            height=400,
            xaxis_title="Temps de réponse",
            yaxis_title="Nombre de réponses",
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)

        # Pourcentage de réponses rapides
        total = sum(values)
        fast_responses = response_time_distribution.get('< 3s', 0) + response_time_distribution.get('3-5s', 0)
        fast_percentage = (fast_responses / total * 100) if total > 0 else 0

        if fast_percentage >= 80:
            st.success(f"🟢 Excellent ! {fast_percentage:.1f}% des réponses en moins de 5 secondes")
        elif fast_percentage >= 60:
            st.info(f"🟡 Bon. {fast_percentage:.1f}% des réponses en moins de 5 secondes")
        else:
            st.warning(f"🔴 À améliorer. Seulement {fast_percentage:.1f}% des réponses en moins de 5 secondes")
    else:
        st.info("Aucune donnée de distribution disponible")

with tab3:
    if response_time_by_user:
        st.caption(f"Temps de réponse moyen par utilisateur ({len(response_time_by_user)} utilisateurs)")

        cols = st.columns([2, 1.5, 1.5, 1.5, 1.5])
        cols[0].markdown("**👤 Matricule**")
        cols[1].markdown("**⚡ Temps moyen**")
        cols[2].markdown("**📊 Nb réponses**")
        cols[3].markdown("**📉 Min**")
        cols[4].markdown("**📈 Max**")

        st.divider()

        for user_data in response_time_by_user[:20]:
            cols = st.columns([2, 1.5, 1.5, 1.5, 1.5])
            cols[0].markdown(f"**{user_data[0]}**")

            avg_time = user_data[1]
            color = "🟢" if avg_time < 5 else "🟡" if avg_time < 10 else "🔴"
            cols[1].markdown(f"{color} {avg_time:.2f}s")

            cols[2].markdown(f"{user_data[2]}")
            cols[3].markdown(f"{user_data[3]:.2f}s")
            cols[4].markdown(f"{user_data[4]:.2f}s")
    else:
        st.info("Aucune donnée utilisateur disponible")
