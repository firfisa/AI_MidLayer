#!/usr/bin/env python3
"""Realistic RAG Benchmark: Simulates real work/study scenarios.

This benchmark creates synthetic documents across 4 common use cases:
1. Technical Documentation (API docs, how-to guides)
2. Study Notes (course notes, research summaries)
3. Project Documents (meeting notes, specs, decisions)
4. Q&A Knowledge Base (FAQs, troubleshooting)

Then evaluates search quality with realistic queries.

Run: python scripts/realistic_benchmark.py
"""

import sys
import tempfile
import time
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.bm25 import BM25Index
from ai_midlayer.knowledge.retriever import Retriever
from ai_midlayer.knowledge.models import Document


console = Console()


# =============================================================================
# SYNTHETIC DOCUMENT CORPUS
# =============================================================================

TECH_DOCS = {
    "api_authentication.md": """# API Authentication Guide

## Overview
Our API uses OAuth 2.0 for authentication. All requests must include a valid access token.

## Getting Started

### Step 1: Register Your Application
1. Go to https://developer.example.com/apps
2. Click "Create New App"
3. Fill in your app details
4. Note your `client_id` and `client_secret`

### Step 2: Obtain Access Token

```python
import requests

response = requests.post('https://api.example.com/oauth/token', data={
    'grant_type': 'client_credentials',
    'client_id': 'YOUR_CLIENT_ID',
    'client_secret': 'YOUR_CLIENT_SECRET'
})
access_token = response.json()['access_token']
```

### Step 3: Make Authenticated Requests

Include the token in the Authorization header:
```
Authorization: Bearer <access_token>
```

## Token Expiration
Access tokens expire after 1 hour. Use refresh tokens to obtain new access tokens.

## Rate Limits
- 1000 requests per hour for free tier
- 10000 requests per hour for paid tier
""",
    
    "database_migration.md": """# Database Migration Guide

## Overview
This guide explains how to safely migrate your database schema.

## Before You Begin
1. Backup your database
2. Test migrations on staging first
3. Schedule during low-traffic periods

## Creating a Migration

```bash
# Create a new migration file
python manage.py makemigrations --name add_user_profile

# Review the generated SQL
python manage.py sqlmigrate app_name 0001
```

## Running Migrations

```bash
# Apply all pending migrations
python manage.py migrate

# Apply specific migration
python manage.py migrate app_name 0001
```

## Rollback Strategy
To rollback a migration:
```bash
python manage.py migrate app_name 0000_previous_migration
```

## Best Practices
- Keep migrations small and focused
- Never edit applied migrations
- Use data migrations for data changes
- Test rollback procedures regularly
""",

    "error_codes.md": """# API Error Codes Reference

## HTTP Status Codes

### 4xx Client Errors

| Code | Name | Description |
|------|------|-------------|
| 400 | Bad Request | The request was malformed or missing required fields |
| 401 | Unauthorized | Authentication required or token expired |
| 403 | Forbidden | You don't have permission to access this resource |
| 404 | Not Found | The requested resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded, slow down |

### 5xx Server Errors

| Code | Name | Description |
|------|------|-------------|
| 500 | Internal Server Error | Something went wrong on our end |
| 502 | Bad Gateway | Upstream service unavailable |
| 503 | Service Unavailable | Server is temporarily down |

## Application Error Codes

| Code | Message | Solution |
|------|---------|----------|
| E001 | Invalid email format | Check email is valid format |
| E002 | Password too weak | Use 8+ chars with numbers and symbols |
| E003 | Username already exists | Choose a different username |
| E004 | Session expired | Log in again to get new session |
| E005 | Payment declined | Check card details or try another card |
""",
}

