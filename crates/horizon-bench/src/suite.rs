//! The gameplay benchmark suite's report and comparison rules (`tools/gameplay_bench.py`).
//!
//! The in-game `--benchmark` and `tools/perf_bench.py` write one [`crate::Report`] per run: startup,
//! chunk loads and flights. This module is the wider suite's machine-readable format: a list of
//! scenarios, each with raw metric samples, correctness checks and frame distributions. Keeping the
//! statistics and the regression rule here means the Python runner and the Rust CLI cannot disagree
//! about what "5% worse" means.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::{Conditions, Frames, Hardware, Summary};

pub const SUITE_FORMAT: &str = "horizon-benchmark-suite";
// Version 2 adds per-metric statistics, per-repeat runs, contamination reports and a noise-aware
// comparison verdict. Version-1 files still parse; newer files are refused.
pub const SUITE_VERSION: u32 = 2;

/// Nearest-rank percentile of sorted, non-empty values (the report format's definition).
fn percentile(sorted: &[f64], p: f64) -> f64 {
    let n = sorted.len();
    sorted[((n as f64 * p).ceil() as usize).clamp(1, n) - 1]
}

/// Three decimals, matching `crate::Summary`.
fn round(v: f64) -> f64 {
    (v * 1000.0).round() / 1000.0
}

/// The binary a run measured, so the same bytes can be reproduced or ruled out.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct BinaryInfo {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub modified: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sha256: Option<String>,
}

/// Provenance of the build and the command that produced the run.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct RunInfo {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub commit: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dirty: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
    /// The Cargo output folder (`release` holds the `bench` profile too); `profile` is the profile.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub build_dir: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rustc: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cargo: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub target: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub python: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub binary: Option<BinaryInfo>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub features: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub command: Vec<String>,
}

/// One correctness assertion: what the workload was supposed to produce, and what it produced.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Check {
    pub name: String,
    pub expected: String,
    pub actual: String,
    pub passed: bool,
}

impl Check {
    pub fn new(
        name: &str,
        expected: impl Into<String>,
        actual: impl Into<String>,
        passed: bool,
    ) -> Check {
        Check {
            name: name.to_owned(),
            expected: expected.into(),
            actual: actual.into(),
            passed,
        }
    }
}

/// One value outside Tukey's fences, reported in place; no sample is ever dropped.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Outlier {
    /// Position in the raw sample list.
    pub index: usize,
    pub value: f64,
    /// `high` or `low`.
    pub side: String,
}

/// A metric's statistics over its raw samples. `Summary` is the comparison contract; this adds the
/// distribution shape a reader needs to judge whether the mean means anything.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Stat {
    pub n: usize,
    pub mean: f64,
    pub median: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub stdev: Option<f64>,
    pub min: f64,
    pub max: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ci95: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ci95_pct: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cv_pct: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub iqr: Option<f64>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub outliers: Vec<Outlier>,
    #[serde(default)]
    pub outlier_count: usize,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub outlier_method: String,
}

