#!/usr/bin/env python3
"""Dogfood Test: Use AI MidLayer to search its own codebase.

This script:
1. Creates a temporary knowledge base from project source code
2. Runs evaluation queries comparing Hybrid vs Vector-only search
3. Generates a quality report with metrics

Run: python scripts/dogfood_test.py
"""

import sys
import tempfile
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.bm25 import BM25Index
from ai_midlayer.knowledge.retriever import Retriever


console = Console()


@dataclass
class EvalQuery:
    """A query for evaluation with expected file hints."""
    query: str
    expected_files: list[str]  # Substrings of expected file names
    category: str  # exact_match, semantic, mixed


@dataclass
class SearchResult:
    """Result from a search for comparison."""
    file_name: str
    score: float
    source: str
    content_preview: str


@dataclass
class EvalResult:
    """Evaluation result for a single query."""
    query: str
    category: str
    hybrid_results: list[SearchResult] = field(default_factory=list)
    vector_results: list[SearchResult] = field(default_factory=list)
    hybrid_precision: float = 0.0
    vector_precision: float = 0.0
    hybrid_mrr: float = 0.0  # Mean Reciprocal Rank
    vector_mrr: float = 0.0
    hybrid_time_ms: float = 0.0
    vector_time_ms: float = 0.0


# Evaluation queries with expected file patterns
EVAL_QUERIES = [
    # Exact function/class name matches (BM25 should excel)
    EvalQuery(
        "class LiteLLMClient",
        ["llm.py"],
        "exact_match"
    ),
    EvalQuery(
        "def reciprocal_rank_fusion",
        ["fusion.py"],
        "exact_match"
    ),
    EvalQuery(
        "class BM25Index sqlite",
        ["bm25.py"],
        "exact_match"
    ),
    EvalQuery(
        "searchFTS bm25 score",
        ["bm25.py"],
        "exact_match"
    ),
    
    # Semantic/conceptual queries (Vector should help)
    EvalQuery(
        "retrieve documents find similar chunks embeddings",
        ["retriever.py", "index.py"],
        "semantic"
    ),
    EvalQuery(
        "merge ranked lists combine results from different sources",
        ["fusion.py", "hybrid.py"],
        "semantic"
    ),
    EvalQuery(
        "conversation chat with memory history messages",
        ["rag.py", "query.py"],
        "semantic"
    ),
    
    # Mixed queries (Hybrid should be best)
    EvalQuery(
        "HybridRetriever BM25 vector fusion",
        ["hybrid.py"],
        "mixed"
    ),
    EvalQuery(
        "reranker LLM score relevance",
        ["reranker.py"],
        "mixed"
    ),
    EvalQuery(
        "FileStore add_file document save",
        ["store.py"],
        "mixed"
    ),
]


def index_project_source(kb_path: Path, project_root: Path) -> tuple[FileStore, VectorIndex, BM25Index]:
    """Index all Python files from the project."""
    console.print("\n[bold cyan]📦 Indexing project source code...[/bold cyan]\n")
    
    store = FileStore(kb_path)
    vector_index = VectorIndex(kb_path)
    bm25_index = BM25Index(kb_path / "index" / "bm25.db")
    
    src_dir = project_root / "src"
    py_files = list(src_dir.rglob("*.py"))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing files...", total=len(py_files))
        
        for py_file in py_files:
            if "__pycache__" in str(py_file):
                continue
                
            try:
                doc_id = store.add_file(py_file)
                doc = store.get_file(doc_id)
                if doc:
                    vector_index.index_document(doc)
                    bm25_index.index_document(doc)
                progress.update(task, advance=1, description=f"Indexed: {py_file.name}")
            except Exception as e:
                console.print(f"  [yellow]Skip: {py_file.name} - {e}[/yellow]")
    
    stats = vector_index.get_stats()
    console.print(f"\n[green]✓ Indexed {stats['total_documents']} files, {stats['total_chunks']} chunks[/green]")
    
    return store, vector_index, bm25_index


def run_search(
    retriever: Retriever,
    query: str,
    use_hybrid: bool,
    top_k: int = 5
) -> tuple[list[SearchResult], float]:
    """Run a search and return results with timing."""
    start = time.perf_counter()
    results = retriever.retrieve(query, top_k=top_k, use_hybrid=use_hybrid)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    search_results = []
    for r in results:
        file_name = r.chunk.metadata.get("file_name", "unknown")
        source = r.chunk.metadata.get("search_source", "vector")
        preview = r.chunk.content[:100].replace("\n", " ")
        search_results.append(SearchResult(
            file_name=file_name,
            score=r.score,
            source=source,
            content_preview=preview,
        ))
    
    return search_results, elapsed_ms


