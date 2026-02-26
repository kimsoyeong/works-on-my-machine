"""
범용 RAG: manifest 기반 문서 로드 → 청킹 → 임베딩 → Chroma 벡터 스토어 저장/검색.

- 문서 목록은 manifest.json 단일 소스 (id, path, metadata). metadata에 status(active/deprecated 등), collection(CAT-001~006) 포함.
- 벡터 스토어 1개로 두 가지 용도:
  1) Policy Agent: 검색 시 metadata_filter에 status=active 만 사용 → 현재 유효한 정책만 참고.
  2) Result 챗봇: 검색 시 status 필터 없음 → deprecated 포함 전체 검색 (과거 정책 변경 설명 등).
- 인제스트: metadata_filter 없이 실행하면 manifest의 모든 문서(active+deprecated 등) 적재. status=active 만 넣으면 기존처럼 현재 문서만.
- 벡터 스토어: Chroma (디스크 영속, 메타데이터 필터 지원).
"""

import json
import os
import re
from pathlib import Path

import data.env  # noqa: F401 - load .env before reading os.environ
from data.kb import get_documents, manifest_path, metadata_matches

DATA_DIR = Path(__file__).resolve().parent
# Chroma 영속 저장 경로
# - Azure Web App: CHROMA_PATH=/mnt/data/chroma_db (Azure Files 마운트 경로)
# - 로컬 개발: 환경변수 미설정 시 data/chroma_db/ 사용
CHROMA_PATH = Path(os.environ.get("CHROMA_PATH", str(DATA_DIR / "chroma_db")))
INDEX_PATH = DATA_DIR / "vector_index.json"  # 하위 호환/CLI 메시지용

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80

# Chroma 컬렉션 이름
CHROMA_COLLECTION_NAME = "policy_chunks"


# ---------------------------------------------------------------------------
# 임베딩 (Azure AI Foundry / Azure OpenAI 우선, 없으면 OpenAI)
# ---------------------------------------------------------------------------

def _embed_openai(text: str, model: str | None = None) -> list[float] | None:
    """
    Azure OpenAI(AI Foundry) 또는 OpenAI로 임베딩 생성.
    AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY 있으면 AzureOpenAI 사용,
    없으면 OPENAI_API_KEY로 OpenAI 사용.
    """
    try:
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
        if not api_key:
            return None

        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        if azure_endpoint and azure_endpoint.strip():
            # Azure AI Foundry / Azure OpenAI
            from openai import AzureOpenAI
            deployment = (
                model
                or os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
                or "text-embedding-3-small"
            )
            client = AzureOpenAI(
                api_key=api_key,
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
                azure_endpoint=azure_endpoint.rstrip("/"),
            )
            resp = client.embeddings.create(input=[text], model=deployment)
            return resp.data[0].embedding

        # OpenAI (비-Azure)
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.embeddings.create(
            input=[text],
            model=model or "text-embedding-3-small",
        )
        return resp.data[0].embedding
    except Exception:
        return None


def _embed_stub(text: str, dim: int = 128) -> list[float]:
    h = hash(text) & 0x7FFFFFFF
    return [((h * (i + 1) * 31) % 1000) / 1000.0 - 0.5 for i in range(dim)]


def embed_text(text: str) -> list[float]:
    vec = _embed_openai(text)
    return vec if vec is not None else _embed_stub(text)


# ---------------------------------------------------------------------------
# 청킹
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    if not text or not text.strip():
        return []
    text = text.strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    current = []
    current_len = 0
    for p in paragraphs:
        p_len = len(p) + 2
        if current_len + p_len <= chunk_size:
            current.append(p)
            current_len += p_len
        else:
            if current:
                chunks.append("\n\n".join(current))
            if len(p) > chunk_size:
                start = 0
                while start < len(p):
                    end = start + chunk_size
                    chunks.append(p[start:end])
                    start = end - overlap
                current = []
                current_len = 0
            else:
                current = [p]
                current_len = p_len
    if current:
        chunks.append("\n\n".join(current))
    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Chroma 벡터 스토어
# ---------------------------------------------------------------------------

def _chroma_metadata_flat(meta: dict) -> dict:
    """Chroma는 str/int/float/bool만 허용. 나머지는 str() 변환."""
    out = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


