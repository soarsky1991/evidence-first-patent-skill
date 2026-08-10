# Mechanical figure-set consistency / 机械附图组一致性

Use this reference when a counsel-facing package contains several views of one mechanical assembly, especially when comments concern thread locations, movement clearances, stop faces, disassembly, support chains, slots, or comparative preload dimensions. It governs drafting and review only; it does not establish legal scope or filing readiness.

## 1. Freeze one structural truth before drawing

Create a state-aware relation ledger before opening a drawing tool. For every relation, record:

- the participating components and stable reference signs;
- which component owns each surface, shoulder, slot, bore, or thread;
- whether each component is fixed, removable, or moving;
- the normal state, maximum-travel state, and removal state when applicable;
- the axial/radial clearance, contact, support, or stop relation;
- the primary text paragraph and primary figure location; and
- the approved source or human decision that settles the relation.

Do not let a convenient sketch override this ledger. If the text, an older CAD view, and an approved engineering decision conflict, preserve the conflict internally and resolve the controlling baseline before producing a clean external figure.

## 2. Derive every view from a shared sectional primitive

Treat the controlling component section as the single source of geometry. Reuse or mechanically derive it for the component section, comparison view, local contact section, and exterior assembly projection. Do not redraw each view independently.

The shared primitive must preserve:

- component ownership of faces and interfaces;
- axial order of covers, spacers, springs, shoulders, rods, feet, supports, and bases;
- bore and central-passage continuity;
- radial clearances around moving members;
- ordinary-travel and maximum-travel positions; and
- contact or support chains through the workpiece.

A plan view may simplify depth, and an assembly view may hide internal details, but neither may introduce a different component count, interface, travel direction, or support order.

## 3. Prove movement and absence of interference

For every moving chain, identify the fixed body, moving body, force-transmitting members, and travel direction. Then show at least two states when a stop relation matters:

1. **Normal state** — the moving stop surface remains separated from the fixed stop surface by an axial gap.
2. **Maximum-travel state** — the moving surface reaches and contacts the fixed surface.

Draw an inward stop as side material with a real central passage when a rod must pass through it. Never use a full-width plate that closes the movement channel. A moving shoulder must remain inside the guide bore with visible radial clearance unless contact with the wall is an approved feature.

Place reference signs on the actual owning face or feature. Do not label a nearby volume in a way that reverses which component owns the stop surface.

## 4. Separate interfaces and preserve the removal path

When two threaded or otherwise detachable interfaces exist, show both in one controlling section at their real, distinct locations. The external explanation must identify:

- the two mating component pairs;
- the mating features on each pair;
- which interface is released first;
- the direction in which the removable member exits; and
- which installed component remains fixed during removal.

Run a visual removal-path check: after the stated interface is released, no remaining shoulder, cover, wall, or stop may block the member that is said to be withdrawn.

## 5. Keep openings, projections, and contact zones topologically honest

If a slot is described as connecting an internal opening to an outer perimeter, both ends must be visibly open. Draw its longitudinal boundaries but do not add a closing line at either mouth.

When a pressure member must avoid an opening or reserved region, show their same-plane projections with a visible interval. A section through the support chain does not by itself prove non-overlap in plan.

Do not attach airflow, heat-transfer, sealing, stiffness, or other effects to an opening unless those effects are inside the approved and traceable boundary.

## 6. Compare dimensions without changing the mechanism

For comparative preload or assembly-condition figures, copy the same component primitive and change only the approved variable. Use common reference lines for the relevant upper face, force-receiving face, and lower stop/contact position.

If unequal spacer lengths create different initial compression, label the two dimensions from the same type of reference faces. Keep the spring specification, stop geometry, movement chain, and comparison state identical unless the approved baseline expressly changes them.

## 7. Produce annotated and clean-line variants from one source

Generate two outputs from the same geometry:

| Variant | Permitted content |
|---|---|
| Counsel-review variant | Stable reference signs, Chinese structural names, interface/removal explanations, state labels, and projection or dimension notes needed for technical confirmation |
| Clean-line variant | Geometry, section hatching, leader lines, reference signs, and indispensable dimension symbols only |

The clean-line variant must not contain review instructions, evidence labels, committee findings, uncertainty notes, unsupported effects, prose captions, or state explanations. Prefer a character allowlist audit in addition to visual review.

## 8. Run independent repair and adversarial review

Use two independent roles after rendering:

- **Repair review** checks physical interference, movement paths, interface locations, removal, slot topology, support/contact chains, and shared-geometry reuse.
- **Adversarial review** checks component ownership, cross-view sign stability, text-to-figure mappings, clean-line purity, and regression against the approved baseline.

Record each result as `Finding / Evidence / Impact / Fix / Priority / Confidence`. Review the actual rendered pages, not only source code or drawing objects. A pass requires zero unresolved P0/P1 findings; one committee's pass must not substitute for the other's review.

## 9. Rendered acceptance gate

Before handoff:

- confirm page count, orientation, and intended figure order;
- render every page at a normal review resolution and a high-resolution inspection setting (for example, 300 dpi and 600 dpi);
- inspect callout endpoints, thread bands, hatch boundaries, open slot mouths, face labels, dimensions, glyphs, and clipping;
- verify that the clean-line file contains only its allowed text tokens;
- confirm that regenerated review images correspond to the exact final PDF bytes; and
- retain the relation ledger, findings, hashes, and change history in the internal sidecar.

Passing this gate means the figure set is internally consistent enough for human patent-professional review. It is not a legal conclusion and does not authorize filing or public disclosure.
