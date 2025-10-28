import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from get_stats import (get_feedback_stats, get_user_stats, get_conversation_stats,
                     get_daily_activity, get_connected_users, get_all_feedbacks)
from auth import logout_user

# --- Configuration de la page ---
st.set_page_config(
    page_title="Analytics - Dashboard Admin",
    page_icon="📊",
    layout="wide"
)

# --- Vérification login et rôle admin ---
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 Accès refusé. Veuillez vous connecter.")
    if st.button("🔑 Retour à la connexion"):
        st.switch_page("app.py")
    st.stop()

if st.session_state.role != "admin":
    st.error("🚫 Accès refusé. Cette page est réservée aux administrateurs.")
    st.stop()

with st.sidebar:
    if st.button("🔓 Logout"):
        logout_user()
        st.switch_page("app.py")

# --- En-tête ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("📊 Dashboard Analytics")
    st.caption("Vue d'ensemble de l'utilisation et des performances du chatbot")
with col2:
    st.markdown(f"""
    <div style='text-align: right; padding: 10px;'>
        <p style='margin: 0;'><strong>👤 {st.session_state.nom} {st.session_state.prenom}</strong></p>
        <p style='margin: 0; color: #666;'>ADMIN</p>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --- Récupération des données ---
feedback_stats = get_feedback_stats()
user_stats = get_user_stats()
conversation_stats = get_conversation_stats()
daily_activity = get_daily_activity()
connected_users = get_connected_users()

# === 1. MÉTRIQUES GLOBALES ===
st.subheader("📈 Métriques Globales")

col1, col2, col3, col4, col5 = st.columns(5)

total_feedbacks = feedback_stats["positive"] + feedback_stats["negative"]
satisfaction_rate = (feedback_stats["positive"] / total_feedbacks * 100) if total_feedbacks > 0 else 0

total_questions = sum(user["total_questions"] for user in user_stats)
total_conversations = sum(user["total_conversations"] for user in user_stats)
total_users = len(user_stats)
active_users_today = len([u for u in user_stats if u["last_activity"] and
                          u["last_activity"].startswith(datetime.now().strftime("%Y-%m-%d"))])

with col1:
    st.metric("👥 Utilisateurs totaux", total_users)
    st.caption(f"🟢 {active_users_today} actifs aujourd'hui")

with col2:
    st.metric("❓ Questions posées", f"{total_questions:,}")

with col3:
    st.metric("💬 Conversations", f"{total_conversations:,}")

with col4:
    st.metric("👍 Feedbacks positifs", feedback_stats["positive"])
    st.caption(f"👎 {feedback_stats['negative']} négatifs")

with col5:
    st.metric("📊 Taux de satisfaction", f"{satisfaction_rate:.1f}%")
    delta = satisfaction_rate - 90  # Objectif 90%
    st.caption(f"{'🟢' if delta >= 0 else '🔴'} Objectif: 90%")

st.divider()

# === 2. GRAPHIQUES ===
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Distribution des Feedbacks")

    if total_feedbacks > 0:
        fig = go.Figure(data=[go.Pie(
            labels=['Positifs 👍', 'Négatifs 👎'],
            values=[feedback_stats["positive"], feedback_stats["negative"]],
            hole=.4,
            marker=dict(colors=['#2ecc71', '#e74c3c']),
            textinfo='label+percent+value',
            textfont_size=14
        )])

        fig.update_layout(
            height=350,
            showlegend=True,
            annotations=[dict(text=f'{satisfaction_rate:.1f}%', x=0.5, y=0.5,
                              font_size=24, showarrow=False)]
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucun feedback enregistré pour le moment")

with col2:
    st.subheader("📈 Activité des 30 derniers jours")

    if daily_activity:
        df_activity = pd.DataFrame(daily_activity,
                                   columns=['Date', 'Questions', 'Réponses', 'Utilisateurs actifs'])
        df_activity['Date'] = pd.to_datetime(df_activity['Date'])
        df_activity = df_activity.sort_values('Date')

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df_activity['Date'],
            y=df_activity['Questions'],
            name='Questions',
            mode='lines+markers',
            line=dict(color='#3498db', width=2),
            fill='tonexty'
        ))

        fig.add_trace(go.Scatter(
            x=df_activity['Date'],
            y=df_activity['Utilisateurs actifs'],
            name='Utilisateurs actifs',
            mode='lines+markers',
            line=dict(color='#e67e22', width=2),
            yaxis='y2'
        ))

        fig.update_layout(
            height=350,
            yaxis=dict(title='Questions', side='left'),
            yaxis2=dict(title='Utilisateurs', overlaying='y', side='right'),
            hovermode='x unified',
            showlegend=True
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune activité enregistrée")

st.divider()

# === 3. STATISTIQUES PAR UTILISATEUR ===
st.subheader("👥 Statistiques par Utilisateur")

if user_stats:
    # Préparer les données
    df_users = pd.DataFrame(user_stats)

    # Calculer les métriques dérivées
    df_users['total_feedbacks'] = df_users['positive_feedbacks'] + df_users['negative_feedbacks']
    df_users['satisfaction_rate'] = df_users.apply(
        lambda row: (row['positive_feedbacks'] / row['total_feedbacks'] * 100)
        if row['total_feedbacks'] > 0 else 0, axis=1
    )
    df_users['avg_questions_per_conv'] = (df_users['total_questions'] /
                                          df_users['total_conversations']).round(1)

    # Filtres
    col1, col2 = st.columns([2, 2])
    with col1:
        sort_by = st.selectbox(
            "Trier par",
            ["Questions (↓)", "Conversations (↓)", "Satisfaction (↓)", "Dernière activité (↓)"]
        )

    with col2:
        min_questions = st.number_input("Questions minimum", min_value=0, value=0)

    # Appliquer les filtres
    df_filtered = df_users[df_users['total_questions'] >= min_questions].copy()

    # Tri
    if sort_by == "Questions (↓)":
        df_filtered = df_filtered.sort_values('total_questions', ascending=False)
    elif sort_by == "Conversations (↓)":
        df_filtered = df_filtered.sort_values('total_conversations', ascending=False)
    elif sort_by == "Satisfaction (↓)":
        df_filtered = df_filtered.sort_values('satisfaction_rate', ascending=False)
    else:
        df_filtered = df_filtered.sort_values('last_activity', ascending=False)

    # Affichage du tableau
    st.caption(f"Affichage de {len(df_filtered)} utilisateur(s)")

    # En-tête
    cols = st.columns([1.5, 1, 1, 1, 1.5, 1.5, 1.5])
    cols[0].markdown("**👤 Matricule**")
    cols[1].markdown("**❓ Questions**")
    cols[2].markdown("**💬 Conv.**")
    cols[3].markdown("**📊 Moy. Q/C**")
    cols[4].markdown("**👍/👎 Feedbacks**")
    cols[5].markdown("**📈 Satisfaction**")
    cols[6].markdown("**🕐 Dernière activité**")

    st.divider()

    # Lignes
    for _, row in df_filtered.iterrows():
        cols = st.columns([1.5, 1, 1, 1, 1.5, 1.5, 1.5])

        cols[0].markdown(f"**{row['matricule']}**")
        cols[1].markdown(f"{row['total_questions']}")
        cols[2].markdown(f"{row['total_conversations']}")
        cols[3].markdown(f"{row['avg_questions_per_conv']}")
        cols[4].markdown(f"👍 {row['positive_feedbacks']} / 👎 {row['negative_feedbacks']}")

        # Indicateur de satisfaction
        sat_rate = row['satisfaction_rate']
        if row['total_feedbacks'] > 0:
            color = "🟢" if sat_rate >= 90 else "🟡" if sat_rate >= 50 else "🔴"
            cols[5].markdown(f"{color} {sat_rate:.1f}%")
        else:
            cols[5].markdown("⚪ N/A")

        # Dernière activité
        if row['last_activity']:
            last_act = datetime.strptime(row['last_activity'], "%Y-%m-%d %H:%M:%S")
            time_diff = datetime.now() - last_act

            if time_diff.days == 0:
                cols[6].markdown("🟢 Aujourd'hui")
            elif time_diff.days == 1:
                cols[6].markdown("🟡 Hier")
            elif time_diff.days <= 7:
                cols[6].markdown(f"🟡 Il y a {time_diff.days}j")
            else:
                cols[6].markdown(f"🔴 Il y a {time_diff.days}j")
        else:
            cols[6].markdown("⚪ Jamais")
else:
    st.info("Aucun utilisateur n'a encore utilisé le chatbot")

st.divider()

# === 6. EXPORT DES DONNÉES ===
all_feedbacks = get_all_feedbacks()
st.subheader("💾 Export des données")

col1, col2= st.columns(2)

with col1:
    if user_stats:
        csv_users = pd.DataFrame(user_stats).to_csv(index=False)
        st.download_button(
            label="📥 Télécharger stats utilisateurs (CSV)",
            data=csv_users,
            file_name=f"user_stats_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

with col2:
    if all_feedbacks:
        csv_feedbacks = pd.DataFrame(all_feedbacks,
                                     columns=['Matricule', 'Conversation', 'Index', 'Type', 'Date']).to_csv(index=False)
        st.download_button(
            label="📥 Télécharger feedbacks (CSV)",
            data=csv_feedbacks,
            file_name=f"feedbacks_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
