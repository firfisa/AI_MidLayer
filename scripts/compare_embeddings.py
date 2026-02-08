#!/usr/bin/env python3
"""Compare embedding models on the realistic benchmark.

Tests search quality across different embedding models:
- Local (all-MiniLM-L6-v2)
- text-embedding-3-small
- text-embedding-3-large

Usage:
    python scripts/compare_embeddings.py
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.bm25 import BM25Index
from ai_midlayer.knowledge.retriever import Retriever

# Import test data from realistic benchmark
from realistic_benchmark import (
    TECH_DOCS, STUDY_NOTES, PROJECT_DOCS, QA_KNOWLEDGE,
    BENCHMARK_QUERIES
)

console = Console()

# API Config
API_KEY = "sk-sGxBWy5x1n33TZGx7DqtK1KwAvkEx1jKzHatE4fmyVwwopuf"
BASE_URL = "https://www.dmxapi.cn/v1"

# Models to compare
EMBEDDING_MODELS = [
    ("local (MiniLM)", None, None, 384),
    ("text-embedding-3-small", API_KEY, BASE_URL, 1536),
    ("text-embedding-3-large", API_KEY, BASE_URL, 3072),
]


def create_corpus(kb_path: Path, model: str, api_key: str | None, base_url: str | None, dims: int):
    """Create corpus with specified embedding model."""
    docs_dir = kb_path.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    all_docs = {**TECH_DOCS, **STUDY_NOTES, **PROJECT_DOCS, **QA_KNOWLEDGE}
    for filename, content in all_docs.items():
        (docs_dir / filename).write_text(content)
    
    store = FileStore(kb_path)
    vector_index = VectorIndex(
        kb_path,
        embedding_model=model.split()[0] if " " not in model else "all-MiniLM-L6-v2",
        embedding_api_key=api_key,
        embedding_base_url=base_url,
        embedding_dimensions=dims,
    )
    bm25_index = BM25Index(kb_path / "index" / "bm25.db")
    
    for filename in all_docs.keys():
        filepath = docs_dir / filename
        doc_id = store.add_file(filepath)
        doc = store.get_file(doc_id)
        if doc:
            vector_index.index_document(doc)
            bm25_index.index_document(doc)
    
    return store, vector_index, bm25_index


def run_eval(retriever: Retriever, use_hybrid: bool = True) -> dict:
    """Run evaluation and return metrics."""
    total_mrr = 0
    total_p3 = 0
    
    for bq in BENCHMARK_QUERIES:
        results = retriever.retrieve(bq.query, top_k=5, use_hybrid=use_hybrid)
        files = [r.chunk.metadata.get("file_name", "") for r in results]
        
        # MRR
        mrr = 0.0
        for i, f in enumerate(files, 1):
            if any(r in f for r in bq.relevant_docs):
                mrr = 1.0 / i
                break
        total_mrr += mrr
        
        # P@3
        hits = sum(1 for f in files[:3] if any(r in f for r in bq.relevant_docs))
        total_p3 += hits / 3
    
    n = len(BENCHMARK_QUERIES)
    return {"mrr": total_mrr / n, "p3": total_p3 / n}


def main():
    console.print(Panel(
        "[bold]🔬 Embedding Model Comparison[/bold]\n\n"
        "Testing search quality across different embedding models.",
        border_style="cyan",
    ))
    
    results = []
    
    for model_name, api_key, base_url, dims in EMBEDDING_MODELS:
        console.print(f"\n[cyan]Testing: {model_name}[/cyan]")
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            kb_path = Path(tmp_dir) / ".midlayer"
            kb_path.mkdir(parents=True)
            
            try:
                # Create corpus
                with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
                    task = p.add_task(f"Indexing with {model_name}...")
                    store, vector_index, bm25_index = create_corpus(kb_path, model_name, api_key, base_url, dims)
                    p.update(task, description="Indexing complete")
                
                # Hybrid search
                hybrid_retriever = Retriever(store, vector_index, bm25_index)
                hybrid_metrics = run_eval(hybrid_retriever, use_hybrid=True)
                
                # Vector only
                vector_retriever = Retriever(store, vector_index)
                vector_metrics = run_eval(vector_retriever, use_hybrid=False)
                
                results.append({
                    "model": model_name,
                    "hybrid_mrr": hybrid_metrics["mrr"],
                    "hybrid_p3": hybrid_metrics["p3"],
                    "vector_mrr": vector_metrics["mrr"],
                    "vector_p3": vector_metrics["p3"],
                })
                
                console.print(f"  [green]✓ Hybrid MRR: {hybrid_metrics['mrr']:.3f}[/green]")
                console.print(f"  [blue]  Vector MRR: {vector_metrics['mrr']:.3f}[/blue]")
                
            except Exception as e:
                console.print(f"  [red]✗ Error: {e}[/red]")
                results.append({
                    "model": model_name,
                    "hybrid_mrr": 0, "hybrid_p3": 0,
                    "vector_mrr": 0, "vector_p3": 0,
                    "error": str(e),
                })
    
    # Summary table
    console.print("\n")
    table = Table(title="Embedding Model Comparison Results", show_header=True)
    table.add_column("Model", style="cyan")
    table.add_column("Hybrid MRR", justify="right")
    table.add_column("Vector MRR", justify="right")
    table.add_column("Hybrid P@3", justify="right")
    table.add_column("Vector P@3", justify="right")
    
    best_hybrid = max(results, key=lambda x: x["hybrid_mrr"])
    best_vector = max(results, key=lambda x: x["vector_mrr"])
    
    for r in results:
        h_mrr = f"{r['hybrid_mrr']:.3f}"
        v_mrr = f"{r['vector_mrr']:.3f}"
        if r == best_hybrid:
            h_mrr = f"[green bold]{h_mrr} ★[/green bold]"
        if r == best_vector:
            v_mrr = f"[blue bold]{v_mrr} ★[/blue bold]"
        
        table.add_row(
            r["model"],
            h_mrr,
            v_mrr,
            f"{r['hybrid_p3']:.3f}",
            f"{r['vector_p3']:.3f}",
        )
    
    console.print(table)
    
    console.print("\n[bold]结论:[/bold]")
    console.print(f"  🏆 [green]Hybrid 最佳模型: {best_hybrid['model']}[/green]")
    console.print(f"  🏆 [blue]Vector 最佳模型: {best_vector['model']}[/blue]")


if __name__ == "__main__":
    main()
