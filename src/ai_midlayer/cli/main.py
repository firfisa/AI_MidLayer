"""CLI main entry point for AI MidLayer."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.retriever import Retriever

app = typer.Typer(
    name="midlayer",
    help="AI MidLayer - Transform messy project files into high-quality LLM context",
    add_completion=False,
)
console = Console()

# Default knowledge base path
DEFAULT_KB_PATH = ".midlayer"


def get_store(kb_path: str | None = None) -> FileStore:
    """Get or create a file store."""
    path = kb_path or DEFAULT_KB_PATH
    return FileStore(path)


def get_index(kb_path: str | None = None) -> VectorIndex:
    """Get or create a vector index."""
    path = kb_path or DEFAULT_KB_PATH
    return VectorIndex(path)


def get_retriever(kb_path: str | None = None) -> Retriever:
    """Get or create a retriever."""
    path = kb_path or DEFAULT_KB_PATH
    return Retriever(get_store(path), get_index(path))


@app.command()
def init(
    path: Optional[str] = typer.Option(
        None, "--path", "-p", help="Path to initialize the knowledge base"
    )
):
    """Initialize a new project knowledge base."""
    kb_path = path or DEFAULT_KB_PATH
    store = FileStore(kb_path)
    index = VectorIndex(kb_path)
    
    console.print(f"✅ Knowledge base initialized at [bold]{kb_path}[/bold]")
    console.print("\nNext steps:")
    console.print("  1. Add files: [cyan]midlayer add <file>[/cyan]")
    console.print("  2. Search: [cyan]midlayer search <query>[/cyan]")


@app.command()
def add(
    file_path: str = typer.Argument(..., help="Path to file to add"),
    kb_path: Optional[str] = typer.Option(None, "--kb", help="Knowledge base path"),
):
    """Add a file to the knowledge base and index it."""
    path = Path(file_path)
    
    if not path.exists():
        console.print(f"❌ File not found: {file_path}", style="red")
        raise typer.Exit(1)
    
    store = get_store(kb_path)
    index = get_index(kb_path)
    
    if path.is_dir():
        # Add all files in directory
        count = 0
        chunks_total = 0
        for f in path.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                try:
                    doc_id = store.add_file(f)
                    doc = store.get_file(doc_id)
                    if doc:
                        num_chunks = index.index_document(doc)
                        chunks_total += num_chunks
                    console.print(f"  ✓ Added: {f.name} ({doc_id[:8]}, {num_chunks} chunks)")
                    count += 1
                except Exception as e:
                    console.print(f"  ✗ Failed: {f.name} - {e}", style="yellow")
        console.print(f"\n✅ Added {count} files ({chunks_total} chunks indexed)")
    else:
        doc_id = store.add_file(path)
        doc = store.get_file(doc_id)
        num_chunks = 0
        if doc:
            num_chunks = index.index_document(doc)
        console.print(f"✅ Added: {path.name} (ID: {doc_id[:8]}..., {num_chunks} chunks)")


@app.command()
def status(
    kb_path: Optional[str] = typer.Option(None, "--kb", help="Knowledge base path"),
):
    """Show knowledge base status."""
    store = get_store(kb_path)
    index = get_index(kb_path)
    files = store.list_files()
    stats = index.get_stats()
    
    if not files:
        console.print("📭 Knowledge base is empty. Add files with [cyan]midlayer add <file>[/cyan]")
        return
    
    console.print(f"📊 [bold]Index Stats[/bold]: {stats['total_chunks']} chunks from {stats['total_documents']} documents\n")
    
    table = Table(title=f"Knowledge Base ({len(files)} files)")
    table.add_column("ID", style="dim")
    table.add_column("File Name")
    table.add_column("Type")
    table.add_column("Added")
    
    for f in files:
        table.add_row(
            f["id"][:8] + "...",
            f["file_name"],
            f["file_type"],
            f.get("created_at", "")[:10],
        )
    
    console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    kb_path: Optional[str] = typer.Option(None, "--kb", help="Knowledge base path"),
    limit: int = typer.Option(5, "--limit", "-n", help="Number of results"),
):
    """Search the knowledge base using semantic similarity."""
    console.print(f"🔍 Searching for: [bold]{query}[/bold]\n")
    
    retriever = get_retriever(kb_path)
    results = retriever.retrieve(query, top_k=limit)
    
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        console.print("  Try adding more files with [cyan]midlayer add <file>[/cyan]")
        return
    
    for i, result in enumerate(results, 1):
        file_name = result.chunk.metadata.get("file_name", "unknown")
        score = f"{result.score:.2f}"
        
        panel = Panel(
            result.chunk.content[:500] + ("..." if len(result.chunk.content) > 500 else ""),
            title=f"[{i}] {file_name} (score: {score})",
            subtitle=f"chars {result.chunk.start_idx}-{result.chunk.end_idx}",
            border_style="blue",
        )
        console.print(panel)


@app.command()
def remove(
    doc_id: str = typer.Argument(..., help="Document ID to remove"),
    kb_path: Optional[str] = typer.Option(None, "--kb", help="Knowledge base path"),
):
    """Remove a file from the knowledge base."""
    store = get_store(kb_path)
    index = get_index(kb_path)
    
    # Remove from index first
    index.remove_document(doc_id)
    
    if store.remove_file(doc_id):
        console.print(f"✅ Removed document: {doc_id[:8]}...")
    else:
        console.print(f"❌ Document not found: {doc_id}", style="red")


if __name__ == "__main__":
    app()

