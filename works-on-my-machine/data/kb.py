"""
범용 Knowledge Base 레이어: manifest 기반 문서 등록 및 조회.

- 단일 진실 공급원: manifest.json (문서 id, path, metadata 목록)
- 문서 본문은 path 기준으로 저장 (폴더 구조는 도메인 비의존)
- 추가/삭제: manifest 항목만 수정 후 재인제스트
- Azure Blob Storage: AZURE_STORAGE_CONNECTION_STRING 환경변수가 있으면 Blob에서 읽고,
  없으면 로컬 파일 폴백 (개발 환경에서는 로컬 그대로 동작).
"""

import json
import os
from pathlib import Path
from typing import Any, Callable

MANIFEST_VERSION = "1.0"
BLOB_CONTAINER_NAME = "documents"

# ---------------------------------------------------------------------------
# Azure Blob Storage 클라이언트 (프로세스당 1회 초기화)
# ---------------------------------------------------------------------------

_container_client = None
_container_client_initialized = False


def _get_blob_container_client():
    """
    Azure Blob Storage 컨테이너 클라이언트 반환.
    AZURE_STORAGE_CONNECTION_STRING 환경변수가 없거나 오류 시 None 반환 → 로컬 파일 폴백.
    """
    global _container_client, _container_client_initialized
    if _container_client_initialized:
        return _container_client
    _container_client_initialized = True
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        return None
    try:
        from azure.storage.blob import BlobServiceClient
        _container_client = (
            BlobServiceClient.from_connection_string(conn_str)
            .get_container_client(BLOB_CONTAINER_NAME)
        )
        return _container_client
    except Exception:
        return None


def get_data_source() -> str:
    """
    현재 문서 데이터 소스 반환.
    - "azure_blob": AZURE_STORAGE_CONNECTION_STRING 설정됨 + Blob에서 manifest 읽기 성공
    - "local": 로컬 파일 사용 (Blob 미설정 또는 연결 실패)
    """
    container = _get_blob_container_client()
    if container is None:
        return "local"
    try:
        blob = container.get_blob_client("manifest.json")
        blob.download_blob().readall()
        return "azure_blob"
    except Exception:
        return "local"


def _blob_name_from_path(manifest_rel_path: str) -> str:
    """
    manifest의 상대 경로 → Blob 이름 변환.
    예: "documents/CAT-001/POST-001/FILE-001.txt" → "CAT-001/POST-001/FILE-001.txt"
    """
    p = manifest_rel_path.replace("\\", "/")
    if p.startswith("documents/"):
        return p[len("documents/"):]
    return p


# ---------------------------------------------------------------------------
# 로컬 파일 경로 헬퍼
# ---------------------------------------------------------------------------

def manifest_path(base_dir: Path) -> Path:
    return base_dir / "manifest.json"


# ---------------------------------------------------------------------------
# Manifest 로드/저장
# ---------------------------------------------------------------------------

def load_manifest(base_dir: Path) -> list[dict]:
    """
    manifest.json 로드.
    Blob Storage 환경변수 있으면 Blob에서, 없으면 로컬에서.
    반환: [ { "id", "path", "metadata": {} }, ... ]
    """
    container = _get_blob_container_client()
    if container is not None:
        try:
            blob = container.get_blob_client("manifest.json")
            data = json.loads(blob.download_blob().readall().decode("utf-8"))
            return data.get("documents", [])
        except Exception:
            pass  # Blob 실패 시 로컬 폴백

    path = manifest_path(base_dir)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("documents", [])


def save_manifest(base_dir: Path, documents: list[dict]) -> None:
    """
    manifest.json 저장.
    Blob Storage 환경변수 있으면 Blob에, 없으면 로컬에.
    """
    content = json.dumps(
        {"version": MANIFEST_VERSION, "documents": documents},
        ensure_ascii=False,
        indent=2,
    )
    container = _get_blob_container_client()
    if container is not None:
        try:
            container.get_blob_client("manifest.json").upload_blob(
                content.encode("utf-8"), overwrite=True
            )
            return
        except Exception:
            pass  # Blob 실패 시 로컬 폴백

    path = manifest_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# 문서 조회
