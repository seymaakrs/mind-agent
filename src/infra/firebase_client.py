from __future__ import annotations

import mimetypes
from functools import lru_cache
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.storage import Bucket

from src.app.config import get_settings


def _normalize_bucket_name(bucket: str | None) -> str | None:
    """Bucket adini normalize eder - gs:// prefix'ini kaldirir."""
    if not bucket:
        return bucket
    # Remove gs:// prefix if present
    if bucket.startswith("gs://"):
        bucket = bucket[5:]
    # Remove trailing slash if present
    return bucket.rstrip("/")


@lru_cache(maxsize=1)
def _initialize_firebase() -> firebase_admin.App:
    """Firebase app'i initialize eder ve cache'ler."""
    settings = get_settings()
    if not settings.firebase_credentials_file:
        raise ValueError("FIREBASE_CREDENTIALS_FILE env degiskeni ayarlanmamis")

    cred = credentials.Certificate(settings.firebase_credentials_file)
    bucket_name = _normalize_bucket_name(settings.firebase_storage_bucket)
    return firebase_admin.initialize_app(cred, {
        "storageBucket": bucket_name,
    })


def get_firestore_client() -> FirestoreClient:
    """Firestore client instance dondurur."""
    _initialize_firebase()
    return firestore.client()


def get_storage_bucket() -> Bucket:
    """Firebase Storage bucket instance dondurur."""
    _initialize_firebase()
    return storage.bucket()


class FirebaseStorageClient:
    """Firebase Storage client for file operations."""

    def __init__(self) -> None:
        self._bucket: Bucket | None = None

    @property
    def bucket(self) -> Bucket:
        if self._bucket is None:
            self._bucket = get_storage_bucket()
        return self._bucket

    def upload_file(
        self,
        file_data: bytes,
        destination_path: str,
        content_type: str | None = None,
    ) -> dict[str, str]:
        """
        Dosyayi Firebase Storage'a yukler.

        Args:
            file_data: Yuklenecek dosya icerigi (bytes).
            destination_path: Storage'daki hedef yol (ornek: "images/photo.jpg").
            content_type: MIME type (ornek: "image/jpeg"). None ise otomatik belirlenir.

        Returns:
            dict: name, path, public_url bilgilerini icerir.
        """
        if content_type is None:
            content_type = mimetypes.guess_type(destination_path)[0] or "application/octet-stream"

        blob = self.bucket.blob(destination_path)
        blob.upload_from_string(file_data, content_type=content_type)
        blob.make_public()

        return {
            "name": blob.name,
            "path": destination_path,
            "public_url": blob.public_url,
        }

    def download_file(self, file_path: str) -> bytes:
        """
        Firebase Storage'dan dosya indirir.

        Args:
            file_path: Storage'daki dosya yolu veya tam URL.
                       Desteklenen formatlar:
                       - Relative path: "logos/mindid.png"
                       - gs:// URL: "gs://bucket-name/logos/mindid.png"
                       - HTTP URL: "https://storage.googleapis.com/bucket-name/logos/mindid.png"
                       - Firebase URL: "https://firebasestorage.googleapis.com/v0/b/bucket/o/path"

        Returns:
            bytes: Dosya icerigi.
        """
        # Extract path from various URL formats
        path = self._extract_path_from_url(file_path)
        blob = self.bucket.blob(path)
        return blob.download_as_bytes()

    def _extract_path_from_url(self, file_path: str) -> str:
        """URL'den Storage path'i extract eder."""
        import urllib.parse

        # gs:// format: gs://bucket-name/path/to/file
        if file_path.startswith("gs://"):
            # Remove gs://bucket-name/ prefix
            parts = file_path[5:].split("/", 1)
            return parts[1] if len(parts) > 1 else ""

        # Firebase Storage URL: https://firebasestorage.googleapis.com/v0/b/bucket/o/encoded%2Fpath
        if "firebasestorage.googleapis.com" in file_path:
            # Extract path after /o/
            if "/o/" in file_path:
                path_part = file_path.split("/o/")[1]
                # Remove query params and decode
                path_part = path_part.split("?")[0]
                return urllib.parse.unquote(path_part)

        # Google Cloud Storage URL: https://storage.googleapis.com/bucket-name/path
        if "storage.googleapis.com" in file_path and "/b/" not in file_path:
            # Format: https://storage.googleapis.com/bucket-name/path/to/file
            parts = file_path.split("storage.googleapis.com/")[1].split("/", 1)
            return parts[1] if len(parts) > 1 else ""

        # Already a relative path
        return file_path

    def delete_file(self, file_path: str) -> bool:
        """
        Firebase Storage'dan dosya siler.

        Args:
            file_path: Silinecek dosyanin yolu.

        Returns:
            bool: Basarili ise True.
        """
        blob = self.bucket.blob(file_path)
        blob.delete()
        return True

    def list_files(self, prefix: str = "", max_results: int = 100) -> list[dict[str, str]]:
        """
        Firebase Storage'daki dosyalari listeler.

        Args:
            prefix: Dosya yolu prefix'i (klasor gibi).
            max_results: Maksimum sonuc sayisi.

        Returns:
            list: Dosya bilgilerini iceren liste.
        """
        blobs = self.bucket.list_blobs(prefix=prefix, max_results=max_results)
        return [
            {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "public_url": blob.public_url if blob.public_url else None,
            }
            for blob in blobs
        ]

    def get_public_url(self, file_path: str) -> str:
        """
        Dosyanin public URL'ini dondurur.

        Args:
            file_path: Storage'daki dosya yolu.

        Returns:
            str: Public URL.
        """
        blob = self.bucket.blob(file_path)
        blob.make_public()
        return blob.public_url


