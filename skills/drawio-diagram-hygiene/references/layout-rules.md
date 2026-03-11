# Layout Rules

Use this reference when editing busy diagrams.net files.

## Highest-value fixes

1. Move long return paths to the page perimeter.
2. Give labeled edges a white label background.
3. Expand boxes before shrinking fonts.
4. Replace long edge prose with separate text notes.

## Collision checklist

- Does a waypoint run through another node's `x/y/width/height` area?
- Does an edge label sit on a crossing or junction?
- Does a container title share the same corridor as a long connector?
- Does a wrapped label need another line of height?

## Safe XML edits

- Edge style cleanup:

```xml
labelBackgroundColor=#FFFFFF;labelBorderColor=none;spacing=6;
```

- Prefer perimeter routes for cross-lane feedback:

```xml
<Array as="points">
  <mxPoint x="..." y="60" />
  <mxPoint x="..." y="60" />
</Array>
```

- Keep note cells separate from process boxes:

```xml
style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;"
```

## When not to over-fix

- Do not completely relayout a stable diagram just to make it prettier.
- Do not introduce diagonal connectors into an orthogonal diagram unless the file already uses them deliberately.
- Do not compress fonts below the rest of the page just to avoid resizing one box.
