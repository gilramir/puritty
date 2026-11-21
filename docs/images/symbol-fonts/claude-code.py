# The case for docs/user/symbol-fonts.md's pictures: a Claude Code screen
# that uses the symbols it draws (❯ ⏺ ● ⎿ ✻ ✢ ✳ ✶ ✽ ⧉ ⏎ ↯ ✓ ✗ ⚠ ◐ ▸ ✦ ⏵ ⏸),
# in Fira Code. render.py draws it with one fallback font at a time.
import sys
E = '\\e'
def c(rgb, s): return f'{E}[38;2;{rgb}m{s}{E}[0m'
ORANGE, GREY, GREEN, RED, YELLOW, BLUE = '215;119;87', '140;140;140', '78;186;101', '255;107;128', '255;193;7', '177;185;249'
lines = [
    c(GREY, '❯ ') + 'why are the two symbols before "auto mode on" boxes?',
    '',
    c(GREEN, '⏺ ') + 'Read(docs/user/fonts.md)',
    c(GREY, '  ⎿  Read 85 lines'),
    c(GREEN, '● ') + 'Bash(fc-list ":charset=23f5" family)',
    c(GREY, '  ⎿  Noto Sans Symbols 2'),
    c(ORANGE, '✻ ✢ ✳ ✶ ✽ ') + c(GREY, 'Thinking… (esc to interrupt)'),
    c(GREEN, '✓ ') + 'found   ' + c(RED, '✗ ') + 'missing   ' + c(YELLOW, '⚠ ') + 'warning   ' + c(BLUE, '◐ ▸ ✦ ↯ ⧉ ⏎'),
    '',
    c(GREY, '─' * 62),
    c(GREY, '> '),
    c(GREY, '─' * 62),
    '  ' + c(ORANGE, '⏵⏵ auto mode on') + c(GREY, ' (shift+tab to cycle)'),
    '  ' + c(BLUE, '⏸ plan mode on'),
]
sys.stdout.write('size 66x15 font="Fira Code" points=14\n' + '\\r\\n'.join(lines) + E + '[11;3H\n')
