"""Draw the profile cards in cards/ and write README.md.

    python generator/build.py

Reads data/profile.json (what I say and what I have shipped), data/work.json (the
language mix and median change size, from mine.py) and data/calendar.json (GitHub's
contribution calendar). Every letter is an outline taken from Martian Mono, so a card
looks the same on any machine and never waits for a font to load.

No card says how many commits sit in a private repository, or what they touched: the
cards show the systems, not someone else's git history.
"""
import datetime
import hashlib
import html
import json
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "generator" / "fonts" / "MartianMono-VF.ttf"
OUT = ROOT / "cards"

W = 412          # one card; two sit side by side on a desktop and stack on a phone
W_WIDE = 2 * W   # the banner: as wide as two cards, so it fills the README column
PAD = 28
INNER = W - 2 * PAD
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# name: (weight, width) on the variable font's two axes
STYLES = {"body": (400, 87.5), "strong": (700, 87.5), "label": (500, 75), "display": (800, 112.5)}

# Black is neutral black, never navy. One accent, and it never carries data.
THEMES = {
    "dark": dict(surface="#0a0a0a", ink="#f4f4f4", ink2="#b8b8b8", muted="#7d7d7d",
                 faint="#565656", hair="#2b2b2b", track="#1d1d1d", accent="#ff453a"),
    "light": dict(surface="#ffffff", ink="#0a0a0a", ink2="#3a3a3a", muted="#6e6e6e",
                  faint="#a6a6a6", hair="#e3e3e3", track="#efefef", accent="#d7261e"),
}

# Every frame of every animation is a complete card: nothing waits for a clock to appear.
# (A browser freezes SVG animations in a hidden tab, and a card that grows in from
# nothing would sit there empty.)
CSS = (
    "@keyframes blink{0%,55%{opacity:1}78%{opacity:.2}100%{opacity:1}}"
    ".blink{animation:blink 2.6s ease-in-out infinite}"
    ".sweep{opacity:0}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
)


def sweep_css(name, axis, travel, seconds):
    """A thin line that crosses a block and fades at both ends; invisible when motion is off."""
    return (f"@keyframes {name}{{0%{{transform:translate{axis}(0);opacity:0}}8%{{opacity:.6}}"
            f"92%{{opacity:.6}}100%{{transform:translate{axis}({travel:.0f}px);opacity:0}}}}"
            f".{name}{{animation:{name} {seconds}s linear infinite}}")


def drift_css(name, tile, seconds):
    """A row of identical things sliding left by exactly one tile, so the loop has no seam."""
    return (f"@keyframes {name}{{to{{transform:translateX(-{tile:.2f}px)}}}}"
            f".{name}{{animation:{name} {seconds}s linear infinite}}")


def hop_css(name, travel, stops, seconds):
    """A marker that parks on one item at a time: every frame still shows a marked item."""
    return (f"@keyframes {name}{{to{{transform:translateY({travel:.1f}px)}}}}"
            f".{name}{{animation:{name} {seconds}s steps({stops}, jump-none) infinite}}")


class Face:
    """One static instance of the variable font, read as outlines."""

    def __init__(self, key, weight, width):
        font = instantiateVariableFont(TTFont(FONT), {"wght": weight, "wdth": width}, inplace=False)
        self.prefix = key[0]
        self.upm = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.glyphs = font.getGlyphSet()
        self.advance = font["hmtx"][self.cmap[ord("n")]][0]   # monospaced: one advance for all
        self.order = {name: i for i, name in enumerate(font.getGlyphOrder())}
        self.paths = {}

    def glyph(self, ch):
        name = self.cmap.get(ord(ch))
        if name is None:
            raise ValueError(f"Martian Mono has no glyph for {ch!r}")
        if name not in self.paths:
            pen = SVGPathPen(self.glyphs)
            self.glyphs[name].draw(pen)
            self.paths[name] = pen.getCommands()
        return f"{self.prefix}{self.order[name]}", self.paths[name]


FACES = {key: Face(key, *axes) for key, axes in STYLES.items()}


def char_width(style, size):
    face = FACES[style]
    return face.advance * size / face.upm


