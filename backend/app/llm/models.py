from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LLMProvider = Literal[
    "ollama",
    "openrouter",
]

MessageRole = Literal[
    "system",
    "user",
    "assistant",
]


class ChatMessage(BaseModel):
    """Mensaje enviado a un modelo de lenguaje."""

    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    role: MessageRole
    content: str = Field(min_length=1)


class ModelResponse(BaseModel):
    """Respuesta normalizada de un proveedor LLM."""

    provider: LLMProvider
    model: str = Field(min_length=1)
    content: str = Field(min_length=1)
    prompt_tokens: int | None = Field(
        default=None,
        ge=0,
    )
    completion_tokens: int | None = Field(
        default=None,
        ge=0,
    )
    fallback_used: bool = False


class ModelProviderError(RuntimeError):
    """Error controlado de un proveedor LLM."""