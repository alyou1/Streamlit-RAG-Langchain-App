import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from get_stats import (
    # Anciennes fonctions
    get_feedback_stats, get_user_stats, get_conversation_stats,
    get_daily_activity, get_connected_users, get_all_feedbacks,
    # Nouvelles fonctions
    get_total_users, get_total_documents, get_documents_by_type,
    get_users_connected_now, get_users_connected_today, get_active_users_now,
    get_total_conversations, get_conversations_by_day, get_conversations_by_weekday,
    get_user_types
)
from auth import logout_user,create_users_table

create_users_table()

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
total_users = get_total_users()
total_documents = get_total_documents()
users_connected_now = get_users_connected_now()
total_conversations = get_total_conversations()
feedback_stats = get_feedback_stats()
user_stats = get_user_stats()
user_types = get_user_types()
documents_by_type = get_documents_by_type()
conversations_by_day = get_conversations_by_day()
conversations_by_weekday = get_conversations_by_weekday()

# === 1. MÉTRIQUES PRINCIPALES ===
st.subheader("📈 Métriques Principales")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("👥 Utilisateurs inscrits", total_users)
    st.caption(f"🟢 {users_connected_now} connectés maintenant")

with col2:
    st.metric("📄 Documents chargés", total_documents)

with col3:
    st.metric("💬 Conversations totales", total_conversations)

with col4:
    total_feedbacks = feedback_stats["positive"] + feedback_stats["negative"]
    satisfaction_rate = (feedback_stats["positive"] / total_feedbacks * 100) if total_feedbacks > 0 else 0
    st.metric("📊 Taux de satisfaction", f"{satisfaction_rate:.1f}%")
    delta = satisfaction_rate - 90
    st.caption(f"{'🟢' if delta >= 0 else '🔴'} Objectif: 90%")

st.divider()

# === 2. GRAPHIQUES PRINCIPAUX ===
col1, col2 = st.columns(2)

