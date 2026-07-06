from pathlib import Path

from config import CHROMA_COLLECTION_NAME, INPUT_DIR


SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md"}


def collect_input_files(input_dir: Path):
    return [
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]


def main():
    files = collect_input_files(INPUT_DIR)
    if not files:
        print(f"No documents found in: {INPUT_DIR}")
        print("Put PDF, TXT, or MD files into data/input and run this script again.")
        return

    print(f"Found {len(files)} document(s).")
    for path in files:
        print(f"- {path}")

    from retrieval.document_indexer import ingest_files

    added_chunks = ingest_files(files, collection_name=CHROMA_COLLECTION_NAME)
    print(f"Ingestion completed. Added {added_chunks} chunk(s) to collection '{CHROMA_COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()
