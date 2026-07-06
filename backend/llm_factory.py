import os

from langchain_openai import ChatOpenAI

from config import (
    LLM_TYPE,
    OLLAMA_API_BASE,
    OLLAMA_API_KEY,
    OLLAMA_MODEL_NAME,
    ONEAPI_API_BASE,
    ONEAPI_API_KEY,
    ONEAPI_MODEL_NAME,
    OPENAI_API_BASE,
    OPENAI_API_KEY,
    OPENAI_MODEL_NAME,
)


def _require_api_key(name: str, value: str):
    if not value:
        raise ValueError(
            f"{name} is empty. Set the matching environment variable before starting the service."
        )


def _build_chat_model(base_url: str, api_key: str, model_name: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
    )


def build_llm(llm_type: str = LLM_TYPE) -> ChatOpenAI:
    if llm_type == "oneapi":
        _require_api_key("ONEAPI_API_KEY", ONEAPI_API_KEY)
        os.environ["OPENAI_API_KEY"] = ONEAPI_API_KEY
        os.environ["OPENAI_API_BASE"] = ONEAPI_API_BASE
        return _build_chat_model(
            base_url=ONEAPI_API_BASE,
            api_key=ONEAPI_API_KEY,
            model_name=ONEAPI_MODEL_NAME,
        )

    if llm_type == "ollama":
        os.environ["OPENAI_API_KEY"] = OLLAMA_API_KEY
        os.environ["OPENAI_API_BASE"] = OLLAMA_API_BASE
        return _build_chat_model(
            base_url=OLLAMA_API_BASE,
            api_key=OLLAMA_API_KEY,
            model_name=OLLAMA_MODEL_NAME,
        )

    _require_api_key("OPENAI_API_KEY", OPENAI_API_KEY)
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE
    return _build_chat_model(
        base_url=OPENAI_API_BASE,
        api_key=OPENAI_API_KEY,
        model_name=OPENAI_MODEL_NAME,
    )
