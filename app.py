import streamlit as st
from openai import OpenAI, OpenAIError
import json
from pathlib import Path
from getpass import getpass
from time import sleep
import os
import bcrypt

model_pricings = {
    "gpt-4o": {
        "input_tokens": 5.00 / 1_000_000, # per token
        "output_tokens": 15.00 / 1_000_000, #per token
    },
    "gpt-4o-mini": {
        "input_tokens": 0.150 / 1_000_000, # per token
        "output_tokens": 0.600 / 1_000_000, # per token
    }
}
MODEL = "gpt-4o"
USD_TO_PLN = 4
PRICING = model_pricings[MODEL]

st.title("\U0001F5E3️ TalkMate")

#
# LOGIN/REGISTER
#

users_db_path = "db"
users_db_file = Path(users_db_path) / "users.json"
os.makedirs(users_db_path, exist_ok=True)
if not users_db_file.exists():
    with open(users_db_file, "w") as f:
        json.dump({}, f)

# Funkcje do obsługi użytkowników
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_hash: str, password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

def login_user(username, password):
    with open(users_db_file, "r") as f:
        users_data = json.load(f)
    return username in users_data and verify_password(users_data[username], password)

def register_user(username, password, confirm_password):
    if password != confirm_password:
        st.error("Hasła nie są identyczne! Spróbuj ponownie.")
        return False
    with open(users_db_file, "r") as f:
        users_data = json.load(f)
    if username in users_data:
        st.error("Użytkownik o tej nazwie już istnieje!")
        return False
    users_data[username] = hash_password(password)
    with open(users_db_file, "w") as f:
        json.dump(users_data, f)
    return True

# Stan sesji użytkownika
if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False

if not st.session_state.user_authenticated:
    tab1, tab2 = st.tabs([
        "Zaloguj się",
        "Zarejestruj się"
    ])

if not st.session_state.user_authenticated:
    tab1.subheader("Zaloguj się")
    username = tab1.text_input("Nazwa użytkownika", key="login_username")
    password = tab1.text_input("Hasło", type="password", key="login_password")
    
    if tab1.button("Zaloguj"):
        if username and password and login_user(username, password):
            st.session_state.user_authenticated = True
            st.session_state.username = username
            st.success("Zalogowano pomyślnie!")
            st.rerun()
        else:
            st.error("Błędna nazwa użytkownika lub hasło.")

    tab2.subheader("Zarejestruj się")
    reg_username = tab2.text_input("Nowa nazwa użytkownika", key="register_username")
    reg_password = tab2.text_input("Nowe hasło", type="password", key="register_password")
    confirm_password = tab2.text_input("Potwierdź hasło", type="password", key="confirm_password")

    if tab2.button("Zarejestruj się"):
        if reg_username and reg_password and confirm_password:
            if register_user(reg_username, reg_password, confirm_password):
                st.session_state.user_authenticated = True
                st.session_state.username = reg_username
                st.success("Zarejestrowano pomyślnie! Zalogowano.")
                st.rerun()
        else:
            st.error("Wpisz nazwę użytkownika i hasło.")
else:
    st.sidebar.write(f"Zalogowany jako: {st.session_state.username}")
    if st.sidebar.button("Wyloguj się"):
        st.session_state.clear()
        st.rerun()
#
# API KEY
#

if "openai_key" not in st.session_state:
    st.session_state.openai_key = ""

if st.session_state.user_authenticated:
    if not st.session_state.openai_key:
        openai_key = st.text_input("Podaj swój OpenAI API Key:", type="password")

        if openai_key:  
            st.session_state.openai_key = openai_key
            st.session_state.openai_key_verified = False
            st.rerun()
    else: 
        if not st.session_state.openai_key_verified:
            try:
                # Sprawdzenie poprawności klucza przez wysłanie testowego zapytania
                openai_client = OpenAI(api_key=st.session_state.openai_key)
                response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo", messages=[{"role": "system", "content": "Ping"}]
                )

                st.session_state.openai_key_verified = True
                st.toast("Klucz API został wprowadzony!", icon="🎉")

            except OpenAIError:
                st.error("Błędny klucz API! Wpisz poprawny klucz.")
                sleep(3)
                del st.session_state.openai_key
                st.session_state.openai_key_verified = False
                st.rerun()

openai_client = OpenAI(api_key=st.session_state.openai_key)

if "openai_key_verified" not in st.session_state:
    st.session_state.openai_key_verified = False

