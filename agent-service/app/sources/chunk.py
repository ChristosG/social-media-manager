import re

_PARA = re.compile(r"\n\s*\n")


def _hard_split(s: str, target: int) -> list[str]:
    return [s[i:i + target] for i in range(0, len(s), target)]


def chunk_text(text: str, target_chars: int = 1200, overlap: int = 120) -> list[str]:
    """Pack paragraphs into ~target_chars chunks (keeps semantic boundaries); hard-split any single
    paragraph longer than target. `overlap` prepends a tail of the previous chunk for context."""
    paras = [p.strip() for p in _PARA.split(text or "") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(p) > target_chars:
            if buf:
                chunks.append(buf); buf = ""
            chunks.extend(_hard_split(p, target_chars))
            continue
        if buf and len(buf) + 2 + len(p) > target_chars:
            chunks.append(buf); buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        chunks.append(buf)
    if overlap and len(chunks) > 1:
        out = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            out.append(f"{tail}\n\n{chunks[i]}")
        return out
    return chunks
