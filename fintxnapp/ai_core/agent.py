from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_core.runnables import Runnable
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.tools import Tool, StructuredTool
from langchain.agents.agent_types import AgentType
from langchain.schema import SystemMessage
from langchain.chains import ConversationalRetrievalChain   # chain is specifically designed for question-answering over a knowledge base in a conversational context, taking into account the chat history.
# from langchain.embeddings import OpenAIEmbeddings
from .memory import get_user_memory, get_vector_memory, store_message
from .tools import (
    get_user_spending_summary,
    get_investment_suggestions,
    explain_financial_concept,
    predict_future_spending,
    get_personalized_financial_tips,
    evaluate_proposed_purchase,
    suggest_monthly_budget,
    summarize_financial_behavior,
    calculate_financial_health_score,
    get_account_balance_details
)
from .prompts import FINANCE_ASSISTANT_PROMPT
from typing import Optional, Literal
from pydantic import BaseModel, Field


# Set OpenAI model
llm = ChatOpenAI(model="gpt-4.1-2025-04-14", temperature=0)

# Initialize embedding model
embeddings = OpenAIEmbeddings()

# Debug wrapper to log tool usage
def wrap_with_logging(name, func):
    def wrapped(*args, **kwargs):
        print(f"\n🔧 Tool Used: {name}")
        print(f"📥 Input: {kwargs if kwargs else args}")
        result = func(*args, **kwargs)
        print(f"📤 Output: {result}\n")
        return result
    return wrapped

class GetAccountBalanceDetailsArgs(BaseModel):
    """Input arguments for the get_account_balance_details tool."""
    detail: Optional[Literal["current", "month_balance", "month_expenses"]] = Field("current", description="The type of balance detail to retrieve. Options are 'current', 'month_balance', or 'month_expenses'.")
    start_date: Optional[str] = Field(None, description="Optional start date (YYYY-MM-DD) to filter transactions.")
    end_date: Optional[str] = Field(None, description="Optional end date (YYYY-MM-DD) to filter transactions.")
    transaction_type: Optional[Literal["credit", "debit"]] = Field(None, description="Optional transaction type to filter by ('credit' or 'debit').")



# Wrap tools as LangChain Tool objects with logging
tools = [
    Tool.from_function(
        name="get_user_spending_summary",
        func=wrap_with_logging("get_user_spending_summary", lambda *args, **kwargs: get_user_spending_summary(**kwargs) if kwargs else get_user_spending_summary(category=args[0], month=args[1], year=args[2], user_id=args[3], transaction_type=args[4]) if len(args) == 5 else None),
        description="Get a detailed summary of spending or income for a specific category, month, and year. Returns total amount, transaction count, and average transaction value."
    ),
    Tool.from_function(
        name="get_investment_suggestions",
        func=wrap_with_logging("get_investment_suggestions", lambda *args, **kwargs: get_investment_suggestions(**kwargs) if kwargs else get_investment_suggestions(amount=args[0], risk_level=args[1], user_id=args[2]) if len(args) == 3 else None),
        description="Suggests a portfolio of investment options (SIPs, mutual funds, etc.) tailored to a monthly amount and risk level, including rationale for each suggestion."
    ),
    Tool.from_function(
        name="explain_financial_concept",
        func=wrap_with_logging("explain_financial_concept", lambda *args, **kwargs: explain_financial_concept(**kwargs) if kwargs else explain_financial_concept(term=args[0], user_id=args[1]) if len(args) == 2 else None),
        description="Provides a clear and concise explanation of a financial term or concept, including examples and potential implications for the user."
    ),
    Tool.from_function(
        name="predict_future_spending",
        func=wrap_with_logging("predict_future_spending", lambda *args, **kwargs: predict_future_spending(**kwargs) if kwargs else predict_future_spending(user_id=args[0]) if len(args) == 1 else None),
        description="Predicts spending for the next month across different categories based on trends from the past three months, highlighting potential areas of increase or decrease."
    ),
    Tool.from_function(
        name="get_personalized_financial_tips",
        func=wrap_with_logging("get_personalized_financial_tips", lambda *args, **kwargs: get_personalized_financial_tips(**kwargs) if kwargs else get_personalized_financial_tips(user_id=args[0]) if len(args) == 1 else None),
        description="Generates actionable and personalized financial tips based on recent spending patterns, including saving opportunities and potential budget adjustments."
    ),
    Tool.from_function(
        name="evaluate_proposed_purchase",
        func=wrap_with_logging("evaluate_proposed_purchase", lambda *args, **kwargs: evaluate_proposed_purchase(**kwargs) if kwargs else evaluate_proposed_purchase(item=args[0], cost=args[1], user_id=args[2]) if len(args) == 3 else None),
        description="Analyzes a proposed purchase (item and cost) against the user's financial situation (savings, spending habits, budget) and provides a recommendation on whether it's a financially wise decision, along with reasoning."
    ),
    Tool.from_function(
        name="suggest_monthly_budget",
        func=wrap_with_logging("suggest_monthly_budget", lambda *args, **kwargs: suggest_monthly_budget(**kwargs) if kwargs else suggest_monthly_budget(user_id=args[0]) if len(args) == 1 else None),
        description="Analyzes past spending to suggest a comprehensive monthly budget plan with recommended spending limits for various categories and an overall savings target."
    ),
    Tool.from_function(
        name="summarize_financial_behavior",
        func=wrap_with_logging("summarize_financial_behavior", lambda *args, **kwargs: summarize_financial_behavior(**kwargs) if kwargs else summarize_financial_behavior(user_id=args[0]) if len(args) == 1 else None),
        description="Provides a detailed summary of the user's financial behavior over the recent period, identifying key spending categories, trends (e.g., increasing/decreasing spending), and potential financial habits."
    ),
    Tool.from_function(
        name="calculate_financial_health_score",
        func=wrap_with_logging("calculate_financial_health_score", lambda *args, **kwargs: calculate_financial_health_score(**kwargs) if kwargs else calculate_financial_health_score(month=args[0], year=args[1], user_id=args[2]) if len(args) == 3 else None),
        description="Calculates a financial health score (0-100) based on income, expenses, and savings ratio for a specific month, along with a breakdown of contributing factors and areas for improvement."
    ),
    StructuredTool.from_function(
        func=wrap_with_logging(get_account_balance_details.__name__, get_account_balance_details),
        name="get_account_balance_details",
        description="""Get details about your account balance. You can ask for the current balance,
        the balance change for a specific period, or the total expenses for a specific period.
        You can specify the time period using a date range (YYYY-MM-DD to<ctrl3348>-MM-DD).
        You can optionally filter by transaction type ('credit' or 'debit').
        Use 'current' for the overall balance, 'month_balance' for the balance change in the specified period,
        and 'month_expenses' for the total expenses in the specified period.
        Requires the user ID.""",
        args_schema=GetAccountBalanceDetailsArgs
    )
]