if st.session_state.user_authenticated and not st.session_state.openai_key_verified:
    st.subheader("Jak stowrzyć własny OpenAI API Key?")
    st.video("https://www.youtube.com/watch?v=hSVTPU-FVLI&ab_channel=techHow")


#
# CHATBOT
#

def get_chatbot_reply(user_prompt, memory):
    # dodaj system message
    messages = [
        {
            "role": "system",
            "content": st.session_state["chatbot_personality"],
        },
    ]

    # dodaj wszystkie wiadomosci z pamieci
    for message in memory:
        messages.append({
            "role": message["role"], 
            "content": message["content"]
            })

    # dodaj wiadomosci uzytkownika
    messages.append({
        "role": "user", 
        "content": user_prompt
        })

    response = openai_client.chat.completions.create(
        model=MODEL,
        messages=messages
    )

    usage = {}
    if response.usage:
        usage = {
            # input
            "prompt_tokens": response.usage.prompt_tokens,
            # output
            "completion_tokens": response.usage.completion_tokens,
            # input + output
            "total_tokens": response.usage.total_tokens,
        }

    return {
        "role": "assistant",
        "content": response.choices[0].message.content,
        "usage": usage,
    }

#
# CONVERSATION HISTORY AND DATABASE
#

DEFAULT_PERSONALITY = """
Jesteś pomocnikiem, który odpowiada na wszystkie pytania użytkownika.
Odpowiadaj na pytania w sposób zwięzły i zrozumiały.
""".strip()

DB_PATH = Path("db")
DB_CONVERSATIONS_PATH = DB_PATH / "conversations"

def load_conversation_to_state(conversation):
    st.session_state["id"] = conversation["id"]
    st.session_state["name"] = conversation["name"]
    st.session_state["messages"] = conversation["messages"]
    st.session_state["chatbot_personality"] = conversation["chatbot_personality"]

def get_user_conversations_path():
    if "username" not in st.session_state:
        return None
    return DB_CONVERSATIONS_PATH / st.session_state["username"]

def load_current_conversation():
    user_conversations_path = get_user_conversations_path()
    
    if not user_conversations_path:
        return

    if not user_conversations_path.exists():
        user_conversations_path.mkdir(parents=True)
        conversation_id = 1
        conversation = {
            "id": conversation_id,
            "name": "Konwersacja 1",
            "chatbot_personality": DEFAULT_PERSONALITY,
            "messages": [],
        }
        with open(user_conversations_path / f"{conversation_id}.json", "w") as f:
            json.dump(conversation, f)
        
        with open(user_conversations_path / "current.json", "w") as f:
            json.dump({"current_conversation_id": conversation_id}, f)
    else:
        with open(user_conversations_path / "current.json", "r") as f:
            data = json.load(f)
            conversation_id = data["current_conversation_id"]

        with open(user_conversations_path / f"{conversation_id}.json", "r") as f:
            conversation = json.load(f)

    load_conversation_to_state(conversation)

def save_current_conversations_messages():
    user_conversations_path = get_user_conversations_path()
    if not user_conversations_path:
        return

    conversation_id = st.session_state["id"]
    new_messages = st.session_state["messages"]

    with open(user_conversations_path / f"{conversation_id}.json", "r") as f:
        conversation = json.load(f)

    with open(user_conversations_path / f"{conversation_id}.json", "w") as f:
        json.dump({**conversation, "messages": new_messages}, f)

def save_current_conversation_name():
    conversation_id = st.session_state["id"]
    new_conversation_name = st.session_state["new_conversation_name"]

    with open(DB_CONVERSATIONS_PATH / f"{conversation_id}.json", "r") as f:
        conversation = json.loads(f.read())

    with open(DB_CONVERSATIONS_PATH / f"{conversation_id}.json", "w") as f:
        f.write(json.dumps({
            **conversation,
            "name": new_conversation_name,
        }))

def save_current_conversation_personality():
    conversation_id = st.session_state["id"]
    new_chatbot_personality = st.session_state["new_chatbot_personality"]

    with open(DB_CONVERSATIONS_PATH / f"{conversation_id}.json", "r") as f:
        conversation = json.loads(f.read())

    with open(DB_CONVERSATIONS_PATH / f"{conversation_id}.json", "w") as f:
        f.write(json.dumps({
            **conversation,
            "chatbot_personality": new_chatbot_personality,
        }))

