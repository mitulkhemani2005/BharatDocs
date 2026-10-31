import type { Rect, TranslationArea } from "./api-client"

const overlaps = (a: Rect, b: Rect) => Math.max(a[0], b[0]) < Math.min(a[2], b[2]) && Math.max(a[1], b[1]) < Math.min(a[3], b[3])

/** Keep every named area intact. Moved areas snap when space is available. */
export function resolveAreaOverlap(areas: TranslationArea[], selected: number, width: number, height: number, moving = false) {
  const active = { ...areas[selected] }
  let rect = active.rect
  const peers = areas.filter((area, i) => i !== selected && (area.mode || "translate") === (active.mode || "translate"))
  if (moving && peers.some(area => overlaps(rect, area.rect))) {
    const w = rect[2] - rect[0], h = rect[3] - rect[1]
    const xs = [rect[0], 0, width - w, ...peers.flatMap(area => [area.rect[0] - w, area.rect[2]])]
    const ys = [rect[1], 0, height - h, ...peers.flatMap(area => [area.rect[1] - h, area.rect[3]])]
    const candidates = xs.flatMap(x => ys.map(y => [x, y, x + w, y + h] as Rect))
      .filter(candidate => candidate[0] >= 0 && candidate[1] >= 0 && candidate[2] <= width && candidate[3] <= height && peers.every(area => !overlaps(candidate, area.rect)))
      .sort((a, b) => Math.hypot(a[0] - rect[0], a[1] - rect[1]) - Math.hypot(b[0] - rect[0], b[1] - rect[1]))
    if (candidates.length) rect = candidates[0]
  }
  const adjusted = rect.some((value, i) => value !== active.rect[i])
  const regions = areas.map((area, i) => i === selected ? { ...area, rect, text_rect: null } : area)
  return { regions, selected, adjusted, merged: false }
}
