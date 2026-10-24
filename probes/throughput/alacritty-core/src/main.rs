//! Feeds a file to Alacritty's Term through vte's Processor, in 64 KB chunks,
//! and prints the milliseconds the whole file took, once per run.
//!
//! usage: alacritty-core FILE [RUNS] [COLS] [LINES] [HISTORY]
//!
//! HISTORY is the scrollback in lines; Alacritty's default is 10,000.

use std::time::Instant;

use alacritty_terminal::event::VoidListener;
use alacritty_terminal::term::test::TermSize;
use alacritty_terminal::term::{Config, Term};
use alacritty_terminal::vte::ansi::Processor;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let data = std::fs::read(&args[1]).expect("read input");
    let runs: usize = args.get(2).map_or(5, |s| s.parse().unwrap());
    let cols: usize = args.get(3).map_or(160, |s| s.parse().unwrap());
    let lines: usize = args.get(4).map_or(50, |s| s.parse().unwrap());
    let history: usize = args.get(5).map_or(10_000, |s| s.parse().unwrap());

    for _ in 0..runs {
        let size = TermSize::new(cols, lines);
        let mut term = Term::new(Config { scrolling_history: history, ..Config::default() }, &size, VoidListener);
        let mut parser: Processor = Processor::new();
        let start = Instant::now();
        for chunk in data.chunks(64 * 1024) {
            parser.advance(&mut term, chunk);
        }
        let ms = start.elapsed().as_secs_f64() * 1000.0;
        // Read the grid so the work cannot be optimized away.
        let cursor = term.grid().cursor.point;
        println!("{:.1} ms  {:.0} MB/s  cursor {}:{}", ms, data.len() as f64 / ms / 1000.0, cursor.line.0, cursor.column.0);
    }
}
