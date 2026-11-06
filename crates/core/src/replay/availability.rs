// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

//! Research-only, trace-driven HPC worker availability for aggregated replay.
//! Events are ordered by simulation time; starting workers are not routable.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "action", rename_all = "snake_case")]
pub enum WorkerAvailabilityAction {
    Add { count: usize },
    Reclaim { worker_ids: Vec<usize> },
    /// Oracle: stop new assignments at reclaim time, but finish in-flight work.
    /// This may overrun the nominal availability window.
    ReclaimGracefully { worker_ids: Vec<usize> },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WorkerAvailabilityEvent {
    pub time_ms: f64,
    #[serde(flatten)]
    pub change: WorkerAvailabilityAction,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkerRecoveryMode {
    #[default]
    None,
    Restart,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct WorkerRecoveryPolicy {
    pub mode: WorkerRecoveryMode,
    pub max_restarts: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize)]
pub struct WorkerAvailabilityStats {
    pub added_workers: usize,
    pub reclaimed_workers: usize,
    pub reclaim_events: usize,
    pub interrupted_attempts: usize,
    pub restarted_attempts: usize,
    pub permanently_failed_requests: usize,
}

pub(crate) fn validate_events(events: &[WorkerAvailabilityEvent]) -> anyhow::Result<()> {
    let mut previous = 0.0;
    for (index, event) in events.iter().enumerate() {
        anyhow::ensure!(
            event.time_ms.is_finite() && event.time_ms >= previous,
            "availability events must have nonnegative, finite, nondecreasing timestamps (index {index})"
        );
        match &event.change {
            WorkerAvailabilityAction::Add { count } => {
                anyhow::ensure!(*count > 0, "worker Add count must be positive");
            }
            WorkerAvailabilityAction::Reclaim { worker_ids }
            | WorkerAvailabilityAction::ReclaimGracefully { worker_ids } => {
                anyhow::ensure!(!worker_ids.is_empty(), "worker Reclaim IDs cannot be empty");
                let unique = worker_ids.iter().copied().collect::<std::collections::BTreeSet<_>>();
                anyhow::ensure!(unique.len() == worker_ids.len(), "duplicate worker Reclaim ID");
            }
        }
        previous = event.time_ms;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reclaim_json_round_trip() {
        let input = r#"{"time_ms":200000.0,"action":"reclaim","worker_ids":[4,5,6,7]}"#;
        let parsed: WorkerAvailabilityEvent = serde_json::from_str(input).unwrap();
        assert_eq!(parsed.change, WorkerAvailabilityAction::Reclaim { worker_ids: vec![4,5,6,7] });
        validate_events(&[parsed.clone()]).unwrap();
        assert_eq!(serde_json::from_str::<WorkerAvailabilityEvent>(&serde_json::to_string(&parsed).unwrap()).unwrap(), parsed);
    }

    #[test]
    fn validates_event_order() {
        let events = [
            WorkerAvailabilityEvent { time_ms: 5.0, change: WorkerAvailabilityAction::Add { count: 1 } },
            WorkerAvailabilityEvent { time_ms: 4.0, change: WorkerAvailabilityAction::Add { count: 1 } },
        ];
        assert!(validate_events(&events).is_err());
    }
}
