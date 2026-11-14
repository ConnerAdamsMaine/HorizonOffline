//! `horizon-bench`: validate and compare gameplay benchmark suite reports
//! (`crates/horizon-bench/src/suite.rs`, `tools/gameplay_bench.py`).
//!
//!     horizon-bench validate run.json [--strict]
//!     horizon-bench compare before.json after.json --threshold 5
//!     horizon-bench summary run.json
//!
//! `compare` exits 1 only for confirmed regressions: a change larger than the threshold whose
//! confidence interval clears zero. A change that cannot be separated from noise is printed as
//! `uncertain` and does not fail the job, so CI fails on regressions rather than on a busy machine.
//! `validate --strict` also rejects a run that is correct but not comparison-grade (one repeat,
//! contamination, no recorded commit or binary).

use std::process::ExitCode;

use horizon_bench::suite::{compare, ComparisonOptions, Suite};

fn usage() -> &'static str {
    "usage: horizon-bench <validate|summary|compare> FILE [FILE] [--threshold PERCENT] [--require-significance] [--strict]"
}

fn read(path: &str) -> Result<Suite, String> {
    let text = std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?;
    Suite::parse(&text).map_err(|e| format!("{path}: {e}"))
}

fn summary_table(suite: &Suite) {
    println!("# {}", suite.label.as_deref().unwrap_or("benchmark suite"));
    println!();
    println!("| scenario | metric | n | mean | outliers |");
    println!("|---|---|---:|---:|---:|");
    for scenario in &suite.scenarios {
        for (metric, values) in &scenario.samples {
            let Some(summary) = scenario.summary(metric) else {
                continue;
            };
            let outliers = scenario
                .stats
                .get(metric)
                .map_or(0, |stat| stat.outlier_count);
            println!(
                "| {} | {} | {} | {:.3} | {} |",
                scenario.name, metric, summary.n, summary.mean, outliers
            );
            let _ = values;
        }
    }
    println!();
    println!(
        "{} scenario(s), {} valid, {} check(s), run {}",
        suite.scenarios.len(),
        suite.scenarios.iter().filter(|s| s.valid()).count(),
        suite
            .scenarios
            .iter()
            .map(|s| s.checks.len())
            .sum::<usize>(),
        suite.run.commit.as_deref().unwrap_or("unknown")
    );
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() || args[0] == "--help" || args[0] == "-h" {
        println!("{}", usage());
        return ExitCode::SUCCESS;
    }
    let command = args[0].as_str();
    let mut threshold = 5.0;
    let mut require_significance = false;
    let mut strict = false;
    let mut files = Vec::new();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--threshold" => {
                i += 1;
                let Some(value) = args.get(i).and_then(|v| v.parse::<f64>().ok()) else {
                    eprintln!("horizon-bench: --threshold needs a number");
                    return ExitCode::from(2);
                };
                threshold = value;
            }
            "--require-significance" => require_significance = true,
            "--strict" => strict = true,
            other => files.push(other.to_owned()),
        }
        i += 1;
    }

    match command {
        "validate" => {
            let Some(path) = files.first() else {
                eprintln!("{}", usage());
                return ExitCode::from(2);
            };
            match read(path) {
                Ok(suite) => {
                    let errors = if strict {
                        suite.comparison_errors()
                    } else {
                        suite.validation_errors()
                    };
                    if errors.is_empty() {
                        println!(
                            "{}: valid ({} scenarios){}",
                            path,
                            suite.scenarios.len(),
                            if strict { ", comparison-grade" } else { "" }
                        );
                        ExitCode::SUCCESS
                    } else {
                        for error in &errors {
                            eprintln!("{path}: {error}");
                        }
                        ExitCode::FAILURE
                    }
                }
                Err(error) => {
                    eprintln!("{error}");
                    ExitCode::FAILURE
                }
            }
        }
        "summary" => {
            let Some(path) = files.first() else {
                eprintln!("{}", usage());
                return ExitCode::from(2);
            };
            match read(path) {
                Ok(suite) => {
                    summary_table(&suite);
                    ExitCode::SUCCESS
                }
                Err(error) => {
                    eprintln!("{error}");
                    ExitCode::FAILURE
                }
            }
        }
        "compare" => {
            if files.len() < 2 {
                eprintln!("{}", usage());
                return ExitCode::from(2);
            }
            let (before, after) = match (read(&files[0]), read(&files[1])) {
                (Ok(a), Ok(b)) => (a, b),
                (Err(error), _) | (_, Err(error)) => {
                    eprintln!("{error}");
                    return ExitCode::FAILURE;
                }
            };
            if !before.is_valid() || !after.is_valid() {
                eprintln!("warning: one side did not validate; its results may not be comparable");
                for error in before.validation_errors().iter().take(5) {
                    eprintln!("  {}: {error}", files[0]);
                }
                for error in after.validation_errors().iter().take(5) {
                    eprintln!("  {}: {error}", files[1]);
                }
            }
            let options = ComparisonOptions {
                threshold_pct: threshold,
                require_significance,
            };
            let results = compare(&before, &after, options);
            println!(
                "| scenario | metric | before | after | change | noise | verdict | significant |"
            );
            println!("|---|---|---:|---:|---:|---:|---|---|");
            for c in &results {
                println!(
                    "| {} | {} | {:.3} | {:.3} | {:+.1}% | {} | {:?} | {} |",
                    c.scenario,
                    c.metric,
                    c.before.mean,
                    c.after.mean,
                    c.change_pct,
                    c.noise_pct.map_or("-".into(), |n| format!("±{n}%")),
                    c.verdict,
                    c.significant.map_or("-", |s| if s { "yes" } else { "no" })
                );
            }
            let regressions = results.iter().filter(|c| c.regression).count();
            let uncertain = results
                .iter()
                .filter(|c| c.verdict == horizon_bench::suite::Verdict::Uncertain)
                .count();
            println!();
            println!(
                "{} metric(s) compared, {regressions} confirmed regression(s) over {threshold}%, {uncertain} uncertain",
                results.len()
            );
            if regressions > 0 {
                ExitCode::FAILURE
            } else {
                ExitCode::SUCCESS
            }
        }
        other => {
            eprintln!("horizon-bench: unknown command {other}\n{}", usage());
            ExitCode::from(2)
        }
    }
}