def wrap(text, style, size, max_width=INNER):
    per_line = int(max_width // char_width(style, size))
    lines, current = [], ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > per_line:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return lines + [current] if current else lines


def wrap_list(items, style, size, max_width=INNER, joiner=" · "):
    """Like wrap, but a line never starts or ends with the separator."""
    per_line = int(max_width // char_width(style, size))
    lines, current = [], ""
    for item in items:
        candidate = f"{current}{joiner}{item}" if current else item
        if current and len(candidate) > per_line:
            lines.append(current)
            current = item
        else:
            current = candidate
    return lines + [current] if current else lines


class Card:
    def __init__(self, name, height, theme, alt, width=W):
        self.name, self.h, self.theme, self.t, self.alt = name, height, theme, THEMES[theme], alt
        self.w = width
        self.defs, self.body, self.css = {}, [], ""
        self.shapes = []    # clip paths and the like, written next to the glyph outlines

    def add(self, markup):
        self.body.append(markup)

    def text(self, x, y, text, style="body", size=12, fill="ink", anchor="start"):
        face = FACES[style]
        scale = size / face.upm
        width = len(text) * char_width(style, size)
        if anchor == "end":
            x -= width
        elif anchor == "middle":
            x -= width / 2
        uses = []
        for i, ch in enumerate(text):
            if ch == " ":
                continue
            glyph_id, path = face.glyph(ch)
            self.defs[glyph_id] = path
            uses.append(f'<use href="#{glyph_id}" x="{i * face.advance}"/>')
        self.add(f'<g transform="translate({x:.2f} {y:.2f}) scale({scale:.5f} {-scale:.5f})" '
                 f'fill="{self.t[fill]}">{"".join(uses)}</g>')
        return width

    def lines(self, x, y, lines, style="body", size=12, fill="ink2", leading=1.6):
        for line in lines:
            self.text(x, y, line, style, size, fill)
            y += size * leading
        return y

    def heading(self, title, sub=None):
        self.text(PAD, 52, title, "strong", 14, "ink")
        if sub:
            self.lines(PAD, 72, wrap(sub, "label", 10.5), "label", 10.5, "muted", leading=1.45)

    def brackets(self, inset=12, arm=10):
        """Viewfinder corners: the frame of every card, joined in a row or stacked."""
        for x, y, dx, dy in ((inset, inset, 1, 1), (self.w - inset, inset, -1, 1),
                             (inset, self.h - inset, 1, -1), (self.w - inset, self.h - inset, -1, -1)):
            self.add(f'<path d="M{x + dx * arm} {y}H{x}V{y + dy * arm}" fill="none" '
                     f'stroke="{self.t["muted"]}" stroke-width="1.5"/>')

    def hairline(self, y, x1=PAD, x2=None):
        x2 = self.w - PAD if x2 is None else x2
        self.add(f'<path d="M{x1} {y}H{x2}" stroke="{self.t["hair"]}" stroke-width="1"/>')

    def svg(self):
        defs = "".join(f'<path id="{key}" d="{path}"/>' for key, path in sorted(self.defs.items()))
        alt = html.escape(self.alt, quote=True)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{alt}"><title>{alt}</title>'
                f'<style>{CSS}{self.css}</style><defs>{defs}{"".join(self.shapes)}</defs>'
                f'<rect width="{self.w}" height="{self.h}" fill="{self.t["surface"]}"/>'
                f'{"".join(self.body)}</svg>\n')


def day_label(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def longest_streak(days):
    best = run = 0
    previous = None
    for iso in sorted(d for d, n in days.items() if n > 0):
        d = datetime.date.fromisoformat(iso)
        run = run + 1 if previous and (d - previous).days == 1 else 1
        best, previous = max(best, run), d
    return best


# ---- cards ---------------------------------------------------------------------------

def block(x, y, w, h, body, hole):
    """A two-hole concrete block, drawn from the front: what the plant actually makes."""
    wall = 7
    bore = (w - 3 * wall) / 2
    holes = "".join(f'<rect x="{x + wall + i * (bore + wall):.2f}" y="{y + wall}" '
                    f'width="{bore:.2f}" height="{h - 2 * wall}" rx="1" fill="{hole}"/>'
                    for i in range(2))
    return f'<rect x="{x:.2f}" y="{y}" width="{w}" height="{h}" rx="2" fill="{body}"/>{holes}'


def card_line(theme, profile, work, calendar):
    """The wide card on top: blocks riding the line past the camera that counts them."""
    alt = (f'{profile["fullName"]} ({profile["login"]}), {profile["role"]}, {profile["place"]}. '
           "Concrete blocks ride a conveyor past a camera that reads the line.")
    c = Card("line", 232, theme, alt, width=W_WIDE)
    c.brackets()
    c.add(f'<circle class="blink" cx="{PAD + 4}" cy="44" r="4" fill="{c.t["accent"]}"/>')
    c.text(PAD + 16, 48, profile["login"], "strong", 12, "ink")
    c.text(c.w - PAD, 48, f'{profile["role"]} · {profile["place"]}', "label", 10.5, "muted",
           anchor="end")

    inner = c.w - 2 * PAD
    name = " ".join(profile["display"])
    size = min(inner / (len(name) * char_width("display", 1)), 46)
    c.text(PAD, 128, name, "display", size, "ink")
    c.hairline(150)
    c.text(PAD, 168, "block line", "label", 10.5, "muted")

    # The belt: one tile is a block plus the gap behind it, so sliding the row left by a
    # tile and starting over is seamless. Blocks and rollers ride in the same group,
    # which is why they never drift apart. Keep a tile wide enough that the camera frame
    # never touches the blocks either side of the one it is reading.
    tile, bw, bh, pitch = 92, 46, 28, 23
    top, surface = 178, 206
    cam = PAD + 6 * tile + bw / 2        # a block sits dead centre under the camera at t=0
    c.shapes.append(f'<clipPath id="belt"><rect x="{PAD}" y="160" width="{inner}" height="60"/>'
                    "</clipPath>")

    riders = [block(PAD + k * tile, top, bw, bh, c.t["ink2"], c.t["surface"])
              for k in range(int(inner / tile) + 2)]
    rollers = "".join(f"M{PAD + i * pitch} {surface + 4}v5"
                      for i in range(int((inner + tile) / pitch) + 1))
    c.add(f'<g clip-path="url(#belt)"><g class="belt">{"".join(riders)}'
          f'<path d="{rollers}" stroke="{c.t["faint"]}" stroke-width="1.5"/></g>'
          f'<path d="M{PAD} {surface}H{c.w - PAD}" stroke="{c.t["ink2"]}" stroke-width="1.5"/></g>')

    # The camera is bolted in place: the frame stays put and brightens as each block
    # arrives under it. Dimmed, it is still a frame, so a frozen tab shows a whole card.
    box, lift = bw + 18, 8
    frame_h = surface + lift - (top - lift)
    c.add(f'<g class="watch" stroke="{c.t["accent"]}" fill="none">'
          f'<rect x="{cam - box / 2}" y="{top - lift}" width="{box}" height="{frame_h}" '
          f'stroke-width="1" stroke-opacity=".35"/>'
          + "".join(f'<path d="M{x + dx * 12} {y}H{x}V{y + dy * 12}" stroke-width="2"/>'
                    for x, y, dx, dy in ((cam - box / 2, top - lift, 1, 1),
                                         (cam + box / 2, top - lift, -1, 1),
                                         (cam - box / 2, surface + lift, 1, -1),
                                         (cam + box / 2, surface + lift, -1, -1)))
          + f'<circle cx="{cam + box / 2}" cy="{top - lift}" r="2.5" '
          f'fill="{c.t["accent"]}" stroke="none"/></g>')

    c.css = (drift_css("belt", tile, 2.3)
             + "@keyframes watch{0%,100%{opacity:1}38%,72%{opacity:.3}}"
             + ".watch{animation:watch 2.3s ease-in-out infinite}"
             + sweep_css("glint", "X", inner, 9))
    c.add(f'<rect class="sweep glint" x="{PAD}" y="{128 - size:.1f}" width="1" '
          f'height="{size * 1.15:.1f}" fill="{c.t["accent"]}"/>')
    return c


def card_id(theme, profile, work, calendar):
    alt = f'{profile["fullName"]} ({profile["login"]}). {profile["role"]}, {profile["place"]}.'
    c = Card("id", 328, theme, alt)
    c.brackets()
    c.add(f'<circle class="blink" cx="{PAD + 4}" cy="48" r="4" fill="{c.t["accent"]}"/>')
    c.text(PAD + 16, 52, profile["login"], "strong", 12, "ink")
    c.text(W - PAD, 52, profile["place"], "label", 10.5, "muted", anchor="end")

    longest = max(len(line) for line in profile["display"])
    size = min(INNER / (longest * FACES["display"].advance / 1000), 62)
    y = 150
    for line in profile["display"]:
        c.text(PAD, y, line, "display", size, "ink")
        y += size * 1.2

    # A ruler under the name: one tick every 8 px, a taller one every fifth.
    ruler = y - size * 1.2 + 26
    ticks = "".join(f"M{PAD + i * 8} {ruler}v{-7 if i % 5 == 0 else -3}" for i in range(INNER // 8 + 1))
    c.add(f'<path d="M{PAD} {ruler}H{W - PAD}{ticks}" fill="none" stroke="{c.t["faint"]}" stroke-width="1"/>')

    top = 150 - size
    c.css = sweep_css("scan", "Y", ruler - top, 7)
    c.add(f'<rect class="sweep scan" x="{PAD}" y="{top:.1f}" width="{INNER}" height="1" fill="{c.t["accent"]}"/>')

    c.text(PAD, ruler + 28, profile["role"], "body", 13, "ink2")
    c.text(PAD, ruler + 48, profile["fullName"], "label", 10.5, "muted")
    return c


def card_about(theme, profile, work, calendar):
    # Nothing here describes an employer's system: not how many modules it has, not who
    # uses it, not which processes it covers. That inventory is theirs, and this is public.
    alt = "About. " + " ".join(profile["about"]) + " " + profile["aboutFoot"]
    c = Card("about", 328, theme, alt)
    c.brackets()
    c.heading("About")
    y = 84
    for paragraph in profile["about"]:
        lines = wrap(paragraph, "body", 12)
        y = c.lines(PAD, y, lines, "body", 12, "ink2", leading=1.58)
        baseline, tail = y - 12 * 1.58, lines[-1]
        y += 7

    # A cursor parked after the last word, blinking where I stopped typing.
    c.add(f'<rect class="blink" x="{PAD + len(tail) * char_width("body", 12) + 3:.1f}" '
          f'y="{baseline - 10:.1f}" width="2" height="12" fill="{c.t["accent"]}"/>')

    foot = wrap(profile["aboutFoot"], "body", 11.5)
    c.hairline(c.h - 34 - len(foot) * 18)
    c.lines(PAD, c.h - 34 - (len(foot) - 1) * 18, foot, "body", 11.5, "muted", leading=1.57)
    return c


def card_built(theme, profile, work, calendar):
    """What I can do and what it is made with — never whose system it was done in."""
    items = profile["built"]
    sub = profile["builtSub"]
    alt = "What I build. " + sub + ". " + " ".join(f"{t}: {d} {w}." for t, d, w in items)
    c = Card("built", 372, theme, alt)
    c.brackets()
    c.heading("What I build", sub)
    first, step = 118, 64
    for i, (title, detail, tools) in enumerate(items):
        y = first + i * step
        c.hairline(y - 18)
        c.text(PAD, y, title, "strong", 11.5, "ink")
        c.lines(PAD, y + 17, wrap(detail, "body", 11), "body", 11, "muted", leading=1.5)
        c.text(PAD, y + 34, tools, "label", 9.5, "faint")

    # The accent bar walks down the list, one system every couple of seconds.
    c.css = hop_css("pick", step * (len(items) - 1), len(items), 2.2 * len(items))
    c.add(f'<rect class="pick" x="{PAD}" y="{first - 18.75}" width="34" height="1.5" '
          f'fill="{c.t["accent"]}"/>')
    return c


def card_signal(theme, profile, work, calendar):
    days = calendar["days"]
    end = datetime.date.fromisoformat(calendar["fetched"])
    span = 70
    window = [end - datetime.timedelta(days=span - 1 - i) for i in range(span)]
    counts = [days.get(d.isoformat(), 0) for d in window]
    peak = max(counts) or 1
    peak_at = counts.index(max(counts))
    year_total = sum(n for d, n in days.items() if d.startswith(str(end.year)))
    active = sum(1 for d, n in days.items() if n and d.startswith(str(end.year)))
    streak = longest_streak(days)
    alt = (f"Daily output. Contributions per day over the last ten weeks; the busiest day was "
           f"{day_label(window[peak_at].isoformat())} with {counts[peak_at]}. {year_total} contributions in "
           f"{end.year}, {active} active days, longest streak {streak} days.")
    c = Card("signal", 372, theme, alt)
    c.brackets()
    c.heading("Daily output", "Contributions per day, last 10 weeks")

    base, tall, step, bar = 236, 112, INNER / span, 3
    c.hairline(base + 0.5)
    for i, n in enumerate(counts):
        if not n:
            continue
        x = PAD + i * step + (step - bar) / 2
        h = max(tall * n / peak, 3)
        top = base - h
        c.add(f'<path d="M{x:.2f} {base}V{top + 1.5:.2f}'
              f'Q{x:.2f} {top:.2f} {x + 1.5:.2f} {top:.2f}Q{x + bar:.2f} {top:.2f} {x + bar:.2f} {top + 1.5:.2f}'
              f'V{base}Z" fill="{c.t["ink"]}"/>')

    c.css = sweep_css("play", "X", INNER, 11)
    c.add(f'<rect class="sweep play" x="{PAD}" y="{base - tall}" width="1" height="{tall}" fill="{c.t["accent"]}"/>')

    # Only the peak wears a number; the rest is read against it.
    px = PAD + peak_at * step + step / 2
    label = f"{counts[peak_at]} · {window[peak_at].day} {MONTHS[window[peak_at].month - 1]}"
    c.text(px + 8, base - tall + 9, label, "label", 10.5, "ink2")

    for i, d in enumerate(window):
        if d.day == 1 or i == 0:
            x = PAD + i * step
            c.add(f'<path d="M{x:.2f} {base + 1}v5" stroke="{c.t["faint"]}" stroke-width="1"/>')
            c.text(x + 4, base + 17, MONTHS[d.month - 1], "label", 10.5, "muted")

    stats = [(str(year_total), ["contributions", f"in {end.year}"]),
             (str(active), ["active days"]),
             (str(streak), ["days, longest", "streak"])]
    for i, (number, caption) in enumerate(stats):
        x = PAD + i * (INNER / 3)
        c.text(x, 300, number, "strong", 24, "ink")
        c.lines(x, 320, caption, "label", 10.5, "muted", leading=1.4)
    return c


def card_stack(theme, profile, work, calendar):
    languages = dict(work["languages"])
    named = [(name, languages.pop(name)) for name in ("C#", "TypeScript") if name in languages]
    named.append(("everything else", sum(languages.values())))
    total = sum(n for _, n in named)
    shares = [(name, n, round(100 * n / total)) for name, n in named]
    alt = ("Stack. Files touched by language: " + ", ".join(f"{name} {pct}%" for name, _, pct in shares) + ". "
           + " ".join(f"{group}: {', '.join(items)}." for group, items in profile["stack"]))
    c = Card("stack", 372, theme, alt)
    c.brackets()
    c.heading("Stack", "Files touched by language, then what I reach for")

    tones = ["ink", "muted", "faint"]   # every segment is also named below: identity is never tone alone
    x, gap = PAD, 2
    usable = INNER - gap * (len(shares) - 1)
    for i, (name, n, pct) in enumerate(shares):
        width = usable * n / total
        c.add(f'<rect x="{x:.2f}" y="98" '
              f'width="{width:.2f}" height="8" rx="2" fill="{c.t[tones[i]]}"/>')
        x += width + gap
    x = PAD
    for i, (name, n, pct) in enumerate(shares):
        c.add(f'<rect x="{x:.2f}" y="121" width="8" height="8" rx="2" fill="{c.t[tones[i]]}"/>')
        x += 13 + c.text(x + 13, 129, f"{name} {pct}%", "label", 10.5, "ink2") + 14

    c.css = sweep_css("read", "X", INNER, 8)
    c.add(f'<rect class="sweep read" x="{PAD}" y="94" width="1" height="16" fill="{c.t["accent"]}"/>')

    y = 166
    for group, items in profile["stack"]:
        c.text(PAD, y, group.upper(), "label", 10.5, "muted")
        y = c.lines(PAD, y + 19, wrap_list(items, "body", 11.5), "body", 11.5, "ink2", leading=1.58) + 10
    return c


def card_method(theme, profile, work, calendar):
    items = [(lead, detail.replace("{medianFiles}", str(work["medianFilesPerCommit"])))
             for lead, detail in profile["method"]]
    updated = day_label(calendar["fetched"])
    alt = ("How I work. " + " ".join(f"{lead} {detail}" for lead, detail in items)
           + f' github.com/{profile["login"]}. Updated {updated}.')
    c = Card("method", 372, theme, alt)
    c.brackets()
    c.heading("How I work")
    y = 88
    for lead, detail in items:
        c.text(PAD, y, lead, "strong", 12, "ink")
        y = c.lines(PAD, y + 19, wrap(detail, "body", 11.5), "body", 11.5, "muted", leading=1.55) + 14
    c.hairline(c.h - 46)
    c.css = sweep_css("tick", "X", INNER, 13)
    c.add(f'<rect class="sweep tick" x="{PAD}" y="{c.h - 49}" width="1" height="7" fill="{c.t["accent"]}"/>')
    c.text(PAD, c.h - 26, f'github.com/{profile["login"]}', "label", 10.5, "ink2")
    c.text(W - PAD, c.h - 26, f"updated {updated}", "label", 10.5, "muted", anchor="end")
    return c


ROWS = [[card_line], [card_id, card_about], [card_built, card_signal], [card_stack, card_method]]


def picture(card, prefix, stamp):
    """GitHub caches a README image by its address, so a redrawn card with the same file
    name can sit there for hours. The content's own digest in the query string makes a
    changed card a new address, and an unchanged one keep its cache."""
    alt = html.escape(card.alt, quote=True)
    return (f'<picture><source media="(prefers-color-scheme: dark)" '
            f'srcset="{prefix}{card.name}-dark.svg?v={stamp["dark"]}">'
            f'<img src="{prefix}{card.name}-light.svg?v={stamp["light"]}" '
            f'width="{card.w}" alt="{alt}"></picture>')


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    profile = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    work = json.loads((ROOT / "data" / "work.json").read_text(encoding="utf-8"))
    calendar = json.loads((ROOT / "data" / "calendar.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)

    # Absolute addresses: GitHub rewrites a relative <img src>, but a <source srcset> is not promised.
    raw = f'https://raw.githubusercontent.com/{profile["login"]}/{profile["login"]}/main/cards/'
    readme_rows, preview = [], {"dark": [], "light": []}
    for row in ROWS:
        pictures = []
        for draw in row:
            stamp = {}
            for theme in THEMES:
                card = draw(theme, profile, work, calendar)
                svg = card.svg()
                stamp[theme] = hashlib.sha1(svg.encode("utf-8")).hexdigest()[:8]
                (OUT / f"{card.name}-{theme}.svg").write_text(svg, encoding="utf-8", newline="\n")
                preview[theme].append(f'<img src="cards/{card.name}-{theme}.svg" width="{card.w}" alt="">')
            pictures.append(picture(card, raw, stamp))
            print(f"{card.name:8} {card.h} px  {len(card.svg()) / 1024:.0f} KB")
        readme_rows.append("".join(pictures))    # no whitespace: the two halves must touch
        for theme in THEMES:
            preview[theme].append("<br>")

    note = ('<p align="center"><sub>Drawn by a small Python script in '
            f'<a href="https://github.com/{profile["login"]}/{profile["login"]}/tree/main/generator">'
            "<code>/generator</code></a>. The numbers come from GitHub and from the systems "
            "themselves.</sub></p>")
    readme = '<p align="center">\n' + "\n<br>\n".join(readme_rows) + "\n</p>\n\n" + note + "\n"
    (ROOT / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    # Local previews that stand in for GitHub's README column, one per theme.
    page = {"dark": ("#0d1117", "#30363d"), "light": ("#ffffff", "#d0d7de")}
    for theme, (background, border) in page.items():
        body = "".join(preview[theme])
        (ROOT / f"preview-{theme}.html").write_text(
            f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>preview {theme}</title><style>body{{margin:0;background:{background};font:14px system-ui}}'
            f'.readme{{max-width:846px;margin:24px auto;padding:24px;border:1px solid {border};border-radius:6px;'
            f'box-sizing:content-box}}.readme p{{margin:0;text-align:center;line-height:0}}'
            f'.readme img{{max-width:100%;height:auto;vertical-align:top}}'
            f'@media(max-width:900px){{.readme{{margin:0;padding:16px;border:0}}}}</style>'
            f'<div class="readme"><p>{body}</p></div>\n', encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