class FirestoreDocumentClient:
    """Firestore client for document operations."""

    def __init__(self, collection_name: str = "documents") -> None:
        self._db: FirestoreClient | None = None
        self.collection_name = collection_name

    @property
    def db(self) -> FirestoreClient:
        if self._db is None:
            self._db = get_firestore_client()
        return self._db

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        """
        Firestore'dan dokuman okur.

        Args:
            document_id: Dokuman ID'si.

        Returns:
            dict: Dokuman verisi veya None.
        """
        doc_ref = self.db.collection(self.collection_name).document(document_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data["documentId"] = doc.id
            return data
        return None

    def set_document(
        self,
        document_id: str,
        data: dict[str, Any],
        merge: bool = True,
    ) -> dict[str, str]:
        """
        Firestore'a dokuman yazar.

        Args:
            document_id: Dokuman ID'si.
            data: Yazilacak veri.
            merge: True ise mevcut veriyle birlestirir.

        Returns:
            dict: documentId bilgisi.
        """
        doc_ref = self.db.collection(self.collection_name).document(document_id)
        doc_ref.set(data, merge=merge)
        return {"documentId": document_id}

    def add_document(self, data: dict[str, Any]) -> dict[str, str]:
        """
        Firestore'a otomatik ID ile dokuman ekler.

        Args:
            data: Yazilacak veri.

        Returns:
            dict: documentId bilgisi.
        """
        doc_ref = self.db.collection(self.collection_name).add(data)
        return {"documentId": doc_ref[1].id}

    def delete_document(self, document_id: str) -> bool:
        """
        Firestore'dan dokuman siler.

        Args:
            document_id: Silinecek dokuman ID'si.

        Returns:
            bool: Basarili ise True.
        """
        doc_ref = self.db.collection(self.collection_name).document(document_id)
        doc_ref.delete()
        return True

    def list_documents(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Collection'daki tum dokumanlari listeler.

        Args:
            limit: Maksimum sonuc sayisi.

        Returns:
            list: Dokumanlarin listesi.
        """
        query = self.db.collection(self.collection_name).limit(limit)
        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["documentId"] = doc.id
            results.append(data)
        return results

    def query_documents(
        self,
        field: str,
        operator: str,
        value: Any,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Firestore'da sorgu yapar.

        Args:
            field: Sorgulanacak alan.
            operator: Karsilastirma operatoru ("==", ">", "<", ">=", "<=", "in", "array-contains").
            value: Karsilastirilacak deger.
            limit: Maksimum sonuc sayisi.

        Returns:
            list: Eslesen dokumanlarin listesi.
        """
        query = self.db.collection(self.collection_name).where(field, operator, value).limit(limit)
        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["documentId"] = doc.id
            results.append(data)
        return results

    def add_to_subcollection(
        self,
        document_id: str,
        subcollection_name: str,
        data: dict[str, Any],
    ) -> dict[str, str]:
        """
        Bir dokuman altindaki subcollection'a yeni dokuman ekler.

        Args:
            document_id: Ana dokuman ID'si.
            subcollection_name: Subcollection adi.
            data: Eklenecek veri.

        Returns:
            dict: documentId bilgisi.
        """
        doc_ref = (
            self.db.collection(self.collection_name)
            .document(document_id)
            .collection(subcollection_name)
            .add(data)
        )
        return {"documentId": doc_ref[1].id}

    def update_subcollection_doc(
        self,
        document_id: str,
        subcollection_name: str,
        subdoc_id: str,
        data: dict[str, Any],
        merge: bool = True,
    ) -> dict[str, str]:
        """
        Subcollection icindeki bir dokumani gunceller.

        Args:
            document_id: Ana dokuman ID'si.
            subcollection_name: Subcollection adi.
            subdoc_id: Guncellenecek subdokuman ID'si.
            data: Guncellenecek veri.
            merge: True ise mevcut veriyle birlestirir.

        Returns:
            dict: documentId bilgisi.
        """
        doc_ref = (
            self.db.collection(self.collection_name)
            .document(document_id)
            .collection(subcollection_name)
            .document(subdoc_id)
        )
        doc_ref.set(data, merge=merge)
        return {"documentId": subdoc_id}

    def list_subcollection(
        self,
        document_id: str,
        subcollection_name: str,
        order_by: str | None = None,
        order_direction: str = "DESCENDING",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Subcollection icindeki tum dokumanlari listeler.

        Args:
            document_id: Ana dokuman ID'si.
            subcollection_name: Subcollection adi.
            order_by: Siralama alani (ornek: "created_at").
            order_direction: "ASCENDING" veya "DESCENDING".
            limit: Maksimum sonuc sayisi.

        Returns:
            list: Dokumanlarin listesi.
        """
        from google.cloud.firestore import Query

        query = (
            self.db.collection(self.collection_name)
            .document(document_id)
            .collection(subcollection_name)
        )

        if order_by:
            direction = (
                Query.DESCENDING
                if order_direction == "DESCENDING"
                else Query.ASCENDING
            )
            query = query.order_by(order_by, direction=direction)

        query = query.limit(limit)
        docs = query.stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            data["documentId"] = doc.id
            results.append(data)
        return results


@lru_cache(maxsize=1)
def get_storage_client() -> FirebaseStorageClient:
    """FirebaseStorageClient instance dondurur (cached)."""
    return FirebaseStorageClient()


@lru_cache(maxsize=1)
def get_document_client(collection_name: str = "documents") -> FirestoreDocumentClient:
    """FirestoreDocumentClient instance dondurur (cached)."""
    return FirestoreDocumentClient(collection_name=collection_name)


def save_media_record(
    business_id: str,
    media_type: str,
    storage_path: str,
    public_url: str,
    file_name: str,
    prompt_summary: str | None = None,
    log_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Uretilen medyayi Firestore'a kaydeder.

    Path: businesses/{business_id}/media/{media_id}

    Args:
        business_id: Isletme ID'si.
        media_type: "image" veya "video".
        storage_path: Firebase Storage path (ornek: "images/abc/photo.png").
        public_url: Public URL.
        file_name: Dosya adi.
        prompt_summary: Prompt ozeti (opsiyonel).
        log_id: Hangi task'ta uretildigi (opsiyonel).
        metadata: Ek bilgiler - width, height, duration, size_bytes (opsiyonel).

    Returns:
        dict: documentId bilgisi.
    """
    from datetime import datetime, timezone

    doc_client = get_document_client("businesses")

    media_data = {
        "type": media_type,
        "storage_path": storage_path,
        "public_url": public_url,
        "file_name": file_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if prompt_summary:
        media_data["prompt_summary"] = prompt_summary
    if log_id:
        media_data["log_id"] = log_id
    if metadata:
        media_data["metadata"] = metadata

    result = doc_client.add_to_subcollection(
        document_id=business_id,
        subcollection_name="media",
        data=media_data,
    )
    return result


def list_media(
    business_id: str,
    media_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Isletmeye ait medyalari listeler.

    Args:
        business_id: Isletme ID'si.
        media_type: Filtrelemek icin "image" veya "video" (opsiyonel).
        limit: Maksimum sonuc sayisi.

    Returns:
        list: Media dokumanlari listesi.
    """
    doc_client = get_document_client("businesses")

    results = doc_client.list_subcollection(
        document_id=business_id,
        subcollection_name="media",
        order_by="created_at",
        order_direction="DESCENDING",
        limit=limit,
    )

    if media_type:
        results = [r for r in results if r.get("type") == media_type]

    return results


__all__ = [
    "FirebaseStorageClient",
    "FirestoreDocumentClient",
    "get_storage_client",
    "get_document_client",
    "get_firestore_client",
    "get_storage_bucket",
    "save_media_record",
    "list_media",
]
