from langchain.memory import ConversationBufferMemory
from langchain_community.vectorstores import FAISS   #  FAISS (Facebook AI Similarity Search) is a library for efficient similarity search and clustering of dense vectors. 
from langchain.embeddings.openai import OpenAIEmbeddings     # class is used to create embeddings (numerical representations) of text using OpenAI's models. 
import os
import pickle   # used for serializing and de-serializing Python object structures. 
from django.conf import settings
from fintxnapp.models import ChatHistory 

# Get memory from PostgreSQL for agent
def get_user_memory(user_id: str):
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    
    # Load past chat messages from DB
    chats = ChatHistory.objects.filter(user_id=user_id).order_by("timestamp")
    print(f"📦 Loading {chats.count()} chat history records for user_id={user_id}", flush=True)
    
    for chat in chats:
        # This adds the user's message to the ConversationBufferMemory.
        memory.chat_memory.add_user_message(chat.user_message)
        # This adds the AI's response corresponding to the user's message to the ConversationBufferMemory
        memory.chat_memory.add_ai_message(chat.ai_response)

    return memory

# Store messages in DB
def store_message(user_id: str, user_msg: str, ai_msg: str):
    ChatHistory.objects.create(user_id=user_id, user_message=user_msg, ai_response=ai_msg)

# FAISS vector store logic
def get_vector_memory(user_id: str):
    # constructs the file path where the FAISS index for the given user_id will be stored.
    db_path = os.path.join(settings.BASE_DIR, f"faiss_index/{user_id}")
    # This block checks if a directory already exists for the user's FAISS index.
    if os.path.exists(db_path):
        # opens a file named faiss.pkl within that directory in read-binary mode ("rb").
        with open(os.path.join(db_path, "faiss.pkl"), "rb") as f:
            # loads the serialized FAISS vector store object
            vectorstore = pickle.load(f)

    # This block executes if the directory for the user's FAISS index does not exist.
    else:
        # used to generate embeddings for any text that is added to the vector store later.
        embeddings = OpenAIEmbeddings()
        # creates a new, empty FAISS vector store.
        vectorstore = FAISS.from_texts([], embedding=embeddings)
        os.makedirs(db_path, exist_ok=True)
        # This opens a file named faiss.pkl within the newly created directory in write-binary mode ("wb").
        with open(os.path.join(db_path, "faiss.pkl"), "wb") as f:
            # This serializes the newly created vectorstore object and saves it to the faiss.pkl file.
            pickle.dump(vectorstore, f)

    # this line converts the vectorstore object into a retriever.
    return vectorstore.as_retriever(search_kwargs={"k": 5})    # it will return the top 5 most relevant documents or text snippets from the vector store.



