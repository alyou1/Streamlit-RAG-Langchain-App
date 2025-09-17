from auth import register_user

# Création du premier admin
register_user("0001", "Super", "Admin", "admin@mail.com", "1234", "admin")
print("✅ Admin créé avec succès ! Matricule=0001, mot de passe=1234")