def calculate_precision(results: list[SearchResult], expected_files: list[str], k: int = 3) -> float:
    """Calculate Precision@K: fraction of top-k results that match expected files."""
    if not results:
        return 0.0
    
    top_k = results[:k]
    hits = 0
    for r in top_k:
        for expected in expected_files:
            if expected.lower() in r.file_name.lower():
                hits += 1
                break
    
    return hits / min(k, len(top_k))


def calculate_mrr(results: list[SearchResult], expected_files: list[str]) -> float:
    """Calculate Mean Reciprocal Rank: 1/rank of first relevant result."""
    for i, r in enumerate(results, 1):
        for expected in expected_files:
            if expected.lower() in r.file_name.lower():
                return 1.0 / i
    return 0.0


def evaluate_queries(
    store: FileStore,
    vector_index: VectorIndex,
    bm25_index: BM25Index,
) -> list[EvalResult]:
    """Run all evaluation queries and collect metrics."""
    console.print("\n[bold cyan]🔍 Running evaluation queries...[/bold cyan]\n")
    
    # Create retrievers
    hybrid_retriever = Retriever(store, vector_index, bm25_index)
    vector_retriever = Retriever(store, vector_index, bm25_index=None)
    
    results = []
    
    for eq in EVAL_QUERIES:
        console.print(f"  Query: [dim]{eq.query[:50]}...[/dim]")
        
        # Run hybrid search
        hybrid_results, hybrid_time = run_search(hybrid_retriever, eq.query, use_hybrid=True)
        
        # Run vector-only search
        vector_results, vector_time = run_search(vector_retriever, eq.query, use_hybrid=False)
        
        # Calculate metrics
        eval_result = EvalResult(
            query=eq.query,
            category=eq.category,
            hybrid_results=hybrid_results,
            vector_results=vector_results,
            hybrid_precision=calculate_precision(hybrid_results, eq.expected_files),
            vector_precision=calculate_precision(vector_results, eq.expected_files),
            hybrid_mrr=calculate_mrr(hybrid_results, eq.expected_files),
            vector_mrr=calculate_mrr(vector_results, eq.expected_files),
            hybrid_time_ms=hybrid_time,
            vector_time_ms=vector_time,
        )
        results.append(eval_result)
    
    return results


def print_detailed_results(results: list[EvalResult]):
    """Print detailed results for each query."""
    console.print("\n[bold cyan]📊 Detailed Query Results[/bold cyan]\n")
    
    for i, r in enumerate(results, 1):
        # Determine winner
        if r.hybrid_precision > r.vector_precision:
            winner = "[green]Hybrid ✓[/green]"
        elif r.vector_precision > r.hybrid_precision:
            winner = "[blue]Vector ✓[/blue]"
        else:
            winner = "[yellow]Tie[/yellow]"
        
        console.print(Panel(
            f"[bold]Query:[/bold] {r.query}\n"
            f"[dim]Category: {r.category} | Winner: {winner}[/dim]\n\n"
            f"[green]Hybrid[/green] P@3: {r.hybrid_precision:.2f} | MRR: {r.hybrid_mrr:.2f} | Time: {r.hybrid_time_ms:.1f}ms\n"
            f"[blue]Vector[/blue] P@3: {r.vector_precision:.2f} | MRR: {r.vector_mrr:.2f} | Time: {r.vector_time_ms:.1f}ms",
            title=f"[{i}] {r.category.upper()}",
            border_style="dim",
        ))
        
        # Show top 3 results comparison
        table = Table(show_header=True, header_style="bold")
        table.add_column("Rank", width=5)
        table.add_column("Hybrid Result", width=35)
        table.add_column("Vector Result", width=35)
        
        for j in range(3):
            h_file = r.hybrid_results[j].file_name if j < len(r.hybrid_results) else "-"
            h_score = f"({r.hybrid_results[j].score:.2f})" if j < len(r.hybrid_results) else ""
            v_file = r.vector_results[j].file_name if j < len(r.vector_results) else "-"
            v_score = f"({r.vector_results[j].score:.2f})" if j < len(r.vector_results) else ""
            
            table.add_row(str(j + 1), f"{h_file} {h_score}", f"{v_file} {v_score}")
        
        console.print(table)
        console.print()