impl Stat {
    /// `None` for no finite values. Outliers use Tukey's 1.5x interquartile fences (needing four
    /// samples, the smallest count for which the quartiles mean anything).
    pub fn of(values: &[f64]) -> Option<Stat> {
        let finite: Vec<f64> = values.iter().copied().filter(|v| v.is_finite()).collect();
        let n = finite.len();
        if n == 0 {
            return None;
        }
        let mean = finite.iter().sum::<f64>() / n as f64;
        let mut sorted = finite.clone();
        sorted.sort_by(f64::total_cmp);
        let median = percentile(&sorted, 0.5);
        let (stdev, ci95) = Summary::of(&finite).map_or((None, None), |s| (s.stdev, s.ci95));
        let ci95_pct = ci95
            .filter(|_| mean != 0.0)
            .map(|ci| (ci / mean).abs() * 100.0);
        let cv_pct = stdev
            .filter(|_| mean != 0.0)
            .map(|sd| sd / mean.abs() * 100.0);
        let iqr = (n >= 4).then(|| percentile(&sorted, 0.75) - percentile(&sorted, 0.25));
        let outliers = iqr.map_or_else(Vec::new, |spread| {
            let (q1, q3) = (percentile(&sorted, 0.25), percentile(&sorted, 0.75));
            let (low, high) = (q1 - 1.5 * spread, q3 + 1.5 * spread);
            finite
                .iter()
                .enumerate()
                .filter(|(_, v)| **v < low || **v > high)
                .map(|(index, value)| Outlier {
                    index,
                    value: round(*value),
                    side: if *value > high { "high" } else { "low" }.into(),
                })
                .collect()
        });
        Some(Stat {
            n,
            mean: round(mean),
            median: round(median),
            stdev: stdev.map(round),
            min: round(sorted[0]),
            max: round(sorted[n - 1]),
            ci95: ci95.map(round),
            ci95_pct: ci95_pct.map(round),
            cv_pct: cv_pct.map(round),
            iqr: iqr.map(round),
            outlier_count: outliers.len(),
            outliers,
            outlier_method: "tukey-1.5-iqr".into(),
        })
    }
}

/// One measured repeat: its own raw samples, checks and notes, so a pooled figure can be traced back.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct ScenarioRun {
    pub repeat: u32,
    #[serde(default)]
    pub samples: BTreeMap<String, Vec<f64>>,
    #[serde(default)]
    pub frames: usize,
    #[serde(default)]
    pub checks: Vec<Check>,
    #[serde(default)]
    pub notes: Vec<String>,
    #[serde(default)]
    pub contamination: Vec<String>,
}

/// One scenario of a suite run.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Scenario {
    pub name: String,
    pub category: String,
    pub seconds: f64,
    pub repeats: u32,
    /// Raw samples by metric name (`tick.tps`, `memory.rss_mb`, `cpu.wall_s`...). The summary is
    /// computed from these, never stored separately, so a reader can re-check the statistics.
    #[serde(default)]
    pub samples: BTreeMap<String, Vec<f64>>,
    #[serde(default)]
    pub checks: Vec<Check>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub frames: Vec<Frames>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub notes: Vec<String>,
    /// Per-metric statistics; optional because it is derivable from `samples`.
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub stats: BTreeMap<String, Stat>,
    /// The repeats individually, not only their pool.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub runs: Vec<ScenarioRun>,
    /// A bounded profiler summary for this scenario (currently the game's Chrome trace top spans).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub profile: Option<serde_json::Value>,
    /// Why this scenario's measurements are not comparison-grade (a busy or short-of-memory machine,
    /// a collapsed tick rate). Correctness can still be accepted; a baseline must be clean.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub contamination: Vec<String>,
}

impl Scenario {
    pub fn new(name: &str, category: &str, seconds: f64, repeats: u32) -> Scenario {
        Scenario {
            name: name.to_owned(),
            category: category.to_owned(),
            seconds,
            repeats,
            samples: BTreeMap::new(),
            checks: Vec::new(),
            frames: Vec::new(),
            notes: Vec::new(),
            stats: BTreeMap::new(),
            runs: Vec::new(),
            profile: None,
            contamination: Vec::new(),
        }
    }

    pub fn sample(&mut self, metric: &str, value: f64) {
        if value.is_finite() {
            self.samples
                .entry(metric.to_owned())
                .or_default()
                .push(value);
        }
    }

    pub fn check(
        &mut self,
        name: &str,
        expected: impl Into<String>,
        actual: impl Into<String>,
        passed: bool,
    ) {
        self.checks.push(Check::new(name, expected, actual, passed));
    }

    pub fn summary(&self, metric: &str) -> Option<Summary> {
        self.samples.get(metric).and_then(|v| Summary::of(v))
    }

    /// A scenario is valid only when every assertion passed and it produced a measurement: an
    /// action that never ran must not look like a fast run.
    pub fn valid(&self) -> bool {
        !self.checks.is_empty() && self.checks.iter().all(|c| c.passed) && !self.samples.is_empty()
    }