STUDY_NOTES = {
    "machine_learning_basics.md": """# Machine Learning Fundamentals

## What is Machine Learning?
Machine Learning (ML) is a subset of artificial intelligence that enables systems 
to learn and improve from experience without being explicitly programmed.

## Types of Machine Learning

### 1. Supervised Learning
- Training data includes labels (correct answers)
- Goal: Learn mapping from inputs to outputs
- Examples: Classification, Regression
- Algorithms: Linear Regression, Decision Trees, SVM, Neural Networks

### 2. Unsupervised Learning  
- Training data has no labels
- Goal: Find hidden patterns in data
- Examples: Clustering, Dimensionality Reduction
- Algorithms: K-Means, PCA, Autoencoders

### 3. Reinforcement Learning
- Agent learns by interacting with environment
- Goal: Maximize cumulative reward
- Examples: Game playing, Robotics
- Algorithms: Q-Learning, Policy Gradient

## Key Concepts

### Training vs Testing
- Training set: Used to learn model parameters
- Validation set: Used to tune hyperparameters
- Test set: Used to evaluate final performance

### Overfitting vs Underfitting
- Overfitting: Model too complex, memorizes training data
- Underfitting: Model too simple, can't capture patterns
- Solution: Regularization, more data, cross-validation

### Bias-Variance Tradeoff
- High bias = underfitting
- High variance = overfitting
- Goal: Find optimal balance
""",

    "python_decorators.md": """# Python Decorators Deep Dive

## What are Decorators?
Decorators are functions that modify the behavior of other functions or classes.
They use the @syntax and are a form of metaprogramming.

## Basic Decorator Pattern

```python
def my_decorator(func):
    def wrapper(*args, **kwargs):
        print("Before function call")
        result = func(*args, **kwargs)
        print("After function call")
        return result
    return wrapper

@my_decorator
def greet(name):
    print(f"Hello, {name}!")

greet("World")  # Prints: Before, Hello World, After
```

## Common Use Cases

### 1. Timing Functions
```python
import time

def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"{func.__name__} took {time.time() - start:.2f}s")
        return result
    return wrapper
```

### 2. Caching Results
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```

### 3. Authentication Check
```python
def require_auth(func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionError("Login required")
        return func(request, *args, **kwargs)
    return wrapper
```

## Decorator with Arguments
```python
def repeat(times):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for _ in range(times):
                func(*args, **kwargs)
        return wrapper
    return decorator

@repeat(3)
def say_hello():
    print("Hello!")
```
""",

    "docker_containers.md": """# Docker Container Essentials

## What is Docker?
Docker is a platform for developing, shipping, and running applications in containers.
Containers are lightweight, isolated environments that package code with dependencies.

## Key Concepts

### Images vs Containers
- **Image**: Read-only template with instructions to create container
- **Container**: Running instance of an image

### Dockerfile
Blueprint for building images:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

## Common Commands

```bash
# Build image
docker build -t myapp:latest .

# Run container
docker run -d -p 8080:80 myapp:latest

# List running containers
docker ps

# View logs
docker logs <container_id>

# Stop container
docker stop <container_id>

# Remove container
docker rm <container_id>
```

## Docker Compose
For multi-container applications:
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8080:80"
  db:
    image: postgres:14
    environment:
      POSTGRES_PASSWORD: secret
```

Run with: `docker-compose up -d`
""",
}

