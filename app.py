import streamlit as st
from pymongo import MongoClient
from datetime import datetime, timedelta, date, time
import streamlit_authenticator as stauth

import yaml
from yaml.loader import SafeLoader

# YAML-Konfiguration laden
with open('credentials.yaml') as file:
    config = yaml.load(file, Loader=yaml.SafeLoader)

# Assuming your passwords in the YAML are plain text, hash them here
hashed_passwords = stauth.Hasher([config['credentials']['usernames']['admin']['password']]).generate()

# Authenticator initialisieren
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# Authentifizierung
name, authentication_status, username = authenticator.login("main", "Login")


# MongoDB Setup
# client = MongoClient("mongodb://localhost:27017/")


client = MongoClient("mongodb+srv://bvsb:admin@database.9f7hc0i.mongodb.net/")
db = client.bvsb
members_collection = db.members


# Funktion zum Hinzufügen eines neuen Mitglieds
def add_member(name, tv_name, price, createdAt):
    
    # Kombiniere das Datum (createdAt) mit der Uhrzeit (Mitternacht) zu einem datetime-Objekt
    createdAt_datetime = datetime.combine(createdAt, time.min)
    members_collection.insert_one({
        "name": name,
        "tv_name": tv_name,
        "price": price,
        "createdAt": createdAt_datetime,
        "recurring": createdAt_datetime + timedelta(days=30)
    })

def update_member_data(member_id, name, tv_name, price, createdAt, recurring):
    createdAt_datetime = datetime.combine(createdAt, time.min)
    recurring_datetime = datetime.combine(recurring, time.min)
    members_collection.update_one(
        {'_id': member_id},
        {'$set': {
            'name': name,
            'tv_name': tv_name,
            'price': price,
            'createdAt': createdAt_datetime,
            'recurring': recurring_datetime
        }}
    )

def delete_member(member_id):
    members_collection.delete_one({'_id': member_id})

# Funktion zum Aktualisieren des recurring Datums für alle Mitglieder
def update_recurrings():
    today = datetime.now()
    for member in members_collection.find({"recurring": {"$lt": today}}):
        new_recurring = member["recurring"] + timedelta(days=30)
        members_collection.update_one({"_id": member["_id"]}, {"$set": {"recurring": new_recurring}})

# Funktion zum Hervorheben fälliger Mitglieder
def mark_due():
    today = datetime.now()
    members_collection.update_many({"recurring": {"$lt": today}}, {"$set": {"due": True}})