    pub fn failures(&self) -> impl Iterator<Item = &Check> {
        self.checks.iter().filter(|c| !c.passed)
    }
}

/// The machine and build conditions of a run, filled in by the runner.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Environment {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub started: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ended: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ram_mb: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cpu_count: Option<usize>,
    /// Free-form snapshots (load, available memory, swap) before and after the run.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub load_before: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub load_after: Option<serde_json::Value>,
}

/// A complete suite run.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Suite {
    pub format: String,
    pub version: u32,
    pub created: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
    #[serde(default)]
    pub run: RunInfo,
    #[serde(default)]
    pub hardware: Hardware,
    #[serde(default)]
    pub conditions: Conditions,
    #[serde(default)]
    pub environment: Environment,
    #[serde(default)]
    pub scenarios: Vec<Scenario>,
}

impl Suite {
    pub fn new(label: Option<String>, run: RunInfo, hardware: Hardware) -> Suite {
        Suite {
            format: SUITE_FORMAT.to_owned(),
            version: SUITE_VERSION,
            created: crate::utc_now(),
            label,
            run,
            hardware,
            conditions: Conditions::default(),
            environment: Environment::default(),
            scenarios: Vec::new(),
        }
    }

    /// Why this run should not be compared or published. Empty means valid.
    pub fn validation_errors(&self) -> Vec<String> {
        let mut errors = Vec::new();
        if self.format != SUITE_FORMAT {
            errors.push(format!("not a benchmark suite: format {:?}", self.format));
        }
        if self.version > SUITE_VERSION {
            errors.push(format!(
                "suite version {} is newer than {SUITE_VERSION}",
                self.version
            ));
        }
        if self.scenarios.is_empty() {
            errors.push("the run has no scenarios".into());
        }
        for scenario in &self.scenarios {
            for check in scenario.failures() {
                errors.push(format!(
                    "{}: {} failed (expected {}, got {})",
                    scenario.name, check.name, check.expected, check.actual
                ));
            }
            if scenario.checks.is_empty() {
                errors.push(format!("{}: no correctness checks", scenario.name));
            }
            if scenario.samples.is_empty() {
                errors.push(format!("{}: no samples", scenario.name));
            }
            for (metric, values) in &scenario.samples {
                if values.iter().any(|v| !v.is_finite()) {
                    errors.push(format!(
                        "{}: {metric} has a non-finite sample",
                        scenario.name
                    ));
                }
            }
        }
        errors
    }

    pub fn is_valid(&self) -> bool {
        self.validation_errors().is_empty()
    }

    /// Why this run is not suitable as a baseline or a comparison side: the measurements are
    /// correct but the machine was too busy (or the run too short) for the numbers to mean much.
    /// Kept separate from [`Self::validation_errors`] so a correctness job never fails on noise.
    pub fn comparison_errors(&self) -> Vec<String> {
        let mut errors = self.validation_errors();
        for scenario in &self.scenarios {
            for reason in &scenario.contamination {
                errors.push(format!("{}: contaminated: {reason}", scenario.name));
            }
            if scenario.repeats < 2 {
                errors.push(format!(
                    "{}: one repeat; a baseline needs at least two",
                    scenario.name
                ));
            }
            match self.run.binary.as_ref().and_then(|b| b.sha256.as_ref()) {
                Some(sha) if !sha.trim().is_empty() => {}
                _ => errors.push("no binary fingerprint is recorded".into()),
            }
        }
        if self.run.commit.is_none() {
            errors.push("no git commit is recorded".into());
        }
        errors
    }

    pub fn is_comparison_grade(&self) -> bool {
        self.comparison_errors().is_empty()
    }

    pub fn parse(json: &str) -> Result<Suite, String> {
        let suite: Suite = serde_json::from_str(json).map_err(|e| e.to_string())?;
        if suite.format != SUITE_FORMAT {
            return Err(format!("not a benchmark suite: format {:?}", suite.format));
        }
        if suite.version > SUITE_VERSION {
            return Err(format!(
                "suite version {} is newer than {SUITE_VERSION}",
                suite.version
            ));
        }
        Ok(suite)
    }