PROJECT_DOCS = {
    "sprint_planning_2024_q1.md": """# Sprint Planning - Q1 2024

## Sprint 12 (Jan 15 - Jan 29)

### Goals
- Complete user authentication refactor
- Launch beta version of mobile app
- Fix critical dashboard performance issues

### Team Assignments

#### Backend Team
- Sarah: OAuth2 integration with Google/GitHub
- Mike: API rate limiting implementation  
- Lisa: Database query optimization

#### Frontend Team
- John: New login/signup flow UI
- Emma: Dashboard charts performance
- Alex: Mobile responsive fixes

### Story Points
- Total capacity: 45 points
- Committed: 42 points
- Buffer: 3 points

### Key Dependencies
- Marketing needs beta build by Jan 25
- Security review required before OAuth launch
- QA needs 3 days for regression testing

### Risks
1. OAuth integration might take longer (mitigation: start early)
2. Mobile build might have iOS issues (mitigation: daily testing)

## Retrospective Notes (Sprint 11)
- What went well: Great collaboration on API redesign
- What didn't: Too many context switches
- Action items: Stricter meeting schedule, no-meeting Wednesday
""",

    "architecture_decision_001.md": """# ADR 001: Choosing a Message Queue

## Status
Accepted

## Context
We need a message queue to handle async job processing for:
- Email notifications
- Report generation
- Data synchronization with third-party services

Current approach (synchronous) causes timeout issues and poor UX.

## Decision
We will use **Redis** with **Celery** for our message queue.

## Alternatives Considered

### Option A: RabbitMQ
- Pros: Full-featured, AMQP support, great reliability
- Cons: More complex setup, higher memory usage

### Option B: Amazon SQS
- Pros: Fully managed, auto-scaling, reliable
- Cons: Vendor lock-in, higher latency, limited features

### Option C: Redis + Celery (Chosen)
- Pros: Simple setup, fast, already using Redis for caching
- Cons: Less durable than RabbitMQ for critical messages

## Rationale
1. We already have Redis in our stack for caching
2. Most of our jobs are not mission-critical (can retry)
3. Celery has excellent Python integration
4. Simpler operations for our small team

## Consequences
- Need to set up Redis persistence for reliability
- Need to implement retry logic for failed jobs
- Will need to monitor queue depth

## Related Decisions
- ADR 002: Implementing job retry strategy
- ADR 003: Queue monitoring and alerting
""",

    "meeting_notes_product_sync.md": """# Product Sync Meeting - February 5, 2024

## Attendees
- PM: Jessica Chen
- Design: Marcus Lee
- Engineering: Sarah Kim, David Park
- QA: Rachel Green

## Agenda
1. Q1 feature prioritization
2. User feedback review
3. Technical debt discussion

## Discussion Summary

### Feature Prioritization
Jessica presented updated priorities based on user research:

1. **High Priority (Must have Q1)**
   - Dark mode support
   - Export to PDF/CSV
   - Two-factor authentication

2. **Medium Priority (Nice to have)**
   - Keyboard shortcuts
   - Email digest settings
   - Advanced search filters

3. **Low Priority (Q2+)**
   - Mobile app widgets
   - Desktop notifications
   - AI-powered suggestions

### User Feedback Themes
Marcus shared insights from 50 user interviews:
- Users love the clean interface
- Main pain point: slow search on large datasets
- Feature request: bulk actions for multiple items

### Technical Debt
Sarah flagged these issues:
- Legacy API endpoints need deprecation
- Test coverage is at 60%, target is 80%
- Need to upgrade from Python 3.9 to 3.11

## Action Items
| Owner | Action | Due Date |
|-------|--------|----------|
| Sarah | Create tech debt tickets in Jira | Feb 7 |
| Marcus | Share user interview summary | Feb 8 |
| David | Prototype dark mode toggle | Feb 12 |
| Jessica | Update roadmap in Confluence | Feb 9 |

## Next Meeting
February 12, 2024 at 2 PM PST
""",
}

