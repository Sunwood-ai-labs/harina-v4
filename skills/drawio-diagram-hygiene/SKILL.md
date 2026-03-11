---
name: drawio-diagram-hygiene
description: Improve diagrams.net and draw.io diagrams by reducing overlap between connectors, boxes, and text, and by applying consistent routing, spacing, and label placement. Use when Codex edits `.drawio` or `mxfile` diagrams, reviews unreadable layouts, or needs to reroute connectors and clean labels without changing diagram meaning.
---

# Drawio Diagram Hygiene

Keep the diagram's meaning stable while making it easier to scan. Prefer small XML edits that reduce collisions over large manual rearrangements.

Read [references/layout-rules.md](references/layout-rules.md) before editing when the diagram has more than a handful of edges or any long return path.

## Workflow

1. Inspect the target `.drawio` / `mxfile` and identify the clutter source:
   - long back edges that cut across active content
   - edge labels sitting directly on busy connectors
   - nodes that are too short for wrapped text
   - notes or container titles placed in connector corridors
2. Preserve semantics first:
   - do not rename nodes, remove connections, or change the process flow unless the user asks
   - prefer rerouting, resizing, spacing, or label treatment changes
3. Normalize the layout:
   - keep one dominant flow direction per page, usually left-to-right
   - route exceptions and feedback loops on the outer perimeter, not through the middle of the diagram
   - keep sibling nodes aligned and leave visible gutters between them
4. Clean edges before moving nodes:
   - keep `edgeStyle=orthogonalEdgeStyle` unless the file already uses another deliberate style
   - add explicit waypoints for long or returning edges
   - add `labelBackgroundColor=#FFFFFF;labelBorderColor=none;spacing=6;` to labeled edges so text remains readable even when a crossing is unavoidable
   - shorten edge labels; move explanatory prose into a separate text note instead of a long edge label
5. Clean nodes only as needed:
   - increase box height before reducing font size
   - keep `whiteSpace=wrap`
   - if a connector still collides with text, move the text into its own note cell or reroute the connector around the box
6. Re-read the XML and sanity-check the riskiest edges:
   - look for waypoint y/x coordinates that run through another node's bounds
   - ensure any long perimeter route stays outside containers and title areas

## Default Rules

- Leave roughly `40-80` px between sibling nodes when space allows.
- Reserve a top or bottom corridor for long return lines.
- Prefer node labels of `2-3` lines max; resize the box if the content is longer.
- Prefer short edge labels like `extract`, `append row`, or `test only`.
- Use separate note blocks for multi-clause explanations.

## XML Patterns

Use this style fragment for labeled connectors:

```xml
style="edgeStyle=orthogonalEdgeStyle;rounded=0;jettySize=auto;html=1;strokeWidth=2;labelBackgroundColor=#FFFFFF;labelBorderColor=none;spacing=6;"
```

Use explicit perimeter waypoints for long back edges:

```xml
<Array as="points">
  <mxPoint x="1560" y="60" />
  <mxPoint x="425" y="60" />
</Array>
```

## Output Expectations

- Keep diffs tight and readable.
- Mention the specific edges or nodes that were rerouted or resized.
- If the file is too dense to fix safely in one pass, say so and recommend splitting the diagram into multiple pages or lanes.
