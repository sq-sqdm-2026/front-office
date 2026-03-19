"""
Front Office - Character Memory System
Persistent memory for LLM-powered characters (GMs, owners, agents, scouts, etc.).
Characters remember past interactions, hold grudges, recall promises, and evolve over time.
"""
import json
from datetime import datetime
from ..database.db import execute, query, get_connection


VALID_CHARACTER_TYPES = ('gm', 'owner', 'agent', 'scout', 'beat_writer', 'coach')
VALID_CATEGORIES = (
    'trade_negotiation', 'promise', 'grudge', 'compliment', 'insult',
    'deal_outcome', 'conversation',
)

# Categories that resist decay -- characters never fully forget these
HIGH_RETENTION_CATEGORIES = ('grudge', 'promise', 'deal_outcome')

# Minimum decay_factor for high-retention memories (never goes below this)
MIN_DECAY_HIGH_RETENTION = 0.3

# Standard decay rate per call (multiply decay_factor by this)
DECAY_RATE = 0.95

# How many days old a memory must be before decay kicks in
DECAY_AGE_DAYS = 7


def _ensure_table(db_path: str = None):
    """Create the character_memories table if it doesn't exist."""
    conn = get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS character_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            character_type TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            importance INTEGER NOT NULL DEFAULT 5,
            game_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            decay_factor REAL NOT NULL DEFAULT 1.0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_character_memories_lookup
        ON character_memories(character_id, character_type)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_character_memories_category
        ON character_memories(category)
    """)
    conn.commit()
    conn.close()


def store_memory(character_id: int, character_type: str, category: str,
                 content: str, importance: int = 5, game_date: str = None,
                 db_path: str = None) -> int:
    """Store a new memory for a character.

    Args:
        character_id: ID of the character (FK to gm_characters, owner_characters, etc.)
        character_type: One of VALID_CHARACTER_TYPES
        category: One of VALID_CATEGORIES
        content: Free-text description of the memory
        importance: 1-10, determines retention priority during decay
        game_date: In-game date string (e.g. '2026-04-15')
        db_path: Optional database path override

    Returns:
        The row ID of the newly created memory.
    """
    if character_type not in VALID_CHARACTER_TYPES:
        raise ValueError(f"Invalid character_type '{character_type}'. Must be one of {VALID_CHARACTER_TYPES}")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Must be one of {VALID_CATEGORIES}")
    importance = max(1, min(10, importance))

    if game_date is None:
        gs = query("SELECT * FROM game_state WHERE id=1", db_path=db_path)
        game_date = gs[0]["current_date"] if gs else "2026-01-01"

    _ensure_table(db_path)
    return execute(
        """INSERT INTO character_memories
           (character_id, character_type, category, content, importance, game_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (character_id, character_type, category, content, importance, game_date),
        db_path=db_path,
    )


def get_memories(character_id: int, character_type: str, limit: int = 20,
                 category: str = None, db_path: str = None) -> list[dict]:
    """Retrieve memories for a character, sorted by effective importance (importance * decay_factor) and recency.

    Args:
        character_id: Character's ID
        character_type: Type of character
        limit: Maximum number of memories to return
        category: Optional filter by memory category
        db_path: Optional database path override

    Returns:
        List of memory dicts, most important/recent first.
    """
    _ensure_table(db_path)

    if category:
        rows = query(
            """SELECT *, (importance * decay_factor) as effective_importance
               FROM character_memories
               WHERE character_id=? AND character_type=? AND category=?
               ORDER BY effective_importance DESC, created_at DESC
               LIMIT ?""",
            (character_id, character_type, category, limit),
            db_path=db_path,
        )
    else:
        rows = query(
            """SELECT *, (importance * decay_factor) as effective_importance
               FROM character_memories
               WHERE character_id=? AND character_type=?
               ORDER BY effective_importance DESC, created_at DESC
               LIMIT ?""",
            (character_id, character_type, limit),
            db_path=db_path,
        )
    return rows


