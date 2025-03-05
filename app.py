import streamlit as st
from openai import OpenAI, OpenAIError
import json
from pathlib import Path
from getpass import getpass
from time import sleep

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

if "openai_key" not in st.session_state:
    st.session_state.openai_key = ""

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

def load_current_conversation():
    if not DB_PATH.exists():
        DB_PATH.mkdir()
        DB_CONVERSATIONS_PATH.mkdir()
        conversation_id = 1
        conversation = {
            "id": conversation_id,
            "name": "Konwersacja 1",
            "chatbot_personality": DEFAULT_PERSONALITY,
            "messages": [],
        }

        # tworzymy nową konwersację
        with open(DB_CONVERSATIONS_PATH / f"{conversation_id}.json", "w") as f:
            f.write(json.dumps(conversation))

        # która od razu staje się aktualną
        with open(DB_PATH / "current.json", "w") as f:
            f.write(json.dumps({
                "current_conversation_id": conversation_id,
            }))

    else:
        # sprawdzamy, która konwersacja jest aktualna
        with open(DB_PATH / "current.json", "r") as f:
            data = json.loads(f.read())
            conversation_id = data["current_conversation_id"]

        # wczytujemy konwersację
        with open(DB_CONVERSATIONS_PATH / f"{conversation_id}.json", "r") as f:
            conversation = json.loads(f.read())

    load_conversation_to_state(conversation)

def save_current_conversations_messages():
    conversation_id = st.session_state["id"]
    new_messages = st.session_state["messages"]

    with open(DB_CONVERSATIONS_PATH / f"{conversation_id}.json", "r") as f:
        conversation = json.loads(f.read())

    with open(DB_CONVERSATIONS_PATH / f"{conversation_id}.json", "w") as f:
        f.write(json.dumps({
            **conversation,
            "messages": new_messages,
        }))

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
    conversations = []
    for p in DB_CONVERSATIONS_PATH.glob("*.json"):
        with open(p, "r") as f:
            conversation = json.loads(f.read())
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