QA_KNOWLEDGE = {
    "troubleshooting_login.md": """# Troubleshooting: Login Issues

## Common Problems and Solutions

### Problem: "Invalid credentials" error
**Cause**: Wrong email or password

**Solutions**:
1. Check that Caps Lock is off
2. Verify you're using the correct email address
3. Try the "Forgot Password" link to reset your password
4. Check if your account has been deactivated

### Problem: "Account locked" message
**Cause**: Too many failed login attempts (5+)

**Solutions**:
1. Wait 30 minutes for automatic unlock
2. Contact support@example.com for immediate unlock
3. Use password reset to regain access

### Problem: Two-factor authentication not working
**Cause**: Code expired or device time out of sync

**Solutions**:
1. Wait for new code (codes expire in 30 seconds)
2. Sync your phone's time to automatic
3. Use backup codes if available
4. Contact support for 2FA reset

### Problem: "Session expired" errors
**Cause**: Login session timed out after inactivity

**Solutions**:
1. Log in again
2. Enable "Remember me" for longer sessions
3. Check browser isn't blocking cookies

### Problem: SSO login redirect failing
**Cause**: Corporate firewall or SSO misconfiguration

**Solutions**:
1. Try a different browser
2. Disable VPN temporarily
3. Contact your IT department
4. Use direct login instead of SSO
""",

    "faq_billing.md": """# Billing FAQ

## Subscription Questions

### Q: How do I upgrade my plan?
A: Go to Settings > Billing > Change Plan. Select your new plan and confirm.
Your new features will be available immediately.

### Q: Can I downgrade my subscription?
A: Yes. Changes take effect at the next billing cycle. 
You keep premium features until the current period ends.

### Q: How do I cancel my subscription?
A: Go to Settings > Billing > Cancel Subscription.
Note: You can still use the service until your paid period ends.

## Payment Questions

### Q: What payment methods do you accept?
A: We accept:
- Credit/debit cards (Visa, Mastercard, Amex)
- PayPal
- Bank transfer (annual plans only)
- Wire transfer (Enterprise)

### Q: Why was my payment declined?
A: Common reasons include:
- Insufficient funds
- Expired card
- Bank security block
- Incorrect billing address
Try updating your payment method or contact your bank.

### Q: How do I get an invoice?
A: Invoices are automatically emailed after each payment.
For past invoices: Settings > Billing > Invoice History

### Q: Do you offer refunds?
A: We offer full refunds within 14 days of purchase.
After 14 days, we provide prorated credits for annual plans.
Monthly plans are non-refundable after the 14-day period.

## Enterprise Questions

### Q: Do you offer volume discounts?
A: Yes, for 50+ seats. Contact sales@example.com

### Q: Can I pay annually?
A: Yes, annual plans save 20% compared to monthly billing.
""",

    "how_to_export_data.md": """# How to Export Your Data

## Available Export Formats

| Format | Best For | File Size |
|--------|----------|-----------|
| CSV | Spreadsheet analysis, Excel | Small-Medium |
| JSON | API integration, developers | Small-Medium |
| PDF | Sharing reports, printing | Medium |
| Excel | Advanced analysis, pivot tables | Medium-Large |

## Step-by-Step Export Guide

### Method 1: Quick Export
1. Go to the data view you want to export
2. Click the **Export** button (top right)
3. Select format (CSV, JSON, PDF, Excel)
4. Click **Download**

### Method 2: Scheduled Export
1. Go to Settings > Data Management
2. Click **Create Export Schedule**
3. Configure:
   - What to export (all data or filtered)
   - Format
   - Frequency (daily, weekly, monthly)
   - Delivery (download link or email)
4. Click **Save Schedule**

### Method 3: API Export
For developers, use our Data Export API:
```bash
curl -X GET "https://api.example.com/v1/export" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept: application/json" \
  -d '{"format": "csv", "date_range": "last_30_days"}'
```

## Export Limits
- Free tier: 1,000 records per export
- Pro tier: 10,000 records per export  
- Enterprise: Unlimited

## Troubleshooting
- **Export taking too long?** Try filtering to smaller date range
- **File won't open?** Check you're using compatible software
- **Missing data?** Check your permissions for those records
""",
}


# =============================================================================
# EVALUATION QUERIES
# =============================================================================

@dataclass
class BenchmarkQuery:
    """A query with ground truth relevance judgments."""
    query: str
    relevant_docs: list[str]  # List of relevant document filenames
    category: str  # tech_docs, study_notes, project_docs, qa_kb
    difficulty: str  # easy (keyword), medium (semantic), hard (complex)


