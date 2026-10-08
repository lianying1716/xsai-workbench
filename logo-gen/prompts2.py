# 第二轮：避开"四角星/sparkle"这个烂大街符号，改从"采/集/叠"的几何关系入手
COMMON = (
    "flat vector logo mark, bold geometric construction, solid shapes, thick confident strokes, "
    "high contrast, strong simple silhouette, balanced negative space, centered with generous margin, "
    "single mark only, no text, no lettering, no words, no numbers, no gradient, no shadow, no 3D, "
    "no mockup, no watermark, plain flat light background, monochrome black"
)

PROMPTS = {
# 用"采集"的动词关系，而不是星
"11-harvest-comb": (
 "a bold vertical comb of five thick parallel prongs of equal width and equal spacing, "
 "three of the prongs are cut shorter from the top so their top edges form a descending diagonal "
 "staircase, like harvesting teeth combing downward"
),
"12-layer-lift": (
 "three thick horizontal rectangular bars stacked with equal gaps, each bar shifted progressively "
 "to the right so the left edges form a diagonal staircase, and the rightmost bar extends upward "
 "into a vertical stem, building an abstract lifted shape"
),
"13-fold-corner": (
 "a thick square outline whose bottom right quadrant is replaced by a solid filled square, "
 "and a second smaller solid square sits folded outside the top left corner at 45 degrees, "
 "suggesting layered sheets being gathered"
),
"14-diamond-cut": (
 "a large solid diamond (square rotated 45 degrees) with one straight vertical slice removed from "
 "its left half and relocated as a floating bar to the right, creating a crisp offset gap through "
 "the whole form, like a geometric cut and splice"
),
"15-gate-collect": (
 "two thick vertical pillars of different heights on the left and right, and a horizontal bar "
 "spanning between them near the top, with a solid filled square nested in the opening below the bar, "
 "like a dropped item resting in a frame"
),
"16-spiral-in": (
 "four thick straight arms of identical width arranged in a rotational pinwheel around the center, "
 "each arm rotated 90 degrees from the previous and offset so they spiral inward, the center left "
 "as a clean square hole"
),
}
