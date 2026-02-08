"""CLI main entry point for AI MidLayer."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.retriever import Retriever
from ai_midlayer.config import Config, get_config
from ai_midlayer.llm import LiteLLMClient
from ai_midlayer.rag import RAGQuery, ConversationRAG

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


def get_bm25_index(kb_path: str | None = None):
    """Get or create a BM25 index for hybrid search."""
    from ai_midlayer.knowledge.bm25 import BM25Index
    path = Path(kb_path or DEFAULT_KB_PATH)
    bm25_db = path / "index" / "bm25.db"
    if bm25_db.exists():
        return BM25Index(bm25_db)
    return None


def get_retriever(kb_path: str | None = None, hybrid: bool = True) -> Retriever:
    """Get or create a retriever.
    
    Args:
        kb_path: Optional knowledge base path.
        hybrid: Whether to enable hybrid search (BM25 + Vector).
    
    Returns:
        Configured Retriever instance.
    """
    path = kb_path or DEFAULT_KB_PATH
    bm25 = get_bm25_index(path) if hybrid else None
    return Retriever(get_store(path), get_index(path), bm25_index=bm25)


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
    console.print("  3. Chat: [cyan]midlayer chat[/cyan]")


@app.command()
def add(
    file_path: str = typer.Argument(..., help="Path to file to add"),
    kb_path: Optional[str] = typer.Option(None, "--kb", help="Knowledge base path"),
):
    """Add a file to the knowledge base and index it."""
    from ai_midlayer.knowledge.bm25 import BM25Index
    
    path = Path(file_path)
    
    if not path.exists():
        console.print(f"❌ File not found: {file_path}", style="red")
        raise typer.Exit(1)
    
    store = get_store(kb_path)
    index = get_index(kb_path)
    
    # Initialize BM25 index for hybrid search
    kb = Path(kb_path or DEFAULT_KB_PATH)
    bm25_db = kb / "index" / "bm25.db"
    bm25 = BM25Index(bm25_db)
    
    if path.is_dir():
        # Add all files in directory
        count = 0
        vec_chunks = 0
        bm25_chunks = 0
        for f in path.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                try:
                    doc_id = store.add_file(f)
                    doc = store.get_file(doc_id)
                    if doc:
                        nv = index.index_document(doc)
                        nb = bm25.index_document(doc)
                        vec_chunks += nv
                        bm25_chunks += nb
                    console.print(f"  ✓ Added: {f.name} ({doc_id[:8]}, {nv}v/{nb}b chunks)")
                    count += 1
                except Exception as e:
                    console.print(f"  ✗ Failed: {f.name} - {e}", style="yellow")
        console.print(f"\n✅ Added {count} files (Vector: {vec_chunks}, BM25: {bm25_chunks})")
    else:
        doc_id = store.add_file(path)
        doc = store.get_file(doc_id)
        num_vec = 0
        num_bm25 = 0
        if doc:
            num_vec = index.index_document(doc)
            num_bm25 = bm25.index_document(doc)
        console.print(f"✅ Added: {path.name} (ID: {doc_id[:8]}..., Vec: {num_vec}, BM25: {num_bm25})")


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
    hybrid: bool = typer.Option(True, "--hybrid/--no-hybrid", help="Use hybrid search (BM25 + Vector)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed search info"),
):
    """Search the knowledge base using hybrid or semantic search."""
    retriever = get_retriever(kb_path, hybrid=hybrid)
    
    # Determine search mode label
    mode_label = "[green]hybrid[/green]" if retriever.hybrid_enabled else "[blue]vector[/blue]"
    console.print(f"🔍 Searching ({mode_label}): [bold]{query}[/bold]\n")
    
    results = retriever.retrieve(query, top_k=limit)
    
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        console.print("  Try adding more files with [cyan]midlayer add <file>[/cyan]")
        return
    
    for i, result in enumerate(results, 1):
        file_name = result.chunk.metadata.get("file_name", "unknown")
        score = f"{result.score:.2f}"
        source = result.chunk.metadata.get("search_source", "vector")
        
        # Build title with source info
        if verbose:
            rrf_score = result.chunk.metadata.get("rrf_score")
            sources = result.chunk.metadata.get("sources", "")
            if rrf_score:
                title = f"[{i}] {file_name} (rrf: {rrf_score:.3f}, via: {sources})"
            else:
                title = f"[{i}] {file_name} (score: {score}, source: {source})"
        else:
            title = f"[{i}] {file_name} (score: {score})"
        
        # Color based on source
        if "bm25" in source:
            border_style = "yellow"
        elif "hybrid" in source:
            border_style = "green"
        else:
            border_style = "blue"
        
        panel = Panel(
            result.chunk.content[:500] + ("..." if len(result.chunk.content) > 500 else ""),
            title=title,
            subtitle=f"chars {result.chunk.start_idx}-{result.chunk.end_idx}",
            border_style=border_style,
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


@app.command()
def chat(
    kb_path: Optional[str] = typer.Option(None, "--kb", help="Knowledge base path"),
    single: Optional[str] = typer.Option(None, "--query", "-q", help="Single query mode"),
):
    """Interactive RAG chat with the knowledge base."""
    # Load config
    config = get_config()
    
    # Check if LLM is configured
    if not config.llm.api_key:
        console.print("[red]❌ LLM not configured.[/red]")
        console.print("\nSet environment variables:")
        console.print("  export MIDLAYER_LLM_PROVIDER=custom")
        console.print("  export MIDLAYER_LLM_MODEL=deepseek-chat")
        console.print("  export MIDLAYER_BASE_URL=https://api.deepseek.com")
        console.print("  export MIDLAYER_API_KEY=your-api-key")
        raise typer.Exit(1)
    
    # Initialize components
    retriever = get_retriever(kb_path)
    llm_client = LiteLLMClient(config.llm)
    
    # Check if knowledge base has content
    stats = retriever.index.get_stats()
    if stats["total_chunks"] == 0:
        console.print("[yellow]⚠️ Knowledge base is empty.[/yellow]")
        console.print("  Add files first: [cyan]midlayer add <file>[/cyan]")
        raise typer.Exit(1)
    
    console.print(Panel(
        f"🤖 [bold]AI MidLayer Chat[/bold]\n\n"
        f"Model: {config.llm.model}\n"
        f"Knowledge Base: {stats['total_chunks']} chunks from {stats['total_documents']} docs\n\n"
        f"Type [cyan]exit[/cyan] or [cyan]quit[/cyan] to leave.",
        border_style="green",
    ))
    
    # Single query mode
    if single:
        rag = RAGQuery(retriever, llm_client)
        _process_query(rag, single)
        return
    
    # Interactive mode with proper Unicode support
    # Use prompt_toolkit for better CJK character handling
    try:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.styles import Style
        
        pt_style = Style.from_dict({
            '': '#00ff00 bold',  # Default style
        })
        
        def get_input():
            return pt_prompt("You> ", style=pt_style)
        
        use_prompt_toolkit = True
    except ImportError:
        # Fallback to Rich.Prompt if prompt_toolkit not available
        use_prompt_toolkit = False
        console.print("[dim]Tip: Install prompt_toolkit for better Chinese input: pip install prompt_toolkit[/dim]")
    
    conversation = ConversationRAG(retriever, llm_client)
    
    while True:
        try:
            if use_prompt_toolkit:
                console.print()  # Empty line before prompt
                query = get_input()
            else:
                query = Prompt.ask("\n[bold cyan]You[/bold cyan]")
            
            if query.lower() in ["exit", "quit", "q"]:
                console.print("[dim]Goodbye! 👋[/dim]")
                break
            
            if query.lower() == "clear":
                conversation.clear_history()
                console.print("[dim]History cleared.[/dim]")
                continue
            
            if not query.strip():
                continue
            
            # Process query
            with console.status("[bold green]Thinking..."):
                result = conversation.chat(query)
            
            # Display answer
            console.print(f"\n[bold green]Assistant[/bold green]")
            console.print(Markdown(result.answer))
            
            # Display sources
            if result.sources:
                sources = ", ".join(set(s.file_name for s in result.sources[:3]))
                console.print(f"\n[dim]📚 Sources: {sources}[/dim]")
                
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Type 'exit' to quit.[/dim]")
        except EOFError:
            console.print("\n[dim]Goodbye! 👋[/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def _process_query(rag: RAGQuery, query: str):
    """Process a single RAG query."""
    with console.status("[bold green]Searching and generating..."):
        result = rag.query(query)
    
    console.print(f"\n[bold green]Answer[/bold green]")
    console.print(Markdown(result.answer))
    
    if result.sources:
        console.print(f"\n[bold]📚 Sources:[/bold]")
        for i, src in enumerate(result.sources[:5], 1):
            console.print(f"  {i}. {src.file_name} (score: {src.score:.2f})")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
    kb_path: Optional[str] = typer.Option(None, "--kb", help="Knowledge base path"),
):
    """Ask a single question (non-interactive RAG query)."""
    config = get_config()
    
    if not config.llm.api_key:
        console.print("[red]❌ LLM not configured. See 'midlayer chat --help'[/red]")
        raise typer.Exit(1)
    
    retriever = get_retriever(kb_path)
    llm_client = LiteLLMClient(config.llm)
    rag = RAGQuery(retriever, llm_client)
    
    _process_query(rag, question)


if __name__ == "__main__":
    app()


