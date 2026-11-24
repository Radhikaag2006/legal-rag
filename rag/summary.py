"""
Grounded research summaries.

A summary is built ONLY from material already retrieved in the chat: the
answered questions and the judgment extracts behind them. It is produced in
two passes (draft, then a fact-check against the extracts) and every citation
tag is validated in code, so the summary cannot cite a source that does not
exist. The authorities list is built from stored metadata, never by the LLM.
"""
import logging
import re

logger = logging.getLogger(__name__)

MAX_TURNS = 12
MAX_EXCERPTS = 2
MAX_EXCERPT_CHARS = 1500
SUMMARY_TIMEOUT = 90

TAG = re.compile(r"\[S(\d+)\]")

SUMMARY_FORMAT = """
## Overview
(3-4 sentences: what was researched and the overall position of the law.)

## Questions Considered
(Bullet list, one line per question researched.)

## Key Findings
(Bullet points. Each states one legal principle or holding, with its
citation(s) like [S1] or [S2][S3]. Quote short key phrases from the
extracts in quotation marks where useful.)

## Points of Difference or Uncertainty
(Where the sources conflict, or where the extracts leave the position open.
Write "None identified in the retrieved material." if there are none.)

## Limits of This Summary
(What the retrieved material does not cover and should be verified.)
"""


class NothingToSummarise(Exception):
    pass


# ---------------------------------------------------------
# Collecting the research from a chat
# ---------------------------------------------------------

def collect_research(messages):
    """
    Pair each question with its answer and merge all sources into ONE global
    numbering (each answer numbers its own sources from S1, so they collide).
    Unanswered turns are skipped: there is nothing reliable to summarise.
    """
    sources, index, turns = [], {}, []
    pending = None

    for m in messages:
        if m["role"] == "user":
            pending = m["content"]
            continue
        payload = m.get("payload") or {}
        if m["role"] != "assistant" or pending is None or payload.get("answered") is False:
            pending = None
            continue

        local_to_global = {}
        for s in payload.get("sources", []):
            key = (s.get("source_type"), s["document_id"])
            if key not in index:
                index[key] = len(sources) + 1
                sources.append({
                    "number": index[key],
                    "case_title": s["case_title"],
                    "court": s.get("court") or "",
                    "date": s.get("date") or "",
                    "source_type": s.get("source_type", "corpus"),
                    "page": s.get("page"),
                    "pdf_url": s.get("pdf_url"),
                    "viewable": s.get("viewable", False),
                    "external_url": s.get("external_url"),
                    "excerpts": [],
                })
            g = sources[index[key] - 1]
            local_to_global[s["number"]] = g["number"]
            for ex in s.get("excerpts", []):
                if len(g["excerpts"]) < MAX_EXCERPTS and ex not in g["excerpts"]:
                    g["excerpts"].append(ex[:MAX_EXCERPT_CHARS])

        def remap(match, table=local_to_global):
            n = table.get(int(match.group(1)))
            return f"[S{n}]" if n else ""

        turns.append({
            "question": pending,
            "answer": TAG.sub(remap, m["content"]),
        })
        pending = None

    turns = turns[-MAX_TURNS:]
    if not turns:
        raise NothingToSummarise(
            "There is no answered question in this chat to summarise yet."
        )
    return {"turns": turns, "sources": sources}


# ---------------------------------------------------------
# Prompts
# ---------------------------------------------------------

def _sources_block(sources):
    out = ""
    for s in sources:
        kind = "USER DOCUMENT" if s["source_type"] == "upload" else "Reported judgment"
        meta = f"{kind}: {s['case_title']}"
        if s["court"]:
            meta += f" | {s['court']}"
        if s["date"]:
            meta += f" | {s['date']}"
        out += f"\n===== [S{s['number']}] {meta} =====\n"
        out += "\n\n".join(s["excerpts"]) + "\n"
    return out