def build_memory_context(character_id: int, character_type: str,
                         db_path: str = None) -> str:
    """Build a text prompt context from a character's memories for LLM calls.

    Summarizes key relationships, grudges, promises, and recent events into
    a paragraph the LLM can use when generating responses.

    Returns:
        A string suitable for injection into a system/user prompt.
    """
    _ensure_table(db_path)

    memories = get_memories(character_id, character_type, limit=30, db_path=db_path)
    if not memories:
        return ""

    # Group by category for structured output
    grudges = []
    promises = []
    deal_outcomes = []
    recent_interactions = []

    for m in memories:
        cat = m["category"]
        eff = m["importance"] * m["decay_factor"]
        if eff < 1.0:
            continue  # Skip nearly-forgotten memories
        entry = m["content"]
        if cat == "grudge":
            grudges.append(entry)
        elif cat == "promise":
            promises.append(entry)
        elif cat == "deal_outcome":
            deal_outcomes.append(entry)
        else:
            recent_interactions.append(entry)

    sections = []
    sections.append("=== YOUR MEMORIES ===")

    if grudges:
        sections.append("GRUDGES & GRIEVANCES:")
        for g in grudges[:5]:
            sections.append(f"  - {g}")

    if promises:
        sections.append("PROMISES & COMMITMENTS:")
        for p in promises[:5]:
            sections.append(f"  - {p}")

    if deal_outcomes:
        sections.append("PAST DEAL OUTCOMES:")
        for d in deal_outcomes[:5]:
            sections.append(f"  - {d}")

    if recent_interactions:
        sections.append("RECENT INTERACTIONS:")
        for r in recent_interactions[:10]:
            sections.append(f"  - {r}")

    sections.append("=== END MEMORIES ===")
    return "\n".join(sections)


def decay_memories(db_path: str = None):
    """Reduce the decay_factor of old memories.

    Called periodically (e.g. each game day advance). Reduces decay_factor
    by multiplying with DECAY_RATE, but never lets high-retention memories
    (grudges, promises, deal outcomes) drop below MIN_DECAY_HIGH_RETENTION.

    Low-importance memories (importance <= 3) with decay_factor < 0.1 are
    deleted entirely to keep the table manageable.
    """
    _ensure_table(db_path)

    # Decay all memories older than DECAY_AGE_DAYS
    conn = get_connection(db_path)

    # Standard decay for normal categories
    conn.execute(
        f"""UPDATE character_memories
            SET decay_factor = MAX(0.01, decay_factor * {DECAY_RATE})
            WHERE category NOT IN ('grudge', 'promise', 'deal_outcome')
            AND julianday('now') - julianday(created_at) > {DECAY_AGE_DAYS}""",
    )

    # Slower decay for high-retention categories, with a floor
    conn.execute(
        f"""UPDATE character_memories
            SET decay_factor = MAX({MIN_DECAY_HIGH_RETENTION}, decay_factor * {DECAY_RATE})
            WHERE category IN ('grudge', 'promise', 'deal_outcome')
            AND julianday('now') - julianday(created_at) > {DECAY_AGE_DAYS}""",
    )

    # Purge nearly-forgotten low-importance memories
    conn.execute(
        """DELETE FROM character_memories
           WHERE importance <= 3 AND decay_factor < 0.1""",
    )

    conn.commit()
    conn.close()