with col1:
    st.subheader("👥 Types d'utilisateurs")
    if user_types:
        fig = go.Figure(data=[go.Pie(
            labels=list(user_types.keys()),
            values=list(user_types.values()),
            hole=.4,
            marker=dict(colors=['#3498db', '#e74c3c', '#2ecc71', '#f39c12']),
            textinfo='label+percent+value',
            textfont_size=13
        )])
        fig.update_layout(
            height=350,
            showlegend=True,
            annotations=[dict(text=f'{total_users}', x=0.5, y=0.5,
                              font_size=24, showarrow=False)]
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucun utilisateur inscrit")

with col2:
    st.subheader("📄 Types de documents chargés")
    if documents_by_type:
        df_docs = pd.DataFrame(list(documents_by_type.items()), columns=['Type', 'Nombre'])
        fig = px.bar(
            df_docs, x='Type', y='Nombre',
            color='Type',
            color_discrete_map={'PDF': '#e74c3c', 'Excel': '#2ecc71', 'CSV': '#3498db', 'Autre': '#95a5a6'},
            text='Nombre'
        )
        fig.update_traces(texttemplate='%{text}', textposition='outside')
        fig.update_layout(height=350, showlegend=False, xaxis_title="", yaxis_title="Nombre de documents")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucun document chargé")

st.divider()

# === 3. ÉVOLUTION DES CONVERSATIONS ===
st.subheader("📈 Évolution des conversations")

tab1, tab2 = st.tabs(["📅 Par jour (30 derniers jours)", "📊 Moyenne par jour de la semaine"])

with tab1:
    if conversations_by_day:
        df_conv_day = pd.DataFrame(conversations_by_day, columns=['Date', 'Conversations', 'Jour'])
        df_conv_day['Date'] = pd.to_datetime(df_conv_day['Date'])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_conv_day['Date'],
            y=df_conv_day['Conversations'],
            mode='lines+markers',
            name='Conversations',
            line=dict(color='#3498db', width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(52, 152, 219, 0.2)',
            hovertemplate='<b>%{customdata}</b><br>Date: %{x|%d/%m/%Y}<br>Conversations: %{y}<extra></extra>',
            customdata=df_conv_day['Jour']
        ))

        fig.update_layout(
            height=400,
            xaxis_title="Date",
            yaxis_title="Nombre de conversations",
            hovermode='x unified',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        # Statistiques
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Moyenne/jour", f"{df_conv_day['Conversations'].mean():.1f}")
        with col2:
            st.metric("📈 Maximum", f"{df_conv_day['Conversations'].max()}")
        with col3:
            st.metric("📉 Minimum", f"{df_conv_day['Conversations'].min()}")
    else:
        st.info("Aucune donnée de conversation disponible")

with tab2:
    if conversations_by_weekday:
        df_weekday = pd.DataFrame(conversations_by_weekday, columns=['Jour', 'Moyenne'])

        # Ordre des jours
        jour_order = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        df_weekday['Jour'] = pd.Categorical(df_weekday['Jour'], categories=jour_order, ordered=True)
        df_weekday = df_weekday.sort_values('Jour')

        fig = px.bar(
            df_weekday, x='Jour', y='Moyenne',
            color='Moyenne',
            color_continuous_scale='Blues',
            text='Moyenne'
        )
        fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        fig.update_layout(
            height=400,
            xaxis_title="Jour de la semaine",
            yaxis_title="Moyenne de conversations",
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        # Jour le plus actif
        jour_max = df_weekday.loc[df_weekday['Moyenne'].idxmax(), 'Jour']
        st.success(
            f"🏆 Jour le plus actif : **{jour_max}** ({df_weekday['Moyenne'].max():.1f} conversations en moyenne)")
    else:
        st.info("Aucune donnée de conversation disponible")

st.divider()

# === 4. UTILISATEURS CONNECTÉS ===
st.subheader("👥 Utilisateurs connectés")

tab1, tab2 = st.tabs(["🟢 Connectés maintenant", "📅 Connectés aujourd'hui"])

with tab1:
    active_users = get_active_users_now()
    if active_users:
        st.caption(f"{len(active_users)} utilisateur(s) actuellement connecté(s)")

        cols = st.columns([2, 2, 2, 2])
        cols[0].markdown("**👤 Matricule**")
        cols[1].markdown("**📝 Nom**")
        cols[2].markdown("**🎭 Rôle**")
        cols[3].markdown("**🕐 Dernière activité**")

        st.divider()

        for user in active_users:
            cols = st.columns([2, 2, 2, 2])
            cols[0].markdown(f"**{user[0]}**")
            cols[1].markdown(f"{user[1]} {user[2]}")

            role_emoji = "👑" if user[3] == "admin" else "✏️" if "editeur" in user[3].lower() else "👤"
            cols[2].markdown(f"{role_emoji} {user[3]}")

            # user[5] = last_activity
            last_activity = datetime.strptime(user[5], "%Y-%m-%d %H:%M:%S")
            time_diff = datetime.now() - last_activity

            if time_diff.seconds < 300:
                cols[3].markdown(f"🟢 Il y a {time_diff.seconds // 60}min")
            elif time_diff.seconds < 3600:
                cols[3].markdown(f"🟡 Il y a {time_diff.seconds // 60}min")
            else:
                hours = time_diff.seconds // 3600
                cols[3].markdown(f"🟠 Il y a {hours}h")
    else:
        st.info("Aucun utilisateur actuellement connecté")

with tab2:
    users_today = get_users_connected_today()
    if users_today:
        st.caption(f"{len(users_today)} utilisateur(s) connecté(s) aujourd'hui")

        cols = st.columns([2, 2, 2, 2, 1])
        cols[0].markdown("**👤 Matricule**")
        cols[1].markdown("**📝 Nom**")
        cols[2].markdown("**🎭 Rôle**")
        cols[3].markdown("**🕐 Connexion**")
        cols[4].markdown("**🔴 Statut**")

        st.divider()

        for user in users_today:
            cols = st.columns([2, 2, 2, 2, 1])
            cols[0].markdown(f"**{user[0]}**")
            cols[1].markdown(f"{user[1]} {user[2]}")

            role_emoji = "👑" if user[3] == "admin" else "✏️" if "editeur" in user[3].lower() else "👤"
            cols[2].markdown(f"{role_emoji} {user[3]}")

            cols[3].markdown(user[4])

            # user[5] = is_active
            if user[5] == 1:
                cols[4].markdown("🟢 En ligne")
            else:
                cols[4].markdown("⚪ Déconnecté")
    else:
        st.info("Aucun utilisateur connecté aujourd'hui")

st.divider()

# === 5. STATISTIQUES PAR UTILISATEUR ===
st.subheader("👥 Statistiques par utilisateur")

if user_stats:
    df_users = pd.DataFrame(user_stats)
    df_users['total_feedbacks'] = df_users['positive_feedbacks'] + df_users['negative_feedbacks']
    df_users['satisfaction_rate'] = df_users.apply(
        lambda row: (row['positive_feedbacks'] / row['total_feedbacks'] * 100)
        if row['total_feedbacks'] > 0 else 0, axis=1
    )
    df_users['avg_questions_per_conv'] = (df_users['total_questions'] / df_users['total_conversations']).round(1)

    col1, col2 = st.columns([2, 2])
    with col1:
        sort_by = st.selectbox(
            "Trier par",
            ["Questions (↓)", "Conversations (↓)", "Satisfaction (↓)", "Dernière activité (↓)"]
        )
    with col2:
        min_questions = st.number_input("Questions minimum", min_value=0, value=0)

    df_filtered = df_users[df_users['total_questions'] >= min_questions].copy()

    if sort_by == "Questions (↓)":
        df_filtered = df_filtered.sort_values('total_questions', ascending=False)
    elif sort_by == "Conversations (↓)":
        df_filtered = df_filtered.sort_values('total_conversations', ascending=False)
    elif sort_by == "Satisfaction (↓)":
        df_filtered = df_filtered.sort_values('satisfaction_rate', ascending=False)
    else:
        df_filtered = df_filtered.sort_values('last_activity', ascending=False)

    st.caption(f"Affichage de {len(df_filtered)} utilisateur(s)")

    cols = st.columns([1.5, 1, 1, 1, 1.5, 1.5, 1.5])
    cols[0].markdown("**👤 Matricule**")
    cols[1].markdown("**❓ Questions**")
    cols[2].markdown("**💬 Conv.**")
    cols[3].markdown("**📊 Moy. Q/C**")
    cols[4].markdown("**👍/👎 Feedbacks**")
    cols[5].markdown("**📈 Satisfaction**")
    cols[6].markdown("**🕐 Dernière activité**")

    st.divider()

    for _, row in df_filtered.iterrows():
        cols = st.columns([1.5, 1, 1, 1, 1.5, 1.5, 1.5])
        cols[0].markdown(f"**{row['matricule']}**")
        cols[1].markdown(f"{row['total_questions']}")
        cols[2].markdown(f"{row['total_conversations']}")
        cols[3].markdown(f"{row['avg_questions_per_conv']}")
        cols[4].markdown(f"👍 {row['positive_feedbacks']} / 👎 {row['negative_feedbacks']}")

        sat_rate = row['satisfaction_rate']
        if row['total_feedbacks'] > 0:
            color = "🟢" if sat_rate >= 90 else "🟡" if sat_rate >= 50 else "🔴"
            cols[5].markdown(f"{color} {sat_rate:.1f}%")
        else:
            cols[5].markdown("⚪ N/A")

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

col1, col2, col3 = st.columns(3)

with col1:
    if user_stats:
        csv_users = pd.DataFrame(user_stats).to_csv(index=False)
        st.download_button(
            label="📥 Stats utilisateurs (CSV)",
            data=csv_users,
            file_name=f"user_stats_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

with col2:
    if all_feedbacks:
        csv_feedbacks = pd.DataFrame(all_feedbacks,
                                     columns=['Matricule', 'Conversation', 'Index', 'Type', 'Date']).to_csv(index=False)
        st.download_button(
            label="📥 Feedbacks (CSV)",
            data=csv_feedbacks,
            file_name=f"feedbacks_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

with col3:
    if conversations_by_day:
        csv_conv = pd.DataFrame(conversations_by_day, columns=['Date', 'Conversations', 'Jour']).to_csv(index=False)
        st.download_button(
            label="📥 Conversations (CSV)",
            data=csv_conv,
            file_name=f"conversations_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
