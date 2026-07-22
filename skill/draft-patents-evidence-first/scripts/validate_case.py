#!/usr/bin/env python3
"""Validate the complete local case contract without modifying inputs."""
from __future__ import annotations
import argparse, collections, hashlib, os, re, sys
from pathlib import Path
from evidence_first_lib import ValidationError, command_error, load_json, read_case

ACHIEVED = re.compile(
    r"\b(?:proved|proven|tested|improved|improves|increased|achieved|yielded|reduced|enhanced|demonstrated|confirmed|measured|observed|reached|resulted)\b"
    r"|(?:测试表明|证明了|提高了|实现了|达到(?:了)?|降低了|提升了|改善了|测得|验证表明|结果为)", re.I)
NON_ACHIEVED = re.compile(
    r"\b(?:not|no|never|without)\b.{0,36}\b(?:proved|proven|tested|improved|achieved|yielded|reduced|enhanced|demonstrated|confirmed|measured|observed|reached|resulted)\b"
    r"|\b(?:target|goal)\s+(?:is|was|to|for|of)\b|\b(?:proposed|planned|expected|intended)\s+(?:to|for)\b|\baims?\s+to\b|\b(?:to\s+be\s+verified|pending\s+verification)\b"
    r"|(?:未|尚未|并未|不).{0,16}(?:试验|证明|实现|达到|降低|提升|改善|测得|验证|结果)"
    r"|(?:目标(?:为|是)|拟|计划|预期|待验证|有待验证|将).{0,16}(?:实现|达到|降低|提升|改善|测得|验证|结果)", re.I)
CLAIM_LINE = re.compile(r"^\s*(?P<number>\d+)\s*[.．、]\s*(?P<text>.*?)\s*$")
WORD_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "for", "from",
    "has", "have", "in", "into", "is", "it", "its", "may", "of", "on", "or", "that", "the",
    "their", "there", "these", "this", "those", "to", "was", "were", "will", "with", "would",
    "claim", "claims", "evidence", "result", "results", "statement", "source", "record", "review",
}
RELATION_PATTERNS = {
    "contains": r"\b(?:compris\w*|includ\w*|contain\w*|hav(?:e|ing|es))\b|(?:包括|包含|设有|具有)",
    "connects": r"\b(?:connect\w*|coupl\w*|attach\w*|join\w*|interlock\w*)\b|(?:连接|耦合|附接|接合|啮合)",
    "positions": r"\b(?:mount\w*|arrang\w*|position\w*|locat\w*|spac\w*|between|adjacent)\b|(?:安装|布置|定位|位于|间隔|间距|之间|相邻)",
    "configures": r"\b(?:configur\w*|adapt\w*|form\w*|define\w*)\b|(?:配置|构成|形成|限定)",
    "measures": r"\b(?:measur\w*|observ\w*|test\w*|record\w*|detect\w*)\b|(?:测量|测得|观察|试验|测试|记录|检测)",
    "improves": r"\b(?:improv\w*|enhanc\w*|increas\w*|gain\w*|achiev\w*)\b|(?:提高|提升|改善|增强|增加|实现|达到)",
    "reduces": r"\b(?:reduc\w*|decreas\w*|lower\w*|minimi[sz]\w*|loss|lost|declin\w*|deteriorat\w*)\b|(?:降低|减少|减小|抑制|损失|下降|恶化)",
    "supports": r"\b(?:support\w*|hold\w*|constrain\w*|press\w*)\b|(?:支承|支撑|保持|约束|压持)",
    "property": r"\b(?:spacing|dimension|thickness|temperature|pressure|load|accuracy|drift|wear|performance|relation|value|rate)\b|(?:间距|尺寸|厚度|温度|压力|载荷|精度|漂移|磨损|性能|关系|数值|速率)",
}
NEGATION = re.compile(r"\b(?:no|not|never|without|none|lacks?|absent)\b|(?:不|未|无|没有|缺少|不存在)", re.I)
LEGAL_DISCLAIMER = re.compile(
    r"\b(?:not legal advice|does not guarantee (?:patentability|validity)|obtain qualified patent counsel|not filing-ready)\b|"
    r"(?:不构成法律意见|不保证可专利性|具备资质的专利专业人员审核|不可直接用于申请)", re.I,
)
PURE_GOVERNANCE = re.compile(
    r"\b(?:synthetic demonstration|not a real client matter|synthetic exercise considers|design exercise asks|contains no client material and reports no test result|"
    r"no qualifying prior-art record is asserted|no novelty conclusion is made|real matter must verify publication dates|"
    r"may be mistaken for filing advice|bilingual scope may drift|may be mistaken for a measured optimum|"
    r"does not depict a tested apparatus|no statement in this sample establishes|require separately documented verification|"
    r"not performed|required real-case evidence|not claimed)\b|"
    r"(?:虚构演示|并非真实客户案件|本合成练习讨论|本设计练习拟讨论|不含客户材料，也不记载任何试验结果|不主张存在可用于评价的现有技术|"
    r"不作新颖性结论|真实案件在开展对比前|可能被误读为申请建议|双语保护范围可能漂移|可能被误读为实测最优值|"
    r"不代表已经试验的装置|本样例不证明|须另行形成有据可查的验证记录|未实施|未主张)", re.I,
)


def is_unsupported_achieved(sentence: str) -> bool:
    # A target/plan qualifier applies to its own proposition, not to a later
    # measured-result clause in the same sentence.
    return any(bool(ACHIEVED.search(clause) and not NON_ACHIEVED.search(clause)) for clause in output_clauses(sentence))