BENCHMARK_QUERIES = [
    # Tech Docs - Easy (keyword matching) 
    BenchmarkQuery(
        "OAuth 2.0 access token authentication",
        ["api_authentication.md"],
        "tech_docs", "easy"
    ),
    BenchmarkQuery(
        "error code 401 unauthorized",
        ["error_codes.md"],
        "tech_docs", "easy"
    ),
    BenchmarkQuery(
        "database migration rollback command",
        ["database_migration.md"],
        "tech_docs", "easy"
    ),
    
    # Tech Docs - Medium (semantic)
    BenchmarkQuery(
        "how to get API credentials for my app",
        ["api_authentication.md"],
        "tech_docs", "medium"
    ),
    BenchmarkQuery(
        "what to do when server returns an error",
        ["error_codes.md"],
        "tech_docs", "medium"
    ),
    
    # Study Notes - Easy
    BenchmarkQuery(
        "supervised learning classification algorithms",
        ["machine_learning_basics.md"],
        "study_notes", "easy"
    ),
    BenchmarkQuery(
        "Python decorator @lru_cache",
        ["python_decorators.md"],
        "study_notes", "easy"
    ),
    BenchmarkQuery(
        "docker build run container",
        ["docker_containers.md"],
        "study_notes", "easy"
    ),
    
    # Study Notes - Medium
    BenchmarkQuery(
        "how to avoid model memorizing training data",
        ["machine_learning_basics.md"],
        "study_notes", "medium"
    ),
    BenchmarkQuery(
        "wrap function to add logging behavior",
        ["python_decorators.md"],
        "study_notes", "medium"
    ),
    
    # Project Docs - Easy
    BenchmarkQuery(
        "sprint 12 team assignments backend",
        ["sprint_planning_2024_q1.md"],
        "project_docs", "easy"
    ),
    BenchmarkQuery(
        "message queue Redis Celery decision",
        ["architecture_decision_001.md"],
        "project_docs", "easy"
    ),
    BenchmarkQuery(
        "product sync meeting action items",
        ["meeting_notes_product_sync.md"],
        "project_docs", "easy"
    ),
    
    # Project Docs - Medium
    BenchmarkQuery(
        "why did we choose Redis over RabbitMQ",
        ["architecture_decision_001.md"],
        "project_docs", "medium"
    ),
    BenchmarkQuery(
        "what users complained about in interviews",
        ["meeting_notes_product_sync.md"],
        "project_docs", "medium"
    ),
    
    # QA KB - Easy
    BenchmarkQuery(
        "account locked too many login attempts",
        ["troubleshooting_login.md"],
        "qa_kb", "easy"
    ),
    BenchmarkQuery(
        "how to cancel subscription",
        ["faq_billing.md"],
        "qa_kb", "easy"
    ),
    BenchmarkQuery(
        "export data CSV download",
        ["how_to_export_data.md"],
        "qa_kb", "easy"
    ),
    
    # QA KB - Medium
    BenchmarkQuery(
        "payment not going through what to check",
        ["faq_billing.md"],
        "qa_kb", "medium"
    ),
    BenchmarkQuery(
        "get my data out of the system",
        ["how_to_export_data.md"],
        "qa_kb", "medium"
    ),
    
    # Hard queries (cross-document, complex)
    BenchmarkQuery(
        "security settings two factor authentication",
        ["troubleshooting_login.md", "sprint_planning_2024_q1.md"],
        "mixed", "hard"
    ),
    BenchmarkQuery(
        "Python programming examples code snippets",
        ["python_decorators.md", "api_authentication.md"],
        "mixed", "hard"
    ),
]


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

@dataclass
class QueryResult:
    """Result for a single query evaluation."""
    query: str
    category: str
    difficulty: str
    hybrid_hits: list[str]  # Files found by hybrid
    vector_hits: list[str]  # Files found by vector
    relevant_docs: list[str]
    hybrid_precision_at_3: float
    vector_precision_at_3: float
    hybrid_recall_at_5: float
    vector_recall_at_5: float
    hybrid_mrr: float
    vector_mrr: float


def create_test_corpus(kb_path: Path) -> tuple[FileStore, VectorIndex, BM25Index]:
    """Create the synthetic document corpus."""
    console.print("\n[bold cyan]📚 Creating test corpus...[/bold cyan]")
    
    # Create temp docs directory
    docs_dir = kb_path.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    # Write all documents
    all_docs = {**TECH_DOCS, **STUDY_NOTES, **PROJECT_DOCS, **QA_KNOWLEDGE}
    
    for filename, content in all_docs.items():
        (docs_dir / filename).write_text(content)
    
    # Initialize indexes
    store = FileStore(kb_path)
    vector_index = VectorIndex(kb_path)
    bm25_index = BM25Index(kb_path / "index" / "bm25.db")
    
    # Index all documents
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Indexing...", total=len(all_docs))
        
        for filename in all_docs.keys():
            filepath = docs_dir / filename
            doc_id = store.add_file(filepath)
            doc = store.get_file(doc_id)
            if doc:
                vector_index.index_document(doc)
                bm25_index.index_document(doc)
            progress.update(task, advance=1, description=f"Indexed: {filename}")
    
    console.print(f"[green]✓ Created corpus with {len(all_docs)} documents[/green]")
    return store, vector_index, bm25_index