def create_new_conversation():
    # poszukajmy ID dla naszej kolejnej konwersacji
    conversations_ids = []
    for p in DB_CONVERSATIONS_PATH.glob("*.json"):
        conversations_ids.append(int(p.stem))

    # conversations_ids zawiera wszystkie ID konwersacji
    # nastepna konwersacja będzie miała ID o 1 większe niż największe ID z listy
    conversation_id = max(conversations_ids) + 1
    personality = DEFAULT_PERSONALITY
    if "chatbot_personality" in st.session_state and st.session_state["chatbot_personality"]:
        personality = st.session_state["chatbot_personality"]

    conversation = {
        "id": conversation_id,
        "name": f"Konwersacja {conversation_id}",
        "chatbot_personality": personality,
        "messages": [],
    }

    # tworzymy nowa konwersacje
    with open(DB_CONVERSATIONS_PATH / f"{conversation_id}.json", "w") as f:
        f.write(json.dumps(conversation))

    # ktora od razu staje sie aktualna
    with open(DB_PATH / "current.json", "w") as f:
        f.write(json.dumps({
            "current_conversation_id": conversation_id,
        }))

    load_conversation_to_state(conversation)
    st.rerun()

def switch_conversation(conversation_id):
    with open(DB_CONVERSATIONS_PATH / f"{conversation_id}.json", "r") as f:
        conversation = json.loads(f.read())

    with open(DB_PATH / "current.json", "w") as f:
        f.write(json.dumps({
            "current_conversation_id": conversation_id,
        }))

    load_conversation_to_state(conversation)
    st.rerun()

def list_conversations():
    user_conversations_path = get_user_conversations_path()
    if not user_conversations_path:
        return []

    conversations = []
    for p in user_conversations_path.glob("*.json"):
        if p.name == "current.json":
            continue  # Pomijamy plik z aktualnym ID konwersacji
        
        with open(p, "r") as f:
            conversation = json.load(f)
            conversations.append({
                "id": conversation["id"],
                "name": conversation["name"],
            })

    return conversations

#
# MAIN PROGRAM
#


load_current_conversation()

if st.session_state.openai_key:
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if st.session_state.openai_key: 
    prompt = st.chat_input("O co chcesz spytać?")
    if prompt:
        # wyswietlanie wiadomosci uzytkownika
        with st.chat_message("user"):
            st.markdown(prompt)

        st.session_state["messages"].append({
            "role": "user",
            "content": prompt
        })

        # wyswietlenie odpowiedzi AI
        with st.chat_message("assistant"):
            chatbot_message = get_chatbot_reply(
                prompt,
                memory=st.session_state["messages"][-20:]
                )
            st.markdown(chatbot_message["content"])

        st.session_state["messages"].append(chatbot_message)
        save_current_conversations_messages()

if st.session_state.openai_key:
    with st.sidebar:
        st.write("Aktualny model:", MODEL)
        total_cost = 0
        for message in st.session_state["messages"]:
            if "usage" in message:
                total_cost += message["usage"]["prompt_tokens"] * PRICING["input_tokens"]
                total_cost += message["usage"]["completion_tokens"] * PRICING["output_tokens"]
            
        c0, c1 = st.columns(2)
        with c0:
            st.metric("Koszt rozmowy (USD)", f"${total_cost:.4f}")

        with c1:
            st.metric("Koszt rozmowy (PLN)", f"{total_cost * USD_TO_PLN:.4f}")

        st.session_state["name"] = st.text_input(
            "Nazwa konwersacji",
            value=st.session_state["name"],
            key="new_conversation_name",
            on_change=save_current_conversation_name,
        )

        st.session_state["chatbot_personality"] = st.text_area(
            "Osobowość chatbota",
            max_chars=1000,
            height=200,
            value=st.session_state["chatbot_personality"],
            key="new_chatbot_personality",
            on_change=save_current_conversation_personality,
        )

        st.subheader("Konwersacje")
        if st.button("Nowa Konwersacja"):
            create_new_conversation()

        # pokazujemy tylko top 5 konwersacji
        conversations = list_conversations()
        sorted_conversations = sorted(conversations, key=lambda x: x["id"], reverse=True)
        for conversation in sorted_conversations[:5]:
            c0, c1 = st.columns([10, 5])
            with c0:
                st.write(conversation["name"])

            with c1:
                if st.button("załaduj", key=conversation["id"], disabled=conversation["id"] == st.session_state["id"]):
                    switch_conversation(conversation["id"])