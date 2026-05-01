from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class BaseModelWithConfig(BaseModel):
    model_config = {"extra": "allow"}

class SecuritySchemeType(Enum):
    apiKey = "apiKey"
    http = "http"

class SecurityBase(BaseModelWithConfig):
    type_: Annotated[SecuritySchemeType, Field(alias="type")]
    description: str | None = None