def run_benchmark(
    store: FileStore,
    vector_index: VectorIndex,
    bm25_index: BM25Index
) -> list[QueryResult]:
    """Run all benchmark queries."""
    console.print("\n[bold cyan]🔍 Running benchmark queries...[/bold cyan]")
    
    hybrid_retriever = Retriever(store, vector_index, bm25_index)
    vector_retriever = Retriever(store, vector_index, bm25_index=None)
    
    results = []
    
    for bq in BENCHMARK_QUERIES:
        # Run searches
        hybrid_results = hybrid_retriever.retrieve(bq.query, top_k=5)
        vector_results = vector_retriever.retrieve(bq.query, top_k=5)
        
        # Extract file names
        hybrid_files = [r.chunk.metadata.get("file_name", "") for r in hybrid_results]
        vector_files = [r.chunk.metadata.get("file_name", "") for r in vector_results]
        
        # Calculate metrics
        def precision_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
            top_k = retrieved[:k]
            hits = sum(1 for f in top_k if any(r in f for r in relevant))
            return hits / min(k, len(top_k)) if top_k else 0.0
        
        def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
            top_k = retrieved[:k]
            hits = sum(1 for r in relevant if any(r in f for f in top_k))
            return hits / len(relevant) if relevant else 0.0
        
        def mrr(retrieved: list[str], relevant: list[str]) -> float:
            for i, f in enumerate(retrieved, 1):
                if any(r in f for r in relevant):
                    return 1.0 / i
            return 0.0
        
        result = QueryResult(
            query=bq.query,
            category=bq.category,
            difficulty=bq.difficulty,
            hybrid_hits=hybrid_files[:3],
            vector_hits=vector_files[:3],
            relevant_docs=bq.relevant_docs,
            hybrid_precision_at_3=precision_at_k(hybrid_files, bq.relevant_docs, 3),
            vector_precision_at_3=precision_at_k(vector_files, bq.relevant_docs, 3),
            hybrid_recall_at_5=recall_at_k(hybrid_files, bq.relevant_docs, 5),
            vector_recall_at_5=recall_at_k(vector_files, bq.relevant_docs, 5),
            hybrid_mrr=mrr(hybrid_files, bq.relevant_docs),
            vector_mrr=mrr(vector_files, bq.relevant_docs),
        )
        results.append(result)
    
    return results


