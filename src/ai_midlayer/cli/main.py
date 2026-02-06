"""CLI main entry point for AI MidLayer."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ai_midlayer.knowledge.store import FileStore

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


@app.command()
def init(
    path: Optional[str] = typer.Option(
        None, "--path", "-p", help="Path to initialize the knowledge base"
    )
):
    """Initialize a new project knowledge base."""
    kb_path = path or DEFAULT_KB_PATH
    store = FileStore(kb_path)
    
    console.print(f"✅ Knowledge base initialized at [bold]{kb_path}[/bold]")
    console.print("\nNext steps:")
    console.print("  1. Add files: [cyan]midlayer add <file>[/cyan]")
    console.print("  2. Search: [cyan]midlayer search <query>[/cyan]")


@app.command()
def add(
    file_path: str = typer.Argument(..., help="Path to file to add"),
    kb_path: Optional[str] = typer.Option(None, "--kb", help="Knowledge base path"),
):
    """Add a file to the knowledge base."""
    path = Path(file_path)
    
    if not path.exists():
        console.print(f"❌ File not found: {file_path}", style="red")
        raise typer.Exit(1)
    
    store = get_store(kb_path)
    
    if path.is_dir():
        # Add all files in directory
        count = 0
        for f in path.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                try:
                    doc_id = store.add_file(f)
                    console.print(f"  ✓ Added: {f.name} ({doc_id[:8]})")
                    count += 1
                except Exception as e:
                    console.print(f"  ✗ Failed: {f.name} - {e}", style="yellow")
        console.print(f"\n✅ Added {count} files")
    else:
        doc_id = store.add_file(path)
        console.print(f"✅ Added: {path.name} (ID: {doc_id[:8]}...)")


@app.command()
def status(
    kb_path: Optional[str] = typer.Option(None, "--kb", help="Knowledge base path"),
):
    """Show knowledge base status."""
    store = get_store(kb_path)
    files = store.list_files()
    
    if not files:
        console.print("📭 Knowledge base is empty. Add files with [cyan]midlayer add <file>[/cyan]")
        return
    
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
    """Search the knowledge base."""
    console.print(f"🔍 Searching for: [bold]{query}[/bold]\n")
    console.print("[yellow]⚠️ Vector search not yet implemented (Step 3)[/yellow]")
    console.print("  Use [cyan]midlayer status[/cyan] to see available files")


@app.command()
def remove(
    doc_id: str = typer.Argument(..., help="Document ID to remove"),
    kb_path: Optional[str] = typer.Option(None, "--kb", help="Knowledge base path"),
):
    """Remove a file from the knowledge base."""
    store = get_store(kb_path)
    
    if store.remove_file(doc_id):
        console.print(f"✅ Removed document: {doc_id[:8]}...")
    else:
        console.print(f"❌ Document not found: {doc_id}", style="red")


if __name__ == "__main__":
    app()
