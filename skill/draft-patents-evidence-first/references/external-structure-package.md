# Counsel-facing structure package / 对外结构包

Use this reference after the human selection gate when a patent professional returns annotated drawings, a technical disclosure, or a request for point-by-point clarification. It is a drafting-quality control for a counsel-facing package; it does not determine legal scope, patentability, or filing readiness.

## 1. Separate the two deliverables

Maintain two deliberately different layers.

| Layer | Intended reader | Include | Exclude |
|---|---|---|---|
| External structure package | Patent professional | Revised disclosure, point-by-point answers, and formal figures; only checkable components, connections, relative positions, force paths, disassembly paths, and dimension chains | Evidence class, source identity, missing-sample status, review instructions, search strategy, protection strategy, committee notes, unresolved placeholders, and unsupported performance statements |
| Internal sidecar | Project team and reviewer | Comment-to-text-to-figure matrix, evidence and uncertainty status, review findings, risk notes, change log, and claim-synchronization reminders | Material intended to be pasted into the external disclosure or formal figures |

Do not “clean up” an unresolved engineering fact merely by deleting its uncertainty label. If the human-approved technical baseline does not settle a fact, retain it as an internal issue and obtain a human decision before making an external structural assertion.

## 2. Build one master-assembly ledger before redrafting

Create and review one ledger before writing or redrawing. Each row must identify:

1. **Component and reference sign** — one preferred Chinese name and one stable sign.
2. **Relationship** — connection, support, clearance, contact, movement, limit, or removal relation, with the two or more participating components named.
3. **Text location** — the unique external paragraph that defines the relation.
4. **Figure location** — the primary figure and callout, section, projection, or dimension that shows it.
5. **Comment linkage** — every attorney comment affected by the relation.
6. **Claim-sync note** — an internal reminder only; never silently expand or narrow a formal claim.

Use one master assembly for all views. A general assembly view, a plan view, a component sectional view, a comparative dimension-chain view, and a local contact section may show different projections of the same device, but must not become separately invented structures.

For a mechanical figure set with moving members, stop faces, clearances, disassembly, or comparative dimensions, apply [mechanical-figure-consistency.md](mechanical-figure-consistency.md). Its state-aware ledger and shared sectional primitive are the controlling method for preventing cross-view geometry drift.

## 3. Draft external text in checkable Chinese patent language

Use direct structural verbs such as “设置”“形成”“固定”“螺纹配合”“穿设”“抵接”“连通”“承托”“压持”“轴向移动” and “沿轴向取出”. Define a term once, then use the same name and sign throughout.

When a connection has two independent interfaces, state all of the following together in the same paragraph and show them together in the sectional view:

- the first pair of components and its mating features;
- the second pair of components and its mating features;
- their different axial or spatial locations, when material to the distinction; and
- the removal path and the component that remains fixed during removal.

Do not replace a specific relation with shorthand such as “A is fixed to B” where the response turns on distinguishing thread locations, a pass-through bore, a shoulder, a clearance, or a stop face.

Do not add materials, numerical sizes, preload forces, thermal effects, airflow effects, sealing effects, or performance improvements unless they are within the human-approved, traceable external boundary. Where a number is not established, specify the relevant structural reference faces, position relationship, or travel relationship instead of writing a “to be determined” placeholder.

## 4. Treat figures as a single evidence-bearing set

Use clean black-and-white line drawings with stable reference signs. A formal figure set should make the following independently readable where applicable:

- the support/contact chain, for example pressure member—workpiece—support—base;
- the fixed connection between a frame and a base, including the intended count only when that count is part of the approved structure;
- two ends of a physical slot or opening path, without adding unverified thermal or flow effects;
- each thread or other interface at its actual location;
- ordinary travel clearance separately from a maximum-travel stop condition; and
- a comparative dimension chain, including the named parts, reference faces, and unequal dimensions that create the stated assembly condition.

Every callout must point to the intended geometry. A sectional view must not make a moving shoulder appear to contact a guide wall during ordinary travel if the text says there is a radial clearance. A plan view must not imply that a pressure member acts in an avoidance region if the local contact section says otherwise.

## 5. Use a fixed response format for every annotation

For each attorney annotation, provide these five external fields in this order:

1. **Annotation question**
2. **Clear conclusion**
3. **Revised structural explanation**
4. **Corresponding disclosure section**
5. **Figure number and marked location**

The final field must identify the actual callout, section, projection, dimension, or contact region—not merely list a figure number. The answer can name supporting figures where useful, but the internal ledger must identify one primary text location and one primary visual location for resolving the question.

## 6. Claim-synchronization boundary

Check whether a changed term, component count, connection interface, or dimension-chain relation needs to be synchronized with the claim framework. Record the result in the internal sidecar as a recommendation for the patent professional.

Do not draft a replacement claim, silently change claim scope, or represent a claim strategy decision as a technical fact unless the user has expressly authorized that work.

## 7. Final acceptance gate

Before handing off an external structure package, independently check:

- every annotation has all five response fields and an actionable primary mapping;
- each reference sign has one name and one consistent geometry across text and figures;
- each connection, clearance, stop, contact chain, and disassembly path is non-contradictory in the master ledger;
- figures are derived from one master assembly and have no caption, sign, arrow, section, or dimension drift;
- external files contain no internal review language or unsupported effect claim; and
- the rendered documents have been visually reviewed for page breaks, clipped callouts, unreadable dimensions, missing glyphs, and figure/text mismatch.

For multi-view mechanical figures, the rendered check must include both normal and maximum-travel states where applicable, an interference-free removal path, visibly open slot mouths, a closed support/contact chain, and a clean-line text-token audit. Review a normal-resolution render and a high-resolution render rather than relying on the editable source alone.

Keep review records and acceptance findings in the internal sidecar. An external package may be ready for professional review, but it is never a substitute for qualified counsel review before filing or disclosure.