def _get_chroma_client():
    """Chroma PersistentClient 반환. 실패 시 None."""
    try:
        from chromadb import PersistentClient
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        return PersistentClient(path=str(CHROMA_PATH))
    except Exception:
        return None


def _get_chroma_collection():
    """기본 컬렉션 반환. 없으면 None."""
    client = _get_chroma_client()
    if client is None:
        return None
    try:
        return client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 인제스트
# ---------------------------------------------------------------------------

def ingest(
    base_dir: Path | None = None,
    metadata_filter: dict | None = None,
    out_path: Path | None = None,
) -> list[dict]:
    """
    Manifest 기준으로 문서 로드 → 청킹 → 임베딩 → Chroma 벡터 스토어 저장.
    metadata_filter: 포함할 문서만 (예: {"status": "active"}).
    반환: 인덱스 항목 리스트 (id, path, metadata, chunk_index, content, vector) — 호환용.
    """
    base_dir = base_dir or DATA_DIR
    docs = get_documents(base_dir, metadata_filter=metadata_filter)
    indexed = []
    ids_list = []
    embeddings_list = []
    documents_list = []
    metadatas_list = []

    for doc in docs:
        chunks = chunk_text(doc["content"])
        for i, chunk in enumerate(chunks):
            vector = embed_text(chunk)
            chunk_id = f"{doc['id']}_{i}"
            meta = {"path": doc["path"], "chunk_index": i, **_chroma_metadata_flat(doc["metadata"])}
            indexed.append({
                "id": doc["id"],
                "path": doc["path"],
                "metadata": doc["metadata"],
                "chunk_index": i,
                "content": chunk,
                "vector": vector,
            })
            ids_list.append(chunk_id)
            embeddings_list.append(vector)
            documents_list.append(chunk)
            metadatas_list.append(meta)

    client = _get_chroma_client()
    if client is not None and ids_list:
        # 기존 컬렉션 삭제 후 재생성 (전체 재인제스트)
        try:
            client.delete_collection(name=CHROMA_COLLECTION_NAME)
        except Exception:
            pass
        coll = client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        batch_size = 100
        for start in range(0, len(ids_list), batch_size):
            end = start + batch_size
            coll.add(
                ids=ids_list[start:end],
                embeddings=embeddings_list[start:end],
                documents=documents_list[start:end],
                metadatas=metadatas_list[start:end],
            )
    return indexed


# ---------------------------------------------------------------------------
# 검색
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _metadata_to_chroma_where(metadata_filter: dict | None) -> dict | None:
    """search의 metadata_filter를 Chroma where 형식으로 변환."""
    if not metadata_filter:
        return None
    return {k: v for k, v in metadata_filter.items()}


