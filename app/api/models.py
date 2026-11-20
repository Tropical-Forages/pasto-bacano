"""Request and response schemas of the web chat channel.

They follow the contract of the Time2Graze website
(``website/providers/agent.js``):

    POST /api/chat  {session_id, message, language, location, files}
    ->              {reply, attachments: [{type, url, title, mime_type}]}
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

MAX_MESSAGE_CHARS = 4000


class Location(BaseModel):
    """A location shared from the browser, as on WhatsApp."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class InputFile(BaseModel):
    """A file attached to a message (farm boundary or photo), base64 encoded."""

    name: str = Field(min_length=1, max_length=200)
    mime_type: str = Field(default="", max_length=100)
    content_base64: str = Field(min_length=1, max_length=7_500_000)


class ChatRequest(BaseModel):
    """One user message from the website: text, a shared location, files, or a mix."""

    session_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    message: str = Field(default="", max_length=MAX_MESSAGE_CHARS)
    language: Optional[str] = Field(default=None, max_length=16)
    location: Optional[Location] = None
    files: list[InputFile] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def _has_content(self) -> "ChatRequest":
        if not self.message.strip() and self.location is None and not self.files:
            raise ValueError("Send a message, a location or a file.")
        return self

    def agent_input(self) -> str:
        """The text given to the agent; a location becomes the same sentence Semente's WhatsApp channel sends."""
        parts = [self.message.strip()] if self.message.strip() else []
        if self.location is not None:
            parts.append(
                f"I want to register my property at coordinates "
                f"Lat: {self.location.latitude} Long: {self.location.longitude}."
            )
        return " ".join(parts)


class Attachment(BaseModel):
    """A map, report or video produced during the turn, as a link."""

    type: Literal["image", "document", "video"]
    url: str
    title: str = ""
    mime_type: str = ""


class ChatResponse(BaseModel):
    """The agent's answer to one message."""

    reply: str
    attachments: list[Attachment] = Field(default_factory=list)