# Custom Prompt Template with system prompt
prompt = ChatPromptTemplate.from_messages(
    [
    SystemMessage(content=FINANCE_ASSISTANT_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)


# Initialize the agent per user
def get_finance_agent(user_id: str):
    memory = get_user_memory(user_id)
    agent = create_openai_functions_agent(
        llm=llm, 
        tools=tools, 
        prompt=prompt
    )
    executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        memory=memory
    )
    return executor

    
# Run the agent with tool + memory(main entry point for interacting with the financial agent.)
def run_finance_agent(query: str, user_id: str) -> str:
    """
    Core agent entry point. Sends user message to GPT agent and returns response.
    Injects user_id into all tool inputs implicitly before execution.
    """
    try:
        print(f"🧠 Chatbot invoked | user_id: {user_id} | mode: agent | message: {query}", flush=True)
        agent = get_finance_agent(user_id)

        # Simplified approach - modify the input directly
        def preprocess_input(input_data: dict):
            if isinstance(input_data, dict) and "user_id" not in input_data:
                input_data["user_id"] = int(user_id)
            return input_data

        # Apply the preprocessing to all tools
        for tool in agent.tools:
            original_func = tool.func
            tool.func = lambda *args, **kwargs: original_func(**preprocess_input(kwargs if kwargs else {"term": args[0]}))
        
        response = agent.invoke({"input": query})
        answer = response.get("output", "No response from agent.")
        store_message(user_id, query, answer)
        return answer
    
    except Exception as e:
        return f"Agent error: {str(e)}"
    

# Retrieval chain for historical QA
def get_retrieval_chain(user_id: str):
    retriever = get_vector_memory(user_id)
    return ConversationalRetrievalChain.from_llm(
        llm=llm,                                   # Passes the OpenAI chat model to be used for generating the answer.
        retriever=retriever,                       # Provides the retriever to fetch relevant documents based on the query.
        return_source_documents=False
    )


# Run the conversational retriever (no tools, just history-based)
def run_retrieval_chain(query: str, user_id: str) -> str:
    try:
        print(f"🧠 Chatbot invoked | user_id: {user_id} | mode: retrieval | message: {query}", flush=True)
        chain = get_retrieval_chain(user_id)
        response = chain.invoke({"question": query, "chat_history": []})
        store_message(user_id, query, response)
        return response
    except Exception as e:
        return f"Retrieval error: {str(e)}"
    

# Unified entry point: choose between agent or retriever
def run_chatbot(query: str, user_id: str, mode: str = "agent") -> str:
    if mode == "retrieval":
        return run_retrieval_chain(query, user_id)
    return run_finance_agent(query, user_id)