def _draft_prompt(research):
    qa = ""
    for i, t in enumerate(research["turns"], 1):
        qa += f"\n--- Question {i} ---\n{t['question']}\n\n--- Answer {i} ---\n{t['answer']}\n"

    return f"""You are a careful Indian legal research assistant. Write a summary of the
research below for a lawyer who will rely on it.

Rules:
1. Use ONLY the answers and source extracts below. No outside knowledge. Never
   invent case names, holdings, quotes, Articles or citations.
2. Every legal proposition must carry the source tag(s) that support it, e.g. [S1].
   Use only tags that appear below, and only where the extract really supports the point.
3. Keep numbers, dates, Article/section numbers and case names exactly as given.
4. Extracts marked USER DOCUMENT are the user's own material, not binding authority.
   Keep them distinct from reported judgments.
5. If sources conflict or are silent, say so. Do not smooth over gaps.
6. Be concise and neutral. No advice beyond what the sources support.

Follow this format exactly:
{SUMMARY_FORMAT}

==================== ANSWERS GIVEN ====================
{qa}

==================== SOURCE EXTRACTS ====================
{_sources_block(research['sources'])}
=======================================================

Summary:
"""


def _verify_prompt(draft, research):
    return f"""You are a meticulous legal fact-checker. Below are source extracts and a
DRAFT summary. Check every sentence of the draft against the extracts.

For each statement:
- If the extracts directly support it and the citation tag is right, keep it.
- If the citation tag is wrong, correct it to the tag that does support it.
- If it is not supported by the extracts, or overstates them, rewrite it to what the
  extracts actually say, or delete it.
- Do not add new information. Do not use outside knowledge.
- Keep quotations only if they appear word for word in the extracts.

Keep the same section headings and format. Output ONLY the corrected summary, with
no commentary about what you changed.

==================== SOURCE EXTRACTS ====================
{_sources_block(research['sources'])}
=======================================================

DRAFT SUMMARY:
{draft}

CORRECTED SUMMARY:
"""


# ---------------------------------------------------------
# Post-processing
# ---------------------------------------------------------

def _clean(text):
    text = (text or "").strip()
    text = re.sub(r"^```[a-z]*\n|\n```$", "", text).strip()
    return text


def _strip_invalid_tags(text, valid):
    return TAG.sub(lambda m: m.group(0) if int(m.group(1)) in valid else "", text)


def _norm(text):
    text = re.sub("[‘’“”]", "'", text.lower())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _unverified_quotes(summary, sources):
    """Quoted phrases (4+ words) that do not appear verbatim in any extract."""
    haystack = _norm(" ".join(e for s in sources for e in s["excerpts"]))
    bad = []
    for line in summary.splitlines():
        for q in re.findall(r'["“]([^"“”]{12,}?)["”]', line):
            n = _norm(q)
            if len(n.split()) >= 4 and n not in haystack:
                bad.append(q.strip())
    return bad


def _looks_complete(text):
    return text.count("## ") >= 3 and len(text) > 200


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

def generate_summary(gemini, messages):
    research = collect_research(messages)
    valid = {s["number"] for s in research["sources"]}

    draft = _clean(gemini.generate(
        _draft_prompt(research), temperature=0.1, timeout=SUMMARY_TIMEOUT
    ))
    if not _looks_complete(draft):
        raise RuntimeError("The summary came back incomplete. Please try again.")

    final, verified = draft, False
    try:
        checked = _clean(gemini.generate(
            _verify_prompt(draft, research), temperature=0.0, timeout=SUMMARY_TIMEOUT
        ))
        if _looks_complete(checked):
            final, verified = checked, True
        else:
            logger.warning("Fact-check pass returned an unusable result; keeping draft")
    except Exception as e:
        logger.warning(f"Fact-check pass failed; keeping draft: {e}")

    final = _strip_invalid_tags(final, valid)
    cited = {int(n) for n in TAG.findall(final)}
    authorities = [dict(s, cited=s["number"] in cited) for s in research["sources"]]
    # Authorities actually relied on come first; keep original order within each group
    authorities.sort(key=lambda s: not s["cited"])

    return {
        "summary": final,
        "authorities": authorities,
        "verified": verified,
        "unverified_quotes": _unverified_quotes(final, research["sources"]),
        "questions": len(research["turns"]),
    }