def list_members(due_status, search_query=""):
    today = datetime.now()
    if due_status:
        st.subheader("Beitrag fällig")
        # Für fällige Mitglieder bleibt die Sortierung unverändert (keine Sortierung notwendig).
        query_filter = {"recurring": {"$lt": today}}
    else:
        st.subheader("Restliche Mitglieder")
        # Sortiere nicht fällige Mitglieder nach dem 'recurring' Datum aufsteigend.
        query_filter = {"recurring": {"$gte": today}}

    if search_query:
        query_filter["name"] = {"$regex": search_query, "$options": "i"}  # Case-insensitive Suche

    # Unterscheide die Sortierung basierend auf dem due_status
    if due_status:
        members = members_collection.find(query_filter)
    else:
        members = members_collection.find(query_filter).sort("recurring", 1)  # 1 für aufsteigende Sortierung


    for member in members:
        formatted_price = f"{member['price']:.2f}€"
        formatted_recurring = member['recurring'].strftime('%d.%m.%y')
        
        # Unterscheidung zwischen fälligen und nicht fälligen Mitgliedern
        if due_status:
            # Berechne, wie viele Tage das Mitglied überfällig ist
            days_overdue = (today - member['recurring']).days
            overdue_text = f"{days_overdue} Tage überfällig"
            expander_header = f"{formatted_price} | ({overdue_text}) - {member['name']}"
        else:
            # Berechne, wie viele Tage noch verbleiben bis zur nächsten Fälligkeit
            days_remaining = (member['recurring'] - today).days
            remaining_text = f"{days_remaining} Tage bis fällig"
            expander_header = f"{formatted_price} | ({remaining_text}) - {member['name']}"
        
        with st.expander(expander_header):
            with st.form(key=f"form_{member['_id']}"):
                name = st.text_input("Name", value=member['name'], key=f"name_{member['_id']}")
                tv_name = st.text_input("Tradingview Name", value=member['tv_name'], key=f"tv_{member['_id']}")
                price = st.number_input("Beitrag", value=float(member['price']), format="%f", key=f"price_{member['_id']}")
                createdAt = st.date_input("Erstellungsdatum", value=member['createdAt'], key=f"createdAt_{member['_id']}")
                recurring = st.date_input("Recurring Datum", value=member['recurring'], key=f"recurring_{member['_id']}")
                if st.form_submit_button("Änderungen speichern"):
                    update_member_data(member['_id'], name, tv_name, price, createdAt, recurring)
                    st.success("Mitglied aktualisiert")
                    st.rerun()

            if st.button("Mitglied löschen", key=f"delete_{member['_id']}"):
                delete_member(member['_id'])
                st.success(f"{member['name']} wurde erfolgreich gelöscht.")
                st.rerun()



        if due_status:
            if st.button(f"Zahlung für {member['name']} bestätigen", key=f"pay_{member['_id']}"):
                new_recurring = member["recurring"] + timedelta(days=30)
                members_collection.update_one({'_id': member['_id']}, {'$set': {'recurring': new_recurring, 'due': False}})
                st.success(f"Zahlung bestätigt und Recurring-Datum aktualisiert für {member['name']}")
                st.rerun()










# Start der App
def app():

    st.title("Mitgliederverwaltung")

    # Neues Mitglied Button
    if 'show_form' not in st.session_state:
        st.session_state.show_form = False  # Initialer Zustand des Formulars
        st.rerun()


    if st.button('Neues Mitglied hinzufügen' if not st.session_state.show_form else 'Formular schließen'):
        st.session_state.show_form = not st.session_state.show_form
        st.rerun()

    if st.session_state.show_form:
        with st.form("member_form"):
            name = st.text_input("Name")
            tv_name = st.text_input("Tradingview Name")
            price = st.number_input("Beitrag", format="%f", value=159.99)
            createdAt = st.date_input("Erstellungsdatum", value=datetime.now())
            submit = st.form_submit_button("Mitglied erstellen")

            if submit:
                if not name or not tv_name or price <= 0:
                    st.error("Bitte fülle alle Felder korrekt aus.")
                else:
                    add_member(name, tv_name, price, createdAt)
                    st.success("Mitglied erfolgreich hinzugefügt.")
                    st.session_state.show_form = False  # Formular nach dem Hinzufügen schließen




    # Optional: Regelmäßiges Update der Recurrings
    # update_recurrings()

    # Anzeige fälliger Mitglieder
    # st.subheader("Due")
    # due_members = members_collection.find({"due": True})
    # for member in due_members:
    #     st.write(f"{member['name']} - {member['recurring'].strftime('%Y-%m-%d')}")

    # # Anzeige aller Mitglieder
    # st.subheader("Alle Mitglieder")
    # all_members = members_collection.find({})
    # for member in all_members:
    #     st.write(f"{member['name']} - {member['recurring'].strftime('%Y-%m-%d')} - {member['price']}")
           
    st.divider()         
    search_query = st.text_input("Mitglied suchen")

    st.divider()

    list_members(due_status=True, search_query=search_query)  # Fällige Mitglieder
    list_members(due_status=False, search_query=search_query)  # Nicht fällige Mitglieder

# App starten, wenn Authentifizierung erfolgreich
if __name__ == "__main__":
    if authentication_status:
        app()
    elif authentication_status == False:
        st.error("Benutzername/Passwort ist falsch")
    elif authentication_status == None:
        st.warning("Bitte gib deine Zugangsdaten ein")