def print_results(results: list[QueryResult]):
    """Print comprehensive benchmark results."""
    console.print("\n[bold cyan]📊 Benchmark Results[/bold cyan]\n")
    
    # Summary by category and difficulty
    categories = {}
    difficulties = {}
    
    for r in results:
        # By category
        if r.category not in categories:
            categories[r.category] = {"hybrid_p": [], "vector_p": [], "hybrid_mrr": [], "vector_mrr": []}
        categories[r.category]["hybrid_p"].append(r.hybrid_precision_at_3)
        categories[r.category]["vector_p"].append(r.vector_precision_at_3)
        categories[r.category]["hybrid_mrr"].append(r.hybrid_mrr)
        categories[r.category]["vector_mrr"].append(r.vector_mrr)
        
        # By difficulty
        if r.difficulty not in difficulties:
            difficulties[r.difficulty] = {"hybrid_p": [], "vector_p": [], "hybrid_mrr": [], "vector_mrr": []}
        difficulties[r.difficulty]["hybrid_p"].append(r.hybrid_precision_at_3)
        difficulties[r.difficulty]["vector_p"].append(r.vector_precision_at_3)
        difficulties[r.difficulty]["hybrid_mrr"].append(r.hybrid_mrr)
        difficulties[r.difficulty]["vector_mrr"].append(r.vector_mrr)
    
    # Results by Category
    table1 = Table(title="Results by Use Case Category", show_header=True)
    table1.add_column("Category", style="cyan")
    table1.add_column("Hybrid P@3", justify="right")
    table1.add_column("Vector P@3", justify="right")
    table1.add_column("Hybrid MRR", justify="right")
    table1.add_column("Vector MRR", justify="right")
    table1.add_column("Winner", justify="center")
    
    for cat, metrics in sorted(categories.items()):
        h_p = sum(metrics["hybrid_p"]) / len(metrics["hybrid_p"])
        v_p = sum(metrics["vector_p"]) / len(metrics["vector_p"])
        h_mrr = sum(metrics["hybrid_mrr"]) / len(metrics["hybrid_mrr"])
        v_mrr = sum(metrics["vector_mrr"]) / len(metrics["vector_mrr"])
        
        winner = "[green]Hybrid[/green]" if h_mrr > v_mrr else "[blue]Vector[/blue]" if v_mrr > h_mrr else "[yellow]Tie[/yellow]"
        
        table1.add_row(cat, f"{h_p:.2f}", f"{v_p:.2f}", f"{h_mrr:.2f}", f"{v_mrr:.2f}", winner)
    
    console.print(table1)
    
    # Results by Difficulty
    console.print()
    table2 = Table(title="Results by Query Difficulty", show_header=True)
    table2.add_column("Difficulty", style="cyan")
    table2.add_column("Hybrid P@3", justify="right")
    table2.add_column("Vector P@3", justify="right")
    table2.add_column("Hybrid MRR", justify="right")
    table2.add_column("Vector MRR", justify="right")
    table2.add_column("Winner", justify="center")
    
    for diff in ["easy", "medium", "hard"]:
        if diff in difficulties:
            metrics = difficulties[diff]
            h_p = sum(metrics["hybrid_p"]) / len(metrics["hybrid_p"])
            v_p = sum(metrics["vector_p"]) / len(metrics["vector_p"])
            h_mrr = sum(metrics["hybrid_mrr"]) / len(metrics["hybrid_mrr"])
            v_mrr = sum(metrics["vector_mrr"]) / len(metrics["vector_mrr"])
            
            winner = "[green]Hybrid[/green]" if h_mrr > v_mrr else "[blue]Vector[/blue]" if v_mrr > h_mrr else "[yellow]Tie[/yellow]"
            
            table2.add_row(diff, f"{h_p:.2f}", f"{v_p:.2f}", f"{h_mrr:.2f}", f"{v_mrr:.2f}", winner)
    
    console.print(table2)
    
    # Overall summary
    console.print()
    all_hybrid_p = sum(r.hybrid_precision_at_3 for r in results) / len(results)
    all_vector_p = sum(r.vector_precision_at_3 for r in results) / len(results)
    all_hybrid_mrr = sum(r.hybrid_mrr for r in results) / len(results)
    all_vector_mrr = sum(r.vector_mrr for r in results) / len(results)
    
    overall_winner = "🏆 HYBRID" if all_hybrid_mrr > all_vector_mrr else "🏆 VECTOR" if all_vector_mrr > all_hybrid_mrr else "🤝 TIE"
    
    console.print(Panel(
        f"[bold]Overall Winner: {overall_winner}[/bold]\n\n"
        f"Hybrid: P@3 = {all_hybrid_p:.2f}, MRR = {all_hybrid_mrr:.2f}\n"
        f"Vector: P@3 = {all_vector_p:.2f}, MRR = {all_vector_mrr:.2f}\n\n"
        f"Total queries: {len(results)}",
        title="Overall Summary",
        border_style="green" if all_hybrid_mrr > all_vector_mrr else "blue",
    ))
    
    # Sample of individual results
    console.print("\n[bold]Sample Query Results:[/bold]")
    for r in results[:5]:
        h_files = ", ".join(r.hybrid_hits) or "(none)"
        v_files = ", ".join(r.vector_hits) or "(none)"
        console.print(f"  Q: {r.query[:50]}...")
        console.print(f"    [green]Hybrid[/green]: {h_files}")
        console.print(f"    [blue]Vector[/blue]: {v_files}")
        console.print(f"    Expected: {', '.join(r.relevant_docs)}")
        console.print()


def main():
    console.print(Panel(
        "[bold]🧪 Realistic RAG Benchmark[/bold]\n\n"
        "Testing search quality on 4 realistic use cases:\n"
        "• Tech Docs - API guides, error references\n"
        "• Study Notes - ML, Python, Docker\n"
        "• Project Docs - Sprint plans, decisions, meetings\n"
        "• Q&A Knowledge - Troubleshooting, FAQs\n\n"
        f"Total queries: {len(BENCHMARK_QUERIES)}",
        border_style="cyan",
    ))
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        kb_path = Path(tmp_dir) / ".midlayer"
        kb_path.mkdir(parents=True)
        
        # Create corpus
        store, vector_index, bm25_index = create_test_corpus(kb_path)
        
        # Run benchmark
        results = run_benchmark(store, vector_index, bm25_index)
        
        # Print results
        print_results(results)
    
    console.print("\n[bold green]✓ Benchmark complete![/bold green]")


if __name__ == "__main__":
    main()
