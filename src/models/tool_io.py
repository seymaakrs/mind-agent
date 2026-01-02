from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# Firebase Storage tool IO models
class UploadFileInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_data: bytes
    destination_path: str = Field(alias="destinationPath")
    content_type: Optional[str] = Field(default=None, alias="contentType")


class ListFilesInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prefix: str = ""
    max_results: int = Field(default=100, alias="maxResults")


class DeleteFileInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_path: str = Field(alias="filePath")


# Firestore document tool IO models
class GetDocumentInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(alias="documentId")
    collection: str = "documents"


class SaveDocumentInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(alias="documentId")
    data: dict[str, Any]
    collection: str = "documents"
    merge: bool = True


class QueryDocumentsInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field: str
    operator: str
    value: Any
    collection: str = "documents"
    limit: int = 100


# Instagram tool IO model
class PostInstagramInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_path: str = Field(alias="filePath")
    caption: str
    content_type: Literal["image", "video"] = Field(
        default="image", alias="contentType", description="Content type: 'image' or 'video'"
    )


# Image/Video tool output models
class MediaToolOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    path: Optional[str] = None
    public_url: Optional[str] = Field(default=None, alias="publicUrl")
    file_name: Optional[str] = Field(default=None, alias="fileName")
    success: bool = True


__all__ = [
    "UploadFileInput",
    "ListFilesInput",
    "DeleteFileInput",
    "GetDocumentInput",
    "SaveDocumentInput",
    "QueryDocumentsInput",
    "PostInstagramInput",
    "MediaToolOutput",
]