def rendered_claim_inventory(paths: dict[str, Path]) -> list[dict[str, object]]:
    path = paths["output"] / "claims.md"
    if not path.exists():
        raise ValidationError("rendered claims.md missing")
    claims: list[dict[str, object]] = []
    current_number: int | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_number, current_lines
        if current_number is None:
            return
        text = _normalise_claim_lines(current_lines)
        if text:
            dependency = re.search(r"(?:claim|claims|权利要求)\s*(\d+)", text, re.I)
            claims.append({
                "claim_number": current_number,
                "text": text,
                "parent_claim_number": int(dependency.group(1)) if dependency else None,
            })
        current_number = None
        current_lines = []

    for line in path.read_text(encoding="utf-8").splitlines():
        match = CLAIM_LINE.match(line)
        if match:
            flush()
            current_number = int(match.group("number"))
            current_lines = [match.group("text")]
            continue
        if current_number is not None and re.match(r"^\s*#{1,6}\s+", line):
            flush()
            continue
        # Markdown claim continuations must be visibly attached to the numbered
        # item.  In particular, retain each indented bullet as a distinct segment;
        # never absorb an unindented prose note into the preceding claim.
        if current_number is not None and line.strip() and re.match(r"^\s+", line) and not line.lstrip().startswith(("```", "|")):
            current_lines.append(line)
    flush()
    return claims


def _normalise_claim_lines(lines: list[str]) -> str:
    cleaned: list[str] = []
    for line in lines:
        bullet = bool(re.match(r"^\s*(?:[-*+]\s+)", line))
        value = re.sub(r"^\s*(?:[-*+]\s+)", "", line).strip()
        if value:
            # A delimiter is essential for atomization where bullets themselves
            # omit terminal punctuation (the common Markdown claim-list form).
            if bullet and cleaned and not cleaned[-1].rstrip().endswith((";", "；", ",", "，", ":", "：")):
                cleaned[-1] = cleaned[-1].rstrip() + ";"
            cleaned.append(value)
    return re.sub(r"\s+", " ", " ".join(cleaned)).strip()


def _normalise_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .。;；,").casefold()


def rendered_claim_atoms(claim: dict[str, object]) -> list[dict[str, object]]:
    """Return the deterministic atomic limitation inventory for one rendered claim.

    A claim line is no longer an implicit limitation.  Explicit enumerations are
    individual limitations, while an unsplit single feature remains a single atom.
    This deliberately avoids attempting legal claim parsing: it only accepts the
    persisted trace when every rendered textual atom has exactly one trace row.
    """
    text = str(claim["text"])
    # Keep Markdown bullets as deliberate limitation boundaries even when this
    # helper is called directly (rather than only through the file inventory).
    text = re.sub(r"\n\s*[-*+]\s+", "; ", text)
    text = re.sub(r"\s+", " ", text).strip()
    body = re.sub(r"^(?:the\s+\w+\s+of\s+)?(?:claim|claims|权利要求)\s*\d+[^,，;；]*[,，;；]?\s*", "", text, flags=re.I)
    # The preamble is not a limitation by itself.  Split only explicit enumerations;
    # prose such as "a member with a spacing" remains one atomic relation.
    if re.search(r"(?:包括|包含|设有)", body):
        body = re.split(r"(?:包括|包含|设有)", body, maxsplit=1)[1]
        pieces = re.split(r"[;；]|(?:、|，|以及|并且|且|和)(?=\s*(?:一|至少一|所述|[A-Za-z]))", body)
    elif re.search(r"\b(?:comprising|including|having|further comprising)\b", body, re.I):
        body = re.split(r"\b(?:comprising|including|having|further comprising)\b", body, maxsplit=1, flags=re.I)[1]
        pieces = re.split(r"[;；]|\s*,\s*(?=(?:a|an|the|at least one)\b)|\s+and\s+(?=(?:a|an|the|at least one)\b)", body, flags=re.I)
    else:
        pieces = [body]
    cleaned: list[str] = []
    for ordinal, piece in enumerate(pieces, 1):
        atom = re.sub(r"^(?:and|or|以及|和)\s+", "", piece.strip(" :：.。;；,，"), flags=re.I)
        if atom:
            cleaned.append(atom)
    # Preserve the legacy, already-atomic single limitation spelling.  A trace may
    # use the complete claim text only when there is exactly one rendered atom.
    if len(cleaned) == 1:
        cleaned = [text.strip()]
    atoms = [{"claim_number": claim["claim_number"], "parent_claim_number": claim["parent_claim_number"], "text": atom, "ordinal": ordinal} for ordinal, atom in enumerate(cleaned, 1)]
    return atoms or [{"claim_number": claim["claim_number"], "parent_claim_number": claim["parent_claim_number"], "text": _normalise_space(text), "ordinal": 1}]