# ---------------------------------------------------------------------------

def metadata_matches(doc_meta: dict, filter_spec: dict | None) -> bool:
    """filter_spec의 모든 key=value가 doc_meta에 있으면 True."""
    if not filter_spec:
        return True
    return all(doc_meta.get(k) == v for k, v in filter_spec.items())


def get_documents(
    base_dir: Path,
    manifest_path_override: Path | None = None,
    metadata_filter: dict | Callable[[dict], bool] | None = None,
) -> list[dict]:
    """
    Manifest에서 문서 목록을 읽고, 본문을 로드해 반환.
    Blob Storage 환경변수 있으면 Blob에서, 없으면 로컬 파일에서.

    - base_dir: 로컬 폴백 시 manifest와 path의 기준 디렉터리.
    - metadata_filter: 포함할 문서 필터.
      - dict면 해당 key=value가 metadata에 있는 항목만.
      - callable(metadata) -> bool 이면 True인 항목만.
    반환: [ { "id", "path", "metadata", "content" }, ... ]
    """
    container = _get_blob_container_client()

    # --- manifest 로드 (Blob 우선, 실패 시 로컬 폴백) ---
    data = None
    if container is not None:
        try:
            blob = container.get_blob_client("manifest.json")
            data = json.loads(blob.download_blob().readall().decode("utf-8"))
        except Exception:
            pass  # Blob 실패 시 아래 로컬 시도
    if data is None:
        manifest_file = manifest_path_override or base_dir / "manifest.json"
        if not manifest_file.exists():
            return []
        data = json.loads(manifest_file.read_text(encoding="utf-8"))

    entries = data.get("documents", [])
    out = []
    for ent in entries:
        meta = ent.get("metadata") or {}
        if callable(metadata_filter):
            if not metadata_filter(meta):
                continue
        elif isinstance(metadata_filter, dict) and not metadata_matches(meta, metadata_filter):
            continue

        # --- 문서 본문 로드 ---
        content = ""
        if container is not None:
            try:
                blob_name = _blob_name_from_path(ent["path"])
                blob = container.get_blob_client(blob_name)
                content = blob.download_blob().readall().decode("utf-8")
            except Exception:
                content = ""
        else:
            path = (
                base_dir / ent["path"]
                if not Path(ent["path"]).is_absolute()
                else Path(ent["path"])
            )
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                content = ""

        out.append({
            "id": ent["id"],
            "path": ent["path"],
            "metadata": meta,
            "content": content,
        })
    return out


# ---------------------------------------------------------------------------
# 문서 추가/삭제 (manifest 조작)
# ---------------------------------------------------------------------------

def add_document(
    base_dir: Path,
    doc_id: str,
    relative_path: str,
    metadata: dict | None = None,
) -> None:
    """Manifest에 문서 한 건 추가 (이미 있으면 덮어쓰지 않고 무시)."""
    docs = load_manifest(base_dir)
    if any(d["id"] == doc_id for d in docs):
        return
    docs.append({
        "id": doc_id,
        "path": relative_path,
        "metadata": metadata or {},
    })
    save_manifest(base_dir, docs)


def remove_document(base_dir: Path, doc_id: str) -> bool:
    """Manifest에서 해당 id 제거. 반환: 제거 여부."""
    docs = load_manifest(base_dir)
    new_docs = [d for d in docs if d["id"] != doc_id]
    if len(new_docs) == len(docs):
        return False
    save_manifest(base_dir, new_docs)
    return True


def update_document_metadata(base_dir: Path, doc_id: str, metadata_updates: dict) -> bool:
    """
    Manifest에서 특정 문서의 metadata를 부분 업데이트.
    예: update_document_metadata(base, "DOC-001", {"status": "deprecated"})
    반환: 성공 여부 (id를 못 찾으면 False).
    """
    docs = load_manifest(base_dir)
    for doc in docs:
        if doc["id"] == doc_id:
            doc.setdefault("metadata", {}).update(metadata_updates)
            save_manifest(base_dir, docs)
            return True
    return False
