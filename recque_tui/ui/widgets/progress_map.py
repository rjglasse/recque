"""The recursive-descent progress skyline.

Renders one column per skill in the upper region of the question screen:
each box is a level of the descent, coloured by state. A skill drilled deeper
grows a taller column; the active box (where the learner is now) is bracketed.
"""

from textual.widgets import Static

from recque_tui.core.session import BoxState, SkillColumn

# Muted palette, matching the calm theme — no loud accents.
_COLOR = {
    BoxState.CORRECT: "#8faa8b",   # sage
    BoxState.WRONG: "#c2908f",     # dusty rose
    BoxState.PENDING: "#555555",   # quiet grey
}
# Slightly brighter for the box the learner is currently on.
_ACTIVE_COLOR = {
    BoxState.CORRECT: "#a6c0a2",
    BoxState.WRONG: "#d6a9a8",
    BoxState.PENDING: "#9aa0a6",
}

_GLYPH = "██"
_CELL_WIDTH = 4
# Keep the skyline bounded in the upper region. Deeper descents are truncated
# at the bottom with a "⋯" marker; short columns (future skills) stay intact.
_MAX_ROWS = 7


class ProgressMap(Static):
    """A skyline of skill columns; call `update_view` with `Session.progress_view()`."""

    def update_view(self, columns: list[SkillColumn]) -> None:
        if not columns:
            self.update("")
            return

        height = max((len(c.boxes) for c in columns), default=0)
        rows = min(height, _MAX_ROWS)
        last = _MAX_ROWS - 1  # row index that shows "⋯" for over-long columns

        header = "".join(f"[#7a7a7a]{c.label:^{_CELL_WIDTH}}[/]" for c in columns)
        lines = [header]

        for row in range(rows):
            cells = []
            for column in columns:
                if height > _MAX_ROWS and row == last and len(column.boxes) > _MAX_ROWS:
                    cells.append(f"[#7a7a7a]{'⋯':^{_CELL_WIDTH}}[/]")
                elif row < len(column.boxes):
                    state = column.boxes[row]
                    if column.active == row:
                        cells.append(f"[{_ACTIVE_COLOR[state]} b]\\[{_GLYPH}][/]")
                    else:
                        cells.append(f"[{_COLOR[state]}] {_GLYPH} [/]")
                else:
                    cells.append(" " * _CELL_WIDTH)
            lines.append("".join(cells))

        self.update("\n".join(lines))