    pub fn to_json(&self) -> String {
        serde_json::to_string_pretty(self).expect("a suite always serializes")
    }
}

/// Which way is better for a metric, from its name. Frame rates, ticks per second and throughput
/// counts are higher-is-better; times, memory, bytes and counts are lower-is-better (a larger count
/// is more work, which is what a regression detector should flag).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Direction {
    Higher,
    Lower,
}

/// What a comparison concluded, separating a confirmed regression from a change the sample cannot
/// distinguish from noise.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Verdict {
    Regression,
    Improvement,
    Neutral,
    /// A change over the threshold whose confidence interval overlaps zero, or which has too few
    /// repeats to judge. Never treated as a failure.
    Uncertain,
}

pub fn direction(metric: &str) -> Direction {
    if metric.ends_with("fps")
        || metric.ends_with("tps")
        || metric.ends_with("_per_s")
        || metric.ends_with("_throughput")
    {
        Direction::Higher
    } else {
        Direction::Lower
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub struct ComparisonOptions {
    /// The smallest relative change worth reporting, in percent.
    pub threshold_pct: f64,
    /// When both sides have repeats, require the difference to clear the combined 95% standard
    /// error before calling it a regression. Off by default because a suite scenario is often run
    /// once; a single-run difference above the threshold is still labelled as one.
    pub require_significance: bool,
}

impl Default for ComparisonOptions {
    fn default() -> Self {
        ComparisonOptions {
            threshold_pct: 5.0,
            require_significance: false,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Comparison {
    pub scenario: String,
    pub metric: String,
    pub before: Summary,
    pub after: Summary,
    /// Percent change in the metric's own value: positive is a larger number, not necessarily worse.
    pub change_pct: f64,
    /// Half-width of the combined 95% interval as a percent of the baseline mean; `None` without
    /// two repeats on both sides.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub noise_pct: Option<f64>,
    pub direction: Direction,
    /// `None` when either side has fewer than two repeats.
    pub significant: Option<bool>,
    pub verdict: Verdict,
    /// Only a [`Verdict::Regression`]: a worse change that clears the noise and the threshold.
    pub regression: bool,
}

fn significant(before: &Summary, after: &Summary) -> Option<bool> {
    if before.n < 2 || after.n < 2 {
        return None;
    }
    let se = |s: &Summary| s.ci95.map(|ci| ci / 1.96);
    let (a, b) = (se(before)?, se(after)?);
    Some((after.mean - before.mean).abs() > 1.96 * (a * a + b * b).sqrt())
}

/// Combined 95% standard error as a percent of the baseline mean.
fn noise_pct(before: &Summary, after: &Summary) -> Option<f64> {
    if before.n < 2 || after.n < 2 || before.mean == 0.0 {
        return None;
    }
    let se = |s: &Summary| s.ci95.map(|ci| ci / 1.96);
    let (a, b) = (se(before)?, se(after)?);
    Some(round(
        1.96 * (a * a + b * b).sqrt() / before.mean.abs() * 100.0,
    ))
}

/// Compares the common scenarios and metrics of two runs. Scenarios or metrics present on one side
/// only are skipped: that is a changed suite, not a performance change.
pub fn compare(before: &Suite, after: &Suite, options: ComparisonOptions) -> Vec<Comparison> {
    let mut out = Vec::new();
    for old in &before.scenarios {
        let Some(new) = after.scenarios.iter().find(|s| s.name == old.name) else {
            continue;
        };
        for (metric, old_values) in &old.samples {
            let Some(new_values) = new.samples.get(metric) else {
                continue;
            };
            let (Some(old_summary), Some(new_summary)) =
                (Summary::of(old_values), Summary::of(new_values))
            else {
                continue;
            };
            let change_pct = if old_summary.mean == 0.0 {
                if new_summary.mean == 0.0 {
                    0.0
                } else {
                    f64::INFINITY
                }
            } else {
                (new_summary.mean - old_summary.mean) / old_summary.mean.abs() * 100.0
            };
            let dir = direction(metric);
            let worse = match dir {
                Direction::Higher => change_pct < 0.0,
                Direction::Lower => change_pct > 0.0,
            };
            let significant = significant(&old_summary, &new_summary);
            let noise = noise_pct(&old_summary, &new_summary);
            let over = change_pct.abs() > options.threshold_pct;
            let verdict = if !over {
                Verdict::Neutral
            } else if significant != Some(true) {
                Verdict::Uncertain
            } else if worse {
                Verdict::Regression
            } else {
                Verdict::Improvement
            };
            out.push(Comparison {
                scenario: old.name.clone(),
                metric: metric.clone(),
                before: old_summary,
                after: new_summary,
                change_pct: (change_pct * 1000.0).round() / 1000.0,
                noise_pct: noise,
                direction: dir,
                significant,
                verdict,
                regression: verdict == Verdict::Regression,
            });
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::App;

    fn scenario(name: &str, values: &[f64]) -> Scenario {
        let mut s = Scenario::new(name, "test", 1.0, values.len() as u32);
        for &v in values {
            s.sample("tick.mspt", v);
        }
        s.check("ran", "1 tick", "1 tick", true);
        s
    }

    fn suite(name: &str, values: &[f64]) -> Suite {
        let mut s = Suite::new(Some(name.into()), RunInfo::default(), Hardware::default());
        s.scenarios.push(scenario("idle", values));
        s
    }

    #[test]
    fn validation_rejects_a_failed_workload_and_accepts_a_passing_one() {
        let mut run = suite("ok", &[10.0, 11.0]);
        assert!(run.is_valid(), "{:?}", run.validation_errors());
        run.scenarios[0].check("moved", "> 1 block", "0 blocks", false);
        let errors = run.validation_errors();
        assert!(errors.iter().any(|e| e.contains("moved")), "{errors:?}");
        assert!(!run.is_valid());
    }

    #[test]
    fn validation_rejects_empty_scenarios_and_non_finite_samples() {
        let mut run = suite("bad", &[1.0]);
        run.scenarios[0]
            .samples
            .get_mut("tick.mspt")
            .unwrap()
            .push(f64::NAN);
        assert!(run
            .validation_errors()
            .iter()
            .any(|e| e.contains("non-finite")));
        run.scenarios.clear();
        assert!(run
            .validation_errors()
            .iter()
            .any(|e| e.contains("no scenarios")));
    }

    #[test]
    fn comparison_flags_only_worse_changes_over_the_threshold() {
        let before = suite("before", &[10.0, 10.0, 10.0]);
        let after = suite("after", &[12.0, 12.0, 12.0]);
        let out = compare(&before, &after, ComparisonOptions::default());
        let tick = out.iter().find(|c| c.metric == "tick.mspt").unwrap();
        assert_eq!(tick.change_pct, 20.0);
        assert!(tick.regression);
        assert_eq!(tick.direction, Direction::Lower);
        // A 2% change is below the default 5% threshold.
        let close = suite("close", &[10.2, 10.2, 10.2]);
        assert!(!compare(&before, &close, ComparisonOptions::default())[0].regression);
    }

    #[test]
    fn comparison_knows_that_a_lower_frame_rate_is_a_regression() {
        let mut before = suite("before", &[1.0, 1.0, 1.0]);
        before.scenarios[0]
            .samples
            .insert("render.avg_fps".into(), vec![120.0, 121.0, 119.0]);
        let mut after = suite("after", &[1.0, 1.0, 1.0]);
        after.scenarios[0]
            .samples
            .insert("render.avg_fps".into(), vec![90.0, 91.0, 89.0]);
        let out = compare(&before, &after, ComparisonOptions::default());
        let fps = out.iter().find(|c| c.metric == "render.avg_fps").unwrap();
        assert_eq!(fps.change_pct, -25.0);
        assert_eq!(fps.direction, Direction::Higher);
        assert_eq!(fps.verdict, Verdict::Regression);
        assert!(fps.regression);
    }

    #[test]
    fn significance_needs_repeats_on_both_sides() {
        let before = suite("before", &[10.0]);
        let after = suite("after", &[40.0]);
        let out = compare(&before, &after, ComparisonOptions::default());
        assert_eq!(out[0].significant, None);
        // A 300% change on one sample each is not a confirmed regression: nothing can tell it
        // from a cold start, a busy machine or a different world.
        assert_eq!(out[0].verdict, Verdict::Uncertain);
        assert!(!out[0].regression);
        let before = suite("before", &[10.0, 10.1, 9.9]);
        let after = suite("after", &[40.0, 40.1, 39.9]);
        let out = compare(&before, &after, ComparisonOptions::default());
        assert_eq!(out[0].significant, Some(true));
        assert_eq!(out[0].verdict, Verdict::Regression);
    }

    #[test]
    fn a_change_inside_the_noise_is_uncertain_not_a_regression() {
        // Two samples whose spread is wider than the 8% difference between their means.
        let before = suite("before", &[10.0, 14.0, 12.0]);
        let after = suite("after", &[13.0, 17.0, 15.0]);
        let out = compare(&before, &after, ComparisonOptions::default());
        let tick = out.iter().find(|c| c.metric == "tick.mspt").unwrap();
        assert!(tick.change_pct > 5.0, "{tick:?}");
        assert_eq!(tick.significant, Some(false));
        assert_eq!(tick.verdict, Verdict::Uncertain);
        assert!(!tick.regression);
        assert!(tick.noise_pct.unwrap() > 5.0);
    }

    #[test]
    fn statistics_report_outliers_and_keep_every_sample() {
        let values = [10.0, 10.1, 9.9, 10.05, 40.0];
        let stat = Stat::of(&values).unwrap();
        assert_eq!(stat.n, 5);
        assert_eq!(stat.outlier_count, 1);
        assert_eq!(stat.outliers[0].value, 40.0);
        assert_eq!(stat.outliers[0].side, "high");
        assert_eq!(stat.median, 10.05);
        assert_eq!(stat.outlier_method, "tukey-1.5-iqr");
        // Fewer than four samples have no meaningful quartiles: none is called an outlier.
        assert_eq!(Stat::of(&[1.0, 2.0, 100.0]).unwrap().outlier_count, 0);
        assert_eq!(Stat::of(&[f64::NAN]), None);
    }

    #[test]
    fn a_comparison_grade_run_needs_repeats_a_commit_and_no_contamination() {
        let mut run = suite("baseline", &[10.0, 10.1, 9.9]);
        run.run.commit = Some("0123456".into());
        run.run.binary = Some(BinaryInfo {
            sha256: Some("abc123".into()),
            ..BinaryInfo::default()
        });
        run.scenarios[0].repeats = 3;
        assert!(run.is_comparison_grade(), "{:?}", run.comparison_errors());
        run.scenarios[0]
            .contamination
            .push("machine 40% busy".into());
        assert!(!run.is_comparison_grade());
        assert!(run.is_valid(), "correctness is unaffected by contamination");
        run.scenarios[0].contamination.clear();
        run.scenarios[0].repeats = 1;
        assert!(run
            .comparison_errors()
            .iter()
            .any(|e| e.contains("one repeat")));
    }

    #[test]
    fn suite_round_trips_and_rejects_other_formats() {
        let mut run = suite("round trip", &[1.0, 2.0]);
        run.scenarios[0]
            .frames
            .push(Frames::of("idle", 0, &[2.0, 3.0], &[], &[]).unwrap());
        let back = Suite::parse(&run.to_json()).unwrap();
        assert_eq!(back, run);
        let other = run.to_json().replace(SUITE_FORMAT, "something-else");
        assert!(Suite::parse(&other).is_err());
        let newer = run.to_json().replace("\"version\": 2", "\"version\": 3");
        assert!(Suite::parse(&newer).unwrap_err().contains("newer"));
        assert_eq!(run.scenarios[0].repeats, 2);
        assert_eq!(run.scenarios[0].category, "test");
        let _ = App::default();
    }
}