def _tokens(value: str) -> set[str]:
    tokens = {token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|\d+(?:\.\d+)?%?", value)}
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", value):
        tokens.add(chunk)
        tokens.update(chunk[index:index + 2] for index in range(len(chunk) - 1))
    return tokens


def _substantive_tokens(value: str) -> set[str]:
    result: set[str] = set()
    for token in _tokens(value):
        if token in WORD_STOP or token.isdigit() or re.fullmatch(r"(?:src|ev|clm|lim)-?\d+", token):
            continue
        if re.fullmatch(r"[a-z][a-z0-9_-]+", token):
            token = re.sub(r"(?:ies|ing|ed|es|s)$", lambda match: {"ies":"y", "ing":"", "ed":"", "es":"", "s":""}[match.group(0)], token)
        if len(token) >= 2:
            result.add(token)
    return result


def _values(value: str) -> set[str]:
    scrubbed = re.sub(r"\b(?:SRC|EV|CLM|LIM)-\d+\b|\b(?:CN|US|EP|WO)\d+[A-Z0-9]*\b|\b\d{4}-\d{2}-\d{2}\b", "", value, flags=re.I)
    return {re.sub(r"\s+", "", item).casefold() for item in re.findall(r"\d+(?:\.\d+)?\s*(?:%|mm|μm|um|℃|°C|MPa|N|s|min)?", scrubbed, flags=re.I)}


def _has_metric_value(value: str) -> bool:
    return bool(re.search(r"\d+(?:\.\d+)?\s*(?:%|mm|μm|um|℃|°C|MPa|N|s|min)(?![A-Za-z])", value, re.I))


def _relation_signatures(value: str) -> set[str]:
    signatures = {name for name, pattern in RELATION_PATTERNS.items() if re.search(pattern, value, re.I)}
    for predicate in re.findall(r"\b(?:may|can|must|is|are|was|were|be|been|has|have|had)\s+([A-Za-z][A-Za-z-]{2,})", value, re.I):
        normalized = next(iter(_substantive_tokens(predicate)), predicate.casefold())
        if normalized not in {"verifi", "document", "requir", "claim", "propos", "intend", "expect"}:
            signatures.add("verb:" + normalized)
    return signatures


RELATION_ARGUMENT_VERBS = {
    "contains": r"compris(?:e|es|ing)?|includ(?:e|es|ing)?|contain(?:s|ed|ing)?|has|have|having",
    "connects": r"connect(?:s|ed|ing)?|coupl(?:e|es|ed|ing)?|attach(?:es|ed|ing)?|join(?:s|ed|ing)?|interlock(?:s|ed|ing)?",
}
RELATION_ARGUMENT_CHINESE = {
    "contains": r"包括|包含|设有|具有",
    "connects": r"连接|耦合|附接|接合|啮合",
}


def _argument_terms(value: str) -> set[str]:
    """Content terms for a parsed relation endpoint, excluding English articles."""
    return _substantive_tokens(re.sub(r"\b(?:a|an|the|said|each)\b", "", value, flags=re.I))


def _relation_argument_pairs(value: str) -> dict[str, list[tuple[set[str], set[str]]]]:
    """Extract conservative subject→object pairs for common active claim syntax.

    This is deliberately a narrow syntactic guard: when an expression cannot be
    parsed reliably it returns no pair and token/relation matching remains in
    force.  When both sides do express an active relation, reversed endpoints are
    a semantic mismatch rather than evidence of the same proposition.
    """
    parsed: dict[str, list[tuple[set[str], set[str]]]] = collections.defaultdict(list)
    text = _markdown_visible_text(value)
    for relation, verbs in RELATION_ARGUMENT_VERBS.items():
        pattern = re.compile(
            rf"(?P<subject>\b(?:the\s+|a\s+|an\s+)?[A-Za-z][A-Za-z0-9_-]*(?:\s+[A-Za-z][A-Za-z0-9_-]*){{0,3}}?)\s+"
            rf"(?:does\s+not\s+|do\s+not\s+|not\s+)?(?:{verbs})\s+"
            rf"(?P<object>(?:the\s+|a\s+|an\s+)?[A-Za-z][A-Za-z0-9_-]*(?:\s+[A-Za-z][A-Za-z0-9_-]*){{0,4}}?)(?=$|[;,.，。；]|\s+(?:and|or|but)\b)",
            re.I,
        )
        for match in pattern.finditer(text):
            subject, obj = _argument_terms(match.group("subject")), _argument_terms(match.group("object"))
            if subject and obj:
                parsed[relation].append((subject, obj))
    for relation, verbs in RELATION_ARGUMENT_CHINESE.items():
        # The relation word makes a bounded Chinese span safe enough for a
        # direction check without pretending to be a full Chinese parser.
        pattern = re.compile(rf"(?P<subject>[\u4e00-\u9fff]{{1,10}}?)(?:不|未)?(?:{verbs})(?P<object>[\u4e00-\u9fff]{{1,10}}?)(?=$|[，,。；;、])")
        for match in pattern.finditer(text):
            subject, obj = _argument_terms(match.group("subject")), _argument_terms(match.group("object"))
            if subject and obj:
                parsed[relation].append((subject, obj))
    return parsed


def _comparison_polarities(value: str) -> set[str]:
    """Return directional result polarity; empty means no directional result."""
    result: set[str] = set()
    if re.search(r"\b(?:improv\w*|enhanc\w*|increas\w*|gain\w*|better|higher)\b|(?:提高|提升|改善|增强|增加|升高)", value, re.I):
        result.add("positive")
    if re.search(r"\b(?:reduc\w*|decreas\w*|lower\w*|loss|lost|worse|declin\w*|deteriorat\w*)\b|(?:降低|减少|减小|损失|下降|恶化)", value, re.I):
        result.add("negative")
    return result


def _negated_relation_signatures(value: str) -> set[str]:
    """Identify negation attached to a predicate, not unrelated disclaimer text."""
    result: set[str] = set()
    for name, pattern in RELATION_PATTERNS.items():
        for match in re.finditer(pattern, value, re.I):
            # Keep the window deliberately tight: a trailing "no measurement"
            # cannot negate an earlier spacing relationship in the same sentence.
            sentence_start = max(value.rfind(mark, 0, match.start()) for mark in (".", "。", ";", "；", "!", "！", "?", "？")) + 1
            next_marks = [value.find(mark, match.end()) for mark in (".", "。", ";", "；", "!", "！", "?", "？")]
            sentence_end = min([offset for offset in next_marks if offset >= 0] or [len(value)])
            neighborhood = value[max(sentence_start, match.start() - 10):min(sentence_end, match.end() + 10)]
            if NEGATION.search(neighborhood):
                result.add(name)
                break
    return result


def _binding_matches(statement: str, comparable: str) -> bool:
    """Require a proposition-level match, not a coincidental shared token."""
    statement_tokens = _substantive_tokens(statement)
    comparable_tokens = _substantive_tokens(comparable)
    shared = statement_tokens & comparable_tokens
    statement_values, comparable_values = _values(statement), _values(comparable)
    if statement_values and not statement_values <= comparable_values:
        return False
    statement_polarity, comparable_polarity = _comparison_polarities(statement), _comparison_polarities(comparable)
    if statement_polarity or comparable_polarity:
        if statement_polarity != comparable_polarity:
            return False
    statement_relations = _relation_signatures(statement)
    comparable_relations = _relation_signatures(comparable)
    relations = statement_relations & comparable_relations
    # Truth polarity is symmetric for the same proposition.  A generic source
    # disclaimer such as "no measurement" must not negate an unrelated structural
    # limitation, whereas "contains blade" / "does not contain blade" must fail in
    # either direction.
    shared_relation_scope = statement_relations & comparable_relations
    if (_negated_relation_signatures(statement) & shared_relation_scope) != (_negated_relation_signatures(comparable) & shared_relation_scope):
        return False
    directional = statement_relations - {"property", "measures"}
    if directional and not directional & comparable_relations:
        return False
    statement_pairs, comparable_pairs = _relation_argument_pairs(statement), _relation_argument_pairs(comparable)
    for relation in set(statement_pairs) & set(comparable_pairs):
        # Any same-direction endpoint pairing is sufficient (a source may state
        # several relations); a wholly reversed pairing is never a valid binding.
        if not any(
            source_subject & record_subject and source_object & record_object
            for source_subject, source_object in statement_pairs[relation]
            for record_subject, record_object in comparable_pairs[relation]
        ):
            return False
    # A numeric property can be bound by one shared attribute plus the exact value;
    # qualitative propositions need at least two shared object/component terms.
    required_objects = 1 if statement_values or NEGATION.search(statement) else 2
    return len(shared) >= required_objects and bool(relations)


def _achieved_evidence_matches(sentence: str, evidence: list[dict]) -> bool:
    for row in evidence:
        if row["evidence_class"] != "measured" or row["verification_status"] != "verified" or not row["source_location"]:
            continue
        measurement = row.get("measurement", {})
        result = str(measurement.get("result", ""))
        method = str(measurement.get("method", ""))
        context = str(measurement.get("context", ""))
        if not result.strip() or not method.strip() or not context.strip() or not _binding_matches(sentence, result):
            continue
        method_cue = bool(re.search(r"\b(?:by|using|via|method|test(?:ed|ing)?)\b|(?:采用|通过|方法|试验)", sentence, re.I))
        context_cue = bool(re.search(r"\b(?:under|during|at|in)\b|(?:在.+(?:条件下|时))", sentence, re.I))
        method_bound = bool(_substantive_tokens(sentence) & _substantive_tokens(method))
        context_bound = bool(_substantive_tokens(sentence) & _substantive_tokens(context))
        if (not method_cue or method_bound) and (not context_cue or context_bound):
            return True
    return False


def output_clauses(text: str) -> list[str]:
    """Split result assertions before classification so a target cannot mask a result."""
    sentences = re.split(r"[.!?。！？]+\s*", text)
    clauses: list[str] = []
    for sentence in sentences:
        clauses.extend(re.split(
            r"[;；]+|,(?=\s*(?:but|while|however|(?:and\s+)?the\s+(?:trial|test|experiment)|(?:and\s+)?a\s+(?:trial|test|experiment))\b)|"
            r"\s+(?=and\s+(?:the|a)\s+(?:trial|test|experiment)\b)|"
            r"，(?=\s*(?:但|而|试验|测试|实验|样机))",
            sentence,
            flags=re.I,
        ))
    return [clause.strip() for clause in clauses if clause.strip()]


def _is_material_narrative_statement(path: Path, statement: str) -> bool:
    del path
    stripped = statement.strip()
    if not stripped or stripped.startswith(("#", "![")):
        return False
    if LEGAL_DISCLAIMER.search(stripped) or PURE_GOVERNANCE.search(stripped):
        return False
    # A source/disposition-only line is validated by _validate_prior_art.  It is not
    # a technical proposition for evidence-coverage purposes.
    if re.fullmatch(
        r"(?:SRC-\d+\s*[:：]?\s*)?(?:[A-Z]{0,3}\d+[A-Z0-9-]*\s+)?(?:is\s+)?(?:qualifying prior art|retained as context only|context only|excluded from (?:the )?comparison)[^.。]*[.。]?|"
        r"(?:SRC-\d+\s*[:：]?\s*)?.*(?:可用于评价的现有技术|仅作背景|上下文资料|排除在对比之外)[^.。]*[.。]?",
        stripped,
        re.I,
    ):
        return False
    if re.search(r"\bSRC-\d{4,}\b", stripped, re.I) and re.search(r"\bqualifying prior art\b|(?:可用于评价的现有技术)", stripped, re.I) and re.search(r"\b(?:cache|offline review|cited)\b|(?:缓存|离线审查|引用)", stripped, re.I):
        return False
    # Inventory by default. Unknown terms, negative limitations, and prior-art
    # technical sentences must not disappear merely because a vocabulary list lacks
    # their nouns or predicates.
    return True


def _narrative_clauses(text: str) -> list[str]:
    """Extract prose/table assertions without accidentally attaching headings to text."""
    clauses: list[str] = []
    lines = text.splitlines()
    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!["):
            continue
        if line.startswith(">"):
            line = line[1:].strip()
        if line.startswith("|") and line.endswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if not cells or all(re.fullmatch(r"[- :]+", cell) for cell in cells):
                continue
            next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
            if next_line.startswith("|") and all(re.fullmatch(r"[- :]+", cell.strip()) for cell in next_line.strip("|").split("|")):
                continue
            line = ". ".join(_markdown_visible_text(cell) for cell in cells)
            clauses.append(line)
            continue
        visible = _markdown_visible_text(line)
        if visible:
            clauses.extend(output_clauses(visible))
    return clauses


def _markdown_visible_text(value: str) -> str:
    """Keep link labels as prose while removing URL/code noise from language checks."""
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"<https?://[^>]+>", "", value, flags=re.I)
    value = re.sub(r"https?://\S+", "", value, flags=re.I)
    return re.sub(r"[`*_]+", "", value).strip()


def _language_counts(value: str) -> tuple[int, int]:
    visible = _markdown_visible_text(value)
    return len(re.findall(r"[\u4e00-\u9fff]", visible)), len(re.findall(r"[A-Za-z]{3,}", visible))


def statement_inventory(paths: dict[str, Path], trace: list[dict], expected_language: str | None = None) -> list[dict[str, object]]:
    """Stable inventory of every material output assertion and its evidence binding.

    IDs are content-addressed by output-relative path, occurrence, and normalized
    text.  This is intentionally computed rather than persisted so validation stays
    read-only and cannot be bypassed by a stale sidecar file.
    """
    trace_by_atom: dict[tuple[int, str], list[dict]] = collections.defaultdict(list)
    for row in trace:
        if "claim_number" in row and "limitation_text" in row:
            trace_by_atom[(row["claim_number"], _normalise_space(str(row["limitation_text"])))].append(row)
    # Language conformance is a separate validation gate.  Never omit an
    # off-language technical statement from the evidence denominator: doing so
    # would turn a localization defect into a fictitious 100% coverage score.
    del expected_language
    inventory: list[dict[str, object]] = []
    for path in sorted(paths["output"].glob("*.md")):
        relative = path.relative_to(paths["output"]).as_posix()
        if path.name == "claims.md":
            for claim in rendered_claim_inventory(paths):
                for atom in rendered_claim_atoms(claim):
                    normalized = _normalise_space(str(atom["text"]))
                    rows = trace_by_atom.get((int(atom["claim_number"]), normalized), [])
                    evidence_ids = sorted({item for row in rows for item in row.get("evidence_ids", [])})
                    identity = f"{relative}:{atom['claim_number']}:{atom['ordinal']}:{normalized}"
                    inventory.append({"statement_id": "STMT-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16], "path": relative, "text": atom["text"], "evidence_ids": evidence_ids})
            continue
        occurrence = collections.Counter()
        for clause in _narrative_clauses(path.read_text(encoding="utf-8")):
            if not _is_material_narrative_statement(path, clause):
                continue
            normalized = _normalise_space(clause)
            occurrence[normalized] += 1
            identity = f"{relative}:{occurrence[normalized]}:{normalized}"
            inventory.append({"statement_id": "STMT-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16], "path": relative, "text": clause, "evidence_ids": []})
    return inventory


def _narrative_statement_evidence(statement: str, evidence: list[dict], trace: list[dict]) -> list[str]:
    explicit_evidence = set(re.findall(r"\bEV-\d{4,}\b", statement, re.I))
    explicit_sources = set(re.findall(r"\bSRC-\d{4,}\b", statement, re.I))
    matches: list[str] = []
    for row in evidence:
        if row.get("verification_status") == "rejected":
            continue
        if explicit_evidence and str(row.get("evidence_id")) not in explicit_evidence:
            continue
        if explicit_sources and str(row.get("source_id")) not in explicit_sources:
            continue
        comparable = " ".join((str(row.get("statement", "")), str(row.get("verbatim", ""))))
        if row.get("evidence_class") == "designed":
            comparable += " designed proposal target not measured to be verified 拟议设计目标 未实测 待验证"
        # A trace is an explicit output-to-evidence binding, so its limitation text
        # is a valid bridge for matching narrative restatements of that limitation.
        for trace_row in trace:
            if row["evidence_id"] in trace_row.get("evidence_ids", []):
                comparable += " " + str(trace_row.get("limitation_text", ""))
        if _binding_matches(statement, comparable):
            matches.append(str(row["evidence_id"]))
    return sorted(set(matches))


def _utility_model_is_structural(claim: str) -> bool:
    lowered = claim.casefold()
    method_subject = bool(re.match(r"(?:a|an|the)?\s*(?:method|process|procedure|technique|approach|way)\b|(?:一种|一项).{0,20}(?:方法|工艺|流程|步骤|用途)", claim, re.I))
    product = bool(re.search(r"\b(?:fixture|device|apparatus|system|assembly|sensor|module|component|clamp|housing)\b|(?:装置|设备|夹具|系统|组件|模块|传感器|构件|器件)", claim, re.I))
    relation = bool(re.search(r"\b(?:comprising|including|having|connected|coupled|between|spaced|mounted)\b|(?:包括|包含|设有|连接|固定|间距|位于)", claim, re.I))
    return product and relation and not method_subject


def _trace_evidence_matches(limitation: str, row: dict) -> bool:
    """Require every trace edge to carry a proposition, not a merely valid ID.

    Designed and inferred limitations remain reviewable work products, but their
    accepted status does not license an unrelated evidence row.  They use the same
    proposition test; their allowance is solely in the evidence-class and human
    review rules enforced by ``validate_trace`` and ``main``.
    """
    # Evidence statements and verbatim quotations can carry adjacent validation
    # caveats (for example, "no measurement supplied").  Treat each source field
    # as an independent proposition so such a caveat cannot negate a separate,
    # otherwise fully supported structural limitation by concatenation.
    return any(
        _binding_matches(limitation, str(row.get(field, "")))
        for field in ("statement", "verbatim")
        if str(row.get(field, "")).strip()
    )


def _validate_output_language(paths: dict[str, Path], claims: list[dict[str, object]], expected_language: str, *, auto: bool) -> None:
    claim_error = "auto language resolution differs from rendered claim output language" if auto else "configured output language differs from rendered claim output language"
    narrative_error = "auto resolved language differs from narrative deliverable" if auto else "configured output language differs from narrative deliverable"
    for claim in claims:
        chinese, latin_words = _language_counts(str(claim["text"]))
        # A deliberately paired bilingual line is acceptable in auto mode only
        # when it contains substantial text in both languages.  A lone English
        # Markdown label cannot camouflage a Chinese technical statement.
        bilingual_line = chinese >= 2 and latin_words >= 3
        if (expected_language == "zh-CN" and (chinese == 0 or (latin_words >= 3 and not bilingual_line))) or (expected_language == "en-US" and (latin_words == 0 or (chinese >= 2 and not bilingual_line))):
            raise ValidationError(claim_error)
    for path in sorted(paths["output"].glob("*.md")):
        if path.name == "claims.md":
            continue
        for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line or re.fullmatch(r"[|\-: `]+", line):
                continue
            chinese, latin_words = _language_counts(line)
            # Numeric-only and punctuation-only cells are language-neutral. Every
            # narrative-bearing physical line must include the resolved language;
            # statement inventory may then group/translate it without hiding a
            # wrong-language-only line.
            if not chinese and not latin_words:
                continue
            bilingual_line = chinese >= 2 and latin_words >= 3
            if (expected_language == "zh-CN" and (not chinese or (latin_words >= 3 and not bilingual_line))) or (expected_language == "en-US" and (not latin_words or (chinese >= 2 and not bilingual_line))):
                raise ValidationError(f"{narrative_error} {path.name}:{line_number}")


def _validate_auto_output_language(paths: dict[str, Path], claims: list[dict[str, object]], trace: list[dict], resolved_language: str) -> None:
    if any(row.get("language") != resolved_language for row in trace):
        raise ValidationError("auto resolved language differs from claim trace language")
    _validate_output_language(paths, claims, resolved_language, auto=True)


def _validate_prior_art(case: dict, sources: list[dict], prior_art: str) -> None:
    """Reconcile rendered source dispositions with the canonical source records."""
    source_by_id = {row["source_id"]: row for row in sources}
    dispositions = {"qualifying_prior_art", "context_only", "excluded", "not_compared"}
    structured: dict[str, str | None] = {}

    def publication_ids(value: object) -> set[str]:
        # Patent pages are inconsistent about which field carries the publication
        # number, so search the canonical identity fields instead of trusting a
        # rendered prose label.  Require country prefix + at least four digits to
        # avoid treating dates or internal IDs as publications.
        text = str(value or "")
        return {
            re.sub(r"\s+", "", item).upper()
            for item in re.findall(r"\b(?:CN|US|EP|WO|JP|KR|DE|FR|GB)\s*\d{4,}[A-Z]\d?\b|\b(?:CN|US|EP|WO|JP|KR|DE|FR|GB)\s*\d{4,}\b", text, re.I)
        }

    by_publication: dict[str, list[dict]] = collections.defaultdict(list)
    for source in sources:
        direct = source.get("comparison_disposition")
        comparison = source.get("comparison")
        nested = None
        if comparison is not None:
            if not isinstance(comparison, dict):
                raise ValidationError("source comparison must be an object")
            nested = comparison.get("disposition")
        if direct is not None and nested is not None and direct != nested:
            raise ValidationError("source comparison disposition conflicts with comparison_disposition")
        disposition = nested if nested is not None else direct
        structured[source["source_id"]] = disposition
        # Publication-number reconciliation is required even for a patent that
        # has not yet received a comparison disposition in the source ledger.
        if source.get("source_type") == "patent":
            identities = set()
            for field in ("publication_number", "patent_number", "title", "canonical_url", "locator"):
                identities.update(publication_ids(source.get(field)))
            for identity in identities:
                by_publication[identity].append(source)
        if disposition is None:
            continue
        if not isinstance(disposition, str) or disposition not in dispositions:
            raise ValidationError("source comparison disposition is invalid")
        if disposition != "qualifying_prior_art":
            pass
        else:
            if source["source_type"] != "patent":
                raise ValidationError("qualifying prior art must bind a patent source")
            if source.get("verification_status") != "verified" or not source.get("publication_date") or not source.get("accessed_at") or not source.get("canonical_url"):
                raise ValidationError("qualifying prior art needs canonical URL, access date, verified publication date, and verified status")
            if case.get("critical_date") and source["publication_date"] > case["critical_date"]:
                raise ValidationError("post-critical-date patent cannot be qualifying prior art")

    def rendered_disposition(line: str) -> str | None:
        if re.search(r"\b(?:context only|retained as context|background only)\b|(?:仅作背景|上下文资料|仅供参考)", line, re.I):
            return "context_only"
        if re.search(r"\b(?:excluded|exclude(?:s|d)? from (?:the )?comparison|not qualifying prior art)\b|(?:排除|不纳入对比|不属于可用于评价的现有技术)", line, re.I):
            return "excluded"
        if re.search(r"\b(?:not compared|comparison not performed|not asserted)\b|(?:未对比|未实施对比|未主张)", line, re.I):
            return "not_compared"
        if re.search(r"\bqualifying prior art\b|(?:可用于评价的现有技术)", line, re.I):
            return "qualifying_prior_art"
        return None

    for line in prior_art.splitlines():
        source_ids = re.findall(r"\bSRC-\d{4,}\b", line, re.I)
        rendered_publications = publication_ids(line)
        if not source_ids and not rendered_publications:
            continue
        shown = rendered_disposition(line)
        if shown is None:
            raise ValidationError("prior_art.md displayed source needs an explicit disposition")
        referenced: list[dict] = []
        for raw_source_id in source_ids:
            source = source_by_id.get(raw_source_id.upper())
            if source is None:
                raise ValidationError("prior_art.md references an unknown source_id")
            referenced.append(source)
        for publication in rendered_publications:
            matches = by_publication.get(publication, [])
            if len(matches) != 1:
                raise ValidationError("prior_art.md publication number must resolve to exactly one canonical patent source")
            referenced.append(matches[0])
        # A line that gives both an SRC record and a publication must name the same
        # canonical source.  Deduplicate after identity reconciliation.
        unique = {source["source_id"]: source for source in referenced}
        if len(unique) != 1:
            raise ValidationError("prior_art.md source ID and publication number resolve to different canonical sources")
        for source in unique.values():
            source_id = source["source_id"]
            canonical = structured.get(source_id)
            # A displayed disposition is a statement about the canonical ledger,
            # not a free-form label; no structured record means no valid display.
            if canonical is None:
                # Preserve the stronger critical-date/missing-metadata diagnosis for
                # a rendered qualifying patent, then require ledger disposition.
                if shown == "qualifying_prior_art":
                    if source.get("source_type") != "patent" or source.get("verification_status") != "verified" or not source.get("publication_date") or not source.get("accessed_at") or not source.get("canonical_url"):
                        raise ValidationError("qualifying prior art needs canonical URL, access date, verified publication date, and verified status")
                    if case.get("critical_date") and source["publication_date"] > case["critical_date"]:
                        raise ValidationError("post-critical-date patent cannot be qualifying prior art")
                # Legacy/source-ID form is permitted when the line directly names
                # the canonical record and all qualifying checks above pass.  A
                # publication-number-only display has no such explicit ledger key
                # and must carry a structured disposition for reconciliation.
                if not source_ids:
                    raise ValidationError("prior_art.md displayed source lacks structured source disposition")
                continue
            if canonical != shown:
                raise ValidationError("prior_art.md source disposition differs from structured source record")
            if shown == "qualifying_prior_art":
                if source.get("source_type") != "patent" or source.get("verification_status") != "verified" or not source.get("publication_date") or not source.get("accessed_at") or not source.get("canonical_url"):
                    raise ValidationError("qualifying prior art needs canonical URL, access date, verified publication date, and verified status")
                if case.get("critical_date") and source["publication_date"] > case["critical_date"]:
                    raise ValidationError("post-critical-date patent cannot be qualifying prior art")
    for source in sources:
        if source.get("legal_status") in {"expired", "lapsed", "ceased"}:
            authority = source.get("legal_status_source_id")
            if authority not in source_by_id or source_by_id[authority].get("verification_status") != "verified":
                raise ValidationError("patent legal-status assertion needs authoritative verified source")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("case_dir", type=Path); args = parser.parse_args()
    try:
        case, paths, sources, evidence, trace = read_case(args.case_dir)
        score = load_json(paths["scorecard"])
        required = {"schema_version", "generated_at", "evidence_coverage_pct", "unsupported_measured_claims", "duplicate_patent_families", "claim_trace_coverage_pct", "bilingual_atomic_consistency_pct", "confidentiality_findings", "blocking_findings", "status"}
        if not isinstance(score, dict) or required - set(score): raise ValidationError("scorecard missing required fields")
        if score["schema_version"] != "0.1.0": raise ValidationError("scorecard schema mismatch")
        if score["status"] not in {"BLOCKED", "CANDIDATE_CHECKS_PASSED"}: raise ValidationError("scorecard terminal status is acceptance-owned")
        if not isinstance(score["blocking_findings"], list): raise ValidationError("scorecard blocking_findings must be array")

        claims = rendered_claim_inventory(paths)
        # An initialized case is deliberately a blocked drafting shell, not an invalid
        # case.  It has no trace or rendered claims yet and cannot be packaged.
        if not claims and not trace:
            if score["status"] != "BLOCKED" or not score["blocking_findings"]:
                raise ValidationError("empty case must remain explicitly BLOCKED")
            print(f"VALID: {case['case_id']} (initialized BLOCKED case)")
            return 0
        if not claims:
            raise ValidationError("rendered claims.md has no numbered claims")
        trace_keys = collections.Counter((row["claim_number"], _normalise_space(str(row["limitation_text"]))) for row in trace)
        rendered_atoms = [atom for claim in claims for atom in rendered_claim_atoms(claim)]
        rendered_keys = collections.Counter((atom["claim_number"], _normalise_space(str(atom["text"]))) for atom in rendered_atoms)
        if trace_keys != rendered_keys:
            raise ValidationError("rendered claims inventory differs from claim trace at atom level (every atom requires exactly one trace)")
        for claim in claims:
            atoms = rendered_claim_atoms(claim)
            matching = [
                row for atom in atoms for row in trace
                if row["claim_number"] == claim["claim_number"] and _normalise_space(str(row["limitation_text"])) == _normalise_space(str(atom["text"]))
            ]
            if not matching or any(row["parent_claim_number"] != claim["parent_claim_number"] for row in matching):
                raise ValidationError("rendered claim dependency differs from claim trace")
            if any(row["semantic_status"] in {"inferred", "designed"} and row["human_review_status"] != "accepted" for row in matching):
                raise ValidationError("inferred/designed limitation lacks human acceptance")

        independent = [row for row in claims if row["parent_claim_number"] is None]
        if case["patent_type"] == "utility_model" and (not independent or not all(_utility_model_is_structural(str(row["text"])) for row in independent)):
            raise ValidationError("every utility-model independent claim must be structural product")

        evidence_by_id = {item["evidence_id"]: item for item in evidence}
        for row in trace:
            if not any(_trace_evidence_matches(str(row["limitation_text"]), evidence_by_id[evidence_id]) for evidence_id in row["evidence_ids"]):
                raise ValidationError("claim trace limitation lacks a proposition-level evidence binding")

        resolved_language = None
        if case["language"] == "auto":
            resolved_language = load_json(paths["stages"])[0]["resolved_language"]
            _validate_auto_output_language(paths, claims, trace, resolved_language)

        prior = paths["output"] / "prior_art.md"
        _validate_prior_art(case, sources, prior.read_text(encoding="utf-8") if prior.exists() else "")

        outputs = "\n".join(path.read_text(encoding="utf-8") for path in paths["output"].glob("*.md"))
        achieved = [clause for clause in output_clauses(outputs) if is_unsupported_achieved(clause)]
        unsupported = sum(not _achieved_evidence_matches(clause, evidence) for clause in achieved)
        families = [row.get("family_id") for row in sources if row.get("source_type") == "patent" and row.get("family_id")]
        duplicate_families = len(families) - len(set(families))
        trace_coverage = 100.0 * sum(rendered_keys[key] for key in rendered_keys if key in trace_keys and trace_keys[key] == rendered_keys[key]) / len(rendered_atoms)
        expected_language = resolved_language if case["language"] == "auto" else (case["language"] if case["language"] in {"zh-CN", "en-US"} else None)
        statements = statement_inventory(paths, trace, expected_language)
        for statement in statements:
            if not statement["evidence_ids"]:
                statement["evidence_ids"] = _narrative_statement_evidence(str(statement["text"]), evidence, trace)
        evidenced = sum(1 for statement in statements if statement["evidence_ids"])
        evidence_coverage = 100.0 * evidenced / len(statements) if statements else 0.0
        bilingual = case["language"] == "bilingual"
        bilingual_consistency = 100.0 if bilingual and not any(row["semantic_status"] == "conflict" for row in trace) else (None if not bilingual else 0.0)
        expected = {"evidence_coverage_pct": evidence_coverage, "unsupported_measured_claims": unsupported, "duplicate_patent_families": duplicate_families, "claim_trace_coverage_pct": trace_coverage, "bilingual_atomic_consistency_pct": bilingual_consistency}
        if unsupported:
            diagnostic = ""
            # Acceptance fixtures contain synthetic public text.  An explicit CI
            # diagnostic flag may expose only those clauses to make cross-platform
            # false positives actionable; normal case validation never echoes a
            # user's draft content.
            if os.environ.get("EFPS_FIXTURE_DIAGNOSTICS") == "1":
                diagnostic = ": " + repr([clause for clause in achieved if not _achieved_evidence_matches(clause, evidence)])
            raise ValidationError("unsupported_measured_claims contains achieved result(s) without matching verified measured evidence" + diagnostic)
        if any(score[key] != value for key, value in expected.items()):
            raise ValidationError("scorecard metrics are not reconciled with canonical evidence and rendered claims")
        blockers = []
        if unsupported: blockers.append("unsupported_measured_claims")
        if duplicate_families: blockers.append("duplicate_patent_families")
        if trace_coverage != 100.0: blockers.append("claim_trace_coverage_pct")
        if evidence_coverage != 100.0: blockers.append("evidence_coverage_pct")
        if bilingual and bilingual_consistency != 100.0: blockers.append("bilingual_atomic_consistency_pct")
        if bool(score["blocking_findings"]) != bool(blockers) or (score["status"] == "CANDIDATE_CHECKS_PASSED") != (not blockers):
            raise ValidationError("scorecard blocking_findings/status are not reconciled with computed blockers")

        print(f"VALID: {case['case_id']} ({len(sources)} sources, {len(evidence)} evidence, {len(trace)} limitations)")
        return 0
    except ValidationError as exc:
        return command_error(exc)


if __name__ == "__main__":
    sys.exit(main())