def record_interaction(character_id: int, character_type: str,
                       other_party: str, interaction_type: str,
                       outcome: str, notes: str = "",
                       game_date: str = None, db_path: str = None) -> int:
    """Convenience wrapper to record a character interaction as a memory.

    Args:
        character_id: The character recording this memory
        character_type: Type of character
        other_party: Name or description of who they interacted with
        interaction_type: What happened (maps to a category)
        outcome: Result of the interaction (accepted, rejected, etc.)
        notes: Additional context
        game_date: In-game date
        db_path: Optional database path override

    Returns:
        The memory row ID.
    """
    # Map interaction_type to category
    type_to_category = {
        "trade_proposed": "trade_negotiation",
        "trade_accepted": "deal_outcome",
        "trade_rejected": "trade_negotiation",
        "promise_made": "promise",
        "promise_broken": "grudge",
        "insult": "insult",
        "compliment": "compliment",
        "negotiation": "trade_negotiation",
        "conversation": "conversation",
    }
    category = type_to_category.get(interaction_type, "conversation")

    # Determine importance based on outcome significance
    importance_map = {
        "trade_accepted": 8,
        "trade_rejected": 5,
        "promise_made": 7,
        "promise_broken": 9,
        "insult": 7,
        "compliment": 4,
        "trade_proposed": 4,
        "negotiation": 5,
        "conversation": 3,
    }
    importance = importance_map.get(interaction_type, 5)

    content = f"{interaction_type} with {other_party}: {outcome}"
    if notes:
        content += f" ({notes})"

    return store_memory(
        character_id=character_id,
        character_type=character_type,
        category=category,
        content=content,
        importance=importance,
        game_date=game_date,
        db_path=db_path,
    )


def get_relationship_summary(character_id: int, character_type: str,
                             with_character_id: int,
                             db_path: str = None) -> dict:
    """Summarize the history between two characters.

    Searches memories for mentions of the other character and builds
    a relationship summary with sentiment scoring.

    Returns:
        Dict with keys: interactions (int), sentiment (str), memories (list),
        trust_score (float -1 to 1).
    """
    _ensure_table(db_path)

    # Find all memories mentioning the other character
    # We search the content for their ID as a simple heuristic.
    # In practice, record_interaction stores the other party's name,
    # so we search for both ID references and name patterns.
    all_memories = query(
        """SELECT *, (importance * decay_factor) as effective_importance
           FROM character_memories
           WHERE character_id=? AND character_type=?
           ORDER BY effective_importance DESC, created_at DESC""",
        (character_id, character_type),
        db_path=db_path,
    )

    # Also look up the other character's name for content matching
    other_names = []
    for table in ('gm_characters', 'owner_characters'):
        rows = query(
            f"SELECT first_name, last_name FROM {table} WHERE id=?",
            (with_character_id,),
            db_path=db_path,
        )
        if rows:
            other_names.append(f"{rows[0]['first_name']} {rows[0]['last_name']}")

    # Also try agent_characters
    agent_rows = query(
        "SELECT name FROM agent_characters WHERE id=?",
        (with_character_id,),
        db_path=db_path,
    )
    if agent_rows:
        other_names.append(agent_rows[0]["name"])

    # Filter memories that reference the other character
    search_terms = other_names + [str(with_character_id)]
    relevant = []
    for m in all_memories:
        content_lower = m["content"].lower()
        if any(term.lower() in content_lower for term in search_terms):
            relevant.append(m)

    if not relevant:
        return {
            "interactions": 0,
            "sentiment": "neutral",
            "memories": [],
            "trust_score": 0.0,
        }

    # Calculate trust score based on memory categories and importance
    positive_weight = 0.0
    negative_weight = 0.0
    for m in relevant:
        eff = m["importance"] * m["decay_factor"]
        if m["category"] in ("compliment", "deal_outcome"):
            # deal_outcome could be positive or negative, but we count it as mildly positive
            positive_weight += eff
        elif m["category"] in ("grudge", "insult"):
            negative_weight += eff
        elif m["category"] == "promise":
            positive_weight += eff * 0.5  # promises are mildly positive until broken
        else:
            positive_weight += eff * 0.2  # neutral interactions are slightly positive

    total = positive_weight + negative_weight
    if total == 0:
        trust_score = 0.0
    else:
        trust_score = (positive_weight - negative_weight) / total  # Range: -1 to 1

    if trust_score > 0.3:
        sentiment = "positive"
    elif trust_score < -0.3:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return {
        "interactions": len(relevant),
        "sentiment": sentiment,
        "memories": [{"content": m["content"], "category": m["category"],
                       "importance": m["importance"], "game_date": m["game_date"]}
                      for m in relevant[:10]],
        "trust_score": round(trust_score, 2),
    }