def _search_chroma(
    query: str,
    k: int = 5,
    metadata_filter: dict | None = None,
) -> list[dict] | None:
    """Chroma에서 유사도 검색. 실패 시 None."""
    coll = _get_chroma_collection()
    if coll is None:
        return None
    try:
        qvec = embed_text(query)
        where = _metadata_to_chroma_where(metadata_filter)
        res = coll.query(
            query_embeddings=[qvec],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        if not res or not res.get("ids") or not res["ids"][0]:
            return []
        ids = res["ids"][0]
        docs = res["documents"][0]
        metadatas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(ids)
        distances = res["distances"][0] if res.get("distances") else [0.0] * len(ids)
        # cosine distance: 0 = 동일, 2 = 반대. score = 1 - (distance/2) 또는 1 - distance (Chroma cosine)
        # Chroma cosine: distance = 1 - similarity 이므로 score = 1 - distance
        out = []
        for i, doc_id in enumerate(ids):
            dist = distances[i] if i < len(distances) else 0
            score = round(1.0 - float(dist), 4) if dist is not None else 0.0
            meta = metadatas[i] if i < len(metadatas) else {}
            out.append({
                "id": doc_id,
                "path": meta.get("path", ""),
                "metadata": {k: v for k, v in meta.items()},
                "content": docs[i] if i < len(docs) else "",
                "score": score,
            })
        return out
    except Exception:
        return None


def load_index(path: Path | None = None) -> list[dict]:
    """JSON 인덱스 로드 (Chroma 미사용/마이그레이션 시). Chroma 사용 시에는 search가 벡터스토어 직접 조회."""
    p = path or INDEX_PATH
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def search(
    query: str,
    k: int = 5,
    index: list[dict] | None = None,
    metadata_filter: dict | None = None,
) -> list[dict]:
    """
    쿼리와 유사한 청크 상위 k개 반환.
    index가 None이면 Chroma 벡터 스토어 사용, 있으면 in-memory 인덱스 사용.
    metadata_filter가 있으면 해당 메타데이터를 만족하는 청크만 검색 (예: {"collection": "CAT-001"}).
    각 항목: { "id", "path", "metadata", "content", "score" }
    """
    if index is not None:
        # in-memory (테스트/하위 호환)
        if not index:
            return []
        qvec = embed_text(query)
        scored = []
        for item in index:
            if metadata_filter and not metadata_matches(item.get("metadata") or {}, metadata_filter):
                continue
            score = _cosine_similarity(qvec, item["vector"])
            scored.append({
                "id": item["id"],
                "path": item["path"],
                "metadata": item.get("metadata"),
                "content": item.get("content"),
                "score": round(score, 4),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    # Chroma 사용
    results = _search_chroma(query, k=k, metadata_filter=metadata_filter)
    if results is not None:
        return results
    # Chroma 없으면 JSON 인덱스 폴백
    index = load_index()
    if not index:
        return []
    qvec = embed_text(query)
    scored = []
    for item in index:
        if metadata_filter and not metadata_matches(item.get("metadata") or {}, metadata_filter):
            continue
        score = _cosine_similarity(qvec, item["vector"])
        scored.append({
            "id": item["id"],
            "path": item["path"],
            "metadata": item.get("metadata"),
            "content": item.get("content"),
            "score": round(score, 4),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


def search_for_result_chatbot(query: str, k: int = 10, metadata_filter: dict | None = None) -> list[dict]:
    """
    Result 챗봇용 RAG 검색. status 제한 없이 검색 (active + deprecated 등 전체).
    "과거에는 허용이었는데 왜 지금 위반이야?" 같은 질문에 deprecated 정책까지 찾아 답할 때 사용.
    metadata_filter에 collection 등만 넣고 status는 넣지 말 것.
    반환 형식은 search()와 동일: [ { "id", "path", "metadata", "content", "score" }, ... ]
    """
    return search(query, k=k, index=None, metadata_filter=metadata_filter)


def route_category(
    query: str,
    categories: list[dict],
    index: list[dict] | None = None,
) -> str | None:
    """
    질의와 가장 관련 있는 카테고리 ID 하나 반환.
    categories: [ {"category_id", "category_name", "description"}, ... ] (schema.CATEGORIES 형태).
    각 카테고리의 (category_name + description)을 임베딩하고, query 임베딩과 유사도가 가장 높은 카테고리 반환.
    """
    if not categories:
        return None
    index = index if index is not None else load_index()
    qvec = embed_text(query)
    best_id = None
    best_score = -1.0
    for cat in categories:
        cid = cat.get("category_id")
        name = cat.get("category_name") or ""
        desc = cat.get("description") or ""
        text = f"{name}. {desc}".strip()
        if not text:
            continue
        cvec = embed_text(text)
        score = _cosine_similarity(qvec, cvec)
        if score > best_score:
            best_score = score
            best_id = cid
    return best_id


def search_in_stages(
    query: str,
    k: int = 5,
    categories: list[dict] | None = None,
    index: list[dict] | None = None,
) -> dict:
    """
    2단계 검색: (1) 질의가 5개 카테고리 중 어디에 해당하는지 결정 (route_category)
              (2) 해당 카테고리(collection) 청크만 metadata_filter로 걸러서 search.
    반환: { "collection": "CAT-001", "results": [ ... ] }
    index=None이면 검색은 Chroma(또는 JSON 폴백) 사용. route_category는 index 미사용.
    """
    if categories is None:
        from data.schema import CATEGORIES
        categories = CATEGORIES
    collection = route_category(query, categories, index=index)
    if not collection:
        results = search(query, k=k, index=None, metadata_filter=None)
        return {"collection": None, "results": results}
    results = search(
        query, k=k, index=None,
        metadata_filter={"collection": collection},
    )
    return {"collection": collection, "results": results}


# ---------------------------------------------------------------------------
# 검증: Chroma에 카테고리/파일별로 청크가 잘 들어갔는지 확인
# ---------------------------------------------------------------------------

def verify_chroma_embedding() -> dict | None:
    """
    Chroma 벡터 DB에 저장된 청크를 카테고리·파일별로 집계해 반환.
    반환: { "total": N, "by_collection": {"CAT-001": n, ...}, "by_path": {"path": n, ...}, "sample": [...] }
    또는 Chroma 없으면 None.
    """
    coll = _get_chroma_collection()
    if coll is None:
        return None
    try:
        # Chroma get(limit=...) 로 전체 조회 (id 없이 limit만 주면 됨)
        out = coll.get(limit=50000, include=["metadatas", "documents"])
        ids = out.get("ids") or []
        metadatas = out.get("metadatas") or []
        documents = out.get("documents") or []

        by_collection = {}
        by_path = {}
        sample = []

        for i, meta in enumerate(metadatas):
            if not isinstance(meta, dict):
                continue
            col = meta.get("collection") or "(no collection)"
            path = meta.get("path") or "(no path)"
            by_collection[col] = by_collection.get(col, 0) + 1
            by_path[path] = by_path.get(path, 0) + 1
            # 카테고리별 첫 청크만 샘플로
            if col not in [s.get("collection") for s in sample]:
                sample.append({
                    "collection": col,
                    "path": path,
                    "chunk_index": meta.get("chunk_index"),
                    "content_preview": (documents[i] if i < len(documents) else "")[:120] + "...",
                })

        return {
            "total": len(ids),
            "by_collection": dict(sorted(by_collection.items())),
            "by_path": dict(sorted(by_path.items())),
            "sample": sample[:15],
        }
    except Exception:
        return None


def main() -> None:
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m data.rag index [key=value ...] | search <query> | search-stages <query> | verify")
        return
    cmd = sys.argv[1].lower()
    if cmd == "verify":
        info = verify_chroma_embedding()
        if info is None:
            print("Chroma 벡터 DB를 열 수 없습니다. python -m data.rag index status=active 를 먼저 실행하세요.")
            return
        print("=== Chroma 임베딩 검증 ===\n")
        print(f"총 청크 수: {info['total']}\n")
        print("카테고리(collection)별 청크 수:")
        for col, n in info["by_collection"].items():
            print(f"  {col}: {n}")
        print("\n파일(path)별 청크 수:")
        for path, n in sorted(info["by_path"].items(), key=lambda x: -x[1])[:30]:
            print(f"  {n:3d}  {path}")
        if len(info["by_path"]) > 30:
            print(f"  ... 외 {len(info['by_path']) - 30}개 파일")
        print("\n카테고리별 샘플 청크(앞 120자):")
        for s in info["sample"]:
            print(f"  [{s['collection']}] {s['path']} (chunk {s.get('chunk_index')})")
            print(f"    {s['content_preview']}")
        return
    if cmd == "index":
        metadata_filter = None
        for arg in sys.argv[2:]:
            if "=" in arg:
                if metadata_filter is None:
                    metadata_filter = {}
                k, v = arg.split("=", 1)
                metadata_filter[k.strip()] = v.strip()
        docs = get_documents(DATA_DIR, metadata_filter=metadata_filter)
        print(f"Documents from manifest (filter={metadata_filter}): {len(docs)}")
        if metadata_filter is None:
            print("(모든 status 적재. Policy Agent는 검색 시 status=active만 사용, Result 챗봇은 전체 검색)")
        indexed = ingest(metadata_filter=metadata_filter)
        print(f"Chunked & embedded: {len(indexed)} vectors -> Chroma {CHROMA_PATH}")
    elif cmd == "search" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        results = search(query, k=5)
        print(f"Query: {query}\nTop {len(results)}:")
        for r in results:
            print(f"  [{r['score']}] id={r['id']} metadata={r.get('metadata')}")
            print(f"    {r['content'][:80]}...")
    elif cmd == "search-stages" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        out = search_in_stages(query, k=5)
        print(f"Query: {query}\nRouted collection: {out['collection']}\nTop {len(out['results'])}:")
        for r in out["results"]:
            print(f"  [{r['score']}] id={r['id']} metadata={r.get('metadata')}")
            print(f"    {r['content'][:80]}...")
    else:
        print("Usage: python -m data.rag index [key=value ...] | search <query> | search-stages <query> | verify")


if __name__ == "__main__":
    main()