def print_summary_report(results: list[EvalResult]):
    """Print summary metrics by category."""
    console.print("\n[bold cyan]📈 Summary Report[/bold cyan]\n")
    
    # Group by category
    categories = {}
    for r in results:
        if r.category not in categories:
            categories[r.category] = []
        categories[r.category].append(r)
    
    # Overall metrics
    all_hybrid_p = sum(r.hybrid_precision for r in results) / len(results)
    all_vector_p = sum(r.vector_precision for r in results) / len(results)
    all_hybrid_mrr = sum(r.hybrid_mrr for r in results) / len(results)
    all_vector_mrr = sum(r.vector_mrr for r in results) / len(results)
    all_hybrid_time = sum(r.hybrid_time_ms for r in results) / len(results)
    all_vector_time = sum(r.vector_time_ms for r in results) / len(results)
    
    # Summary table
    table = Table(title="Search Quality Comparison", show_header=True, header_style="bold")
    table.add_column("Category", style="cyan")
    table.add_column("Hybrid P@3", justify="right")
    table.add_column("Vector P@3", justify="right")
    table.add_column("Hybrid MRR", justify="right")
    table.add_column("Vector MRR", justify="right")
    table.add_column("Winner", justify="center")
    
    for cat, cat_results in categories.items():
        h_p = sum(r.hybrid_precision for r in cat_results) / len(cat_results)
        v_p = sum(r.vector_precision for r in cat_results) / len(cat_results)
        h_mrr = sum(r.hybrid_mrr for r in cat_results) / len(cat_results)
        v_mrr = sum(r.vector_mrr for r in cat_results) / len(cat_results)
        
        if h_p > v_p:
            winner = "[green]Hybrid[/green]"
        elif v_p > h_p:
            winner = "[blue]Vector[/blue]"
        else:
            winner = "[yellow]Tie[/yellow]"
        
        table.add_row(
            cat,
            f"{h_p:.2f}",
            f"{v_p:.2f}",
            f"{h_mrr:.2f}",
            f"{v_mrr:.2f}",
            winner,
        )
    
    # Overall row
    if all_hybrid_p > all_vector_p:
        overall_winner = "[green bold]Hybrid[/green bold]"
    elif all_vector_p > all_hybrid_p:
        overall_winner = "[blue bold]Vector[/blue bold]"
    else:
        overall_winner = "[yellow bold]Tie[/yellow bold]"
    
    table.add_row(
        "[bold]OVERALL[/bold]",
        f"[bold]{all_hybrid_p:.2f}[/bold]",
        f"[bold]{all_vector_p:.2f}[/bold]",
        f"[bold]{all_hybrid_mrr:.2f}[/bold]",
        f"[bold]{all_vector_mrr:.2f}[/bold]",
        overall_winner,
    )
    
    console.print(table)
    
    # Performance
    console.print(f"\n[dim]⏱️  Avg Latency: Hybrid {all_hybrid_time:.1f}ms | Vector {all_vector_time:.1f}ms[/dim]")
    
    # Interpretation
    console.print("\n[bold]📝 Interpretation:[/bold]")
    console.print("""
- **P@3 (Precision@3)**: Fraction of top-3 results that match expected files (higher = better)
- **MRR (Mean Reciprocal Rank)**: 1/rank of first relevant result (higher = better)

[bold green]✓ Hybrid should win on exact_match[/bold green] - BM25 excels at precise keyword matching
[bold blue]✓ Vector may win on semantic[/bold blue] - Embedding captures meaning better
[bold yellow]✓ Mixed queries benefit from fusion[/bold yellow] - Best of both worlds
""")


def main():
    """Run the dogfood test."""
    console.print(Panel(
        "[bold]🐕 AI MidLayer Dogfood Test[/bold]\n\n"
        "Testing hybrid search quality using the project's own source code.\n"
        "Compares Hybrid (BM25+Vector) vs Vector-only search.",
        border_style="cyan",
    ))
    
    project_root = Path(__file__).parent.parent
    
    # Use temporary directory for test KB
    with tempfile.TemporaryDirectory() as tmp_dir:
        kb_path = Path(tmp_dir) / ".midlayer"
        kb_path.mkdir(parents=True)
        
        # Index project source
        store, vector_index, bm25_index = index_project_source(kb_path, project_root)
        
        # Run evaluation
        results = evaluate_queries(store, vector_index, bm25_index)
        
        # Print results
        print_detailed_results(results)
        print_summary_report(results)
    
    console.print("\n[green bold]✓ Dogfood test complete![/green bold]\n")


if __name__ == "__main__":
    main()
