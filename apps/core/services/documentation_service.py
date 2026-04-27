from __future__ import annotations


def build_documentation_payload() -> dict:
    modules = [
        {
            "id": "dashboard",
            "title": "Dashboard",
            "icon": "dashboard",
            "what_is": (
                "Dashboard is the operational command view that summarizes scan activity, request volume, "
                "result trends, reports, notifications, and assets in one place."
            ),
            "why_used": [
                "Gives operators immediate visibility into current workload and outcomes.",
                "Reduces time-to-triage by surfacing high-value metrics and recent activity first.",
                "Supports daily review, handover notes, and management reporting.",
            ],
            "how_to_use": [
                "Review the KPI cards at the top to assess your current scope.",
                "Check the Scan Requests (Last 7 Days) chart for trend changes.",
                "Use Activity Summary to understand Draft, Pending, Validated, and Rejected request mix.",
                "Open Recent Targets and Recent Scan Requests to continue active investigations quickly.",
            ],
            "fields": [
                {
                    "name": "Scope Label",
                    "details": "Shows whether cards and lists are scoped as My data or All data based on your role.",
                },
                {
                    "name": "KPI Cards",
                    "details": (
                        "Targets, Scan Requests, Pending Requests, Validated Requests, Running Scans, "
                        "Reports, Unread Notifications, and Assets."
                    ),
                },
                {
                    "name": "Scan Requests (Last 7 Days)",
                    "details": "Day-by-day bar chart of request volume used for throughput trend analysis.",
                },
                {
                    "name": "Activity Summary",
                    "details": "Compact counts for Draft, Pending, Validated, and Rejected request states.",
                },
                {
                    "name": "Quick Actions",
                    "details": "New Scan and Add Target shortcuts, with visibility based on your account access scope.",
                },
            ],
            "examples": [
                "Morning operations check: verify Running Scans and Pending Requests before creating new workload.",
                "Weekly review: compare daily request chart trend with report generation output.",
            ],
            "best_practices": [
                "Use Dashboard as a pre-flight check before launching new scans.",
                "Investigate sudden spikes in Pending Requests or Failed executions immediately.",
                "Confirm scope label before exporting metrics into stakeholder reports.",
            ],
            "warnings": [
                "Do not treat dashboard counts as final evidence without validating underlying records.",
            ],
        },
        {
            "id": "new-scan",
            "title": "New Scan",
            "icon": "add_circle",
            "what_is": (
                "New Scan is the controlled request builder used to submit validated scan jobs with "
                "policy-governed options."
            ),
            "why_used": [
                "Standardizes scan creation so teams follow the same safe workflow.",
                "Captures audit-ready context and validates configuration before runtime execution.",
                "Prevents invalid or unsafe request combinations from entering the execution queue.",
            ],
            "how_to_use": [
                "Open New Scan from Dashboard or sidebar.",
                "Select Target and optional Scan Profile.",
                "Set Scan Type, Timing Profile, and Port Scope.",
                "Choose Controlled Options required for your objective.",
                "Add Notes for audit/compliance context.",
                "Review the live preview panel, then click Submit Scan Request.",
            ],
            "fields": [
                {
                    "name": "Target",
                    "details": (
                        "Defines what host or network will be scanned. Supported target formats include "
                        "single IP, domain, or CIDR ranges."
                    ),
                    "examples": ["192.168.1.10", "example.com", "10.0.0.0/24"],
                },
                {
                    "name": "Scan Profile (optional)",
                    "details": (
                        "Predefined template that can prefill scan strategy, timing, and options. "
                        "Use profiles for repeatable scanning standards; use manual setup for custom needs."
                    ),
                },
                {
                    "name": "Scan Type",
                    "details": (
                        "Logical classification controlling primary scan behavior. Available values: "
                        "Host Discovery, Quick TCP, Top 100, Top 1000, Service Detection, Safe Basic."
                    ),
                },
                {
                    "name": "Timing Profile",
                    "details": (
                        "Controls speed-versus-load tradeoff. Normal is conservative baseline, Balanced mixes speed "
                        "and stability, Fast increases aggressiveness and network pressure."
                    ),
                    "examples": ["Normal", "Balanced", "Fast"],
                },
                {
                    "name": "Port Scope",
                    "details": (
                        "Defines ports to probe. Supports single, multi, range, and mixed patterns."
                    ),
                    "examples": ["80", "22,80,443", "1-1024", "80,443,8000-8100"],
                },
                {
                    "name": "Controlled Options",
                    "details": (
                        "Feature toggles that tune scan depth and runtime behavior. "
                        "Use only the options required for the current objective."
                    ),
                    "examples": [
                        "Host Discovery",
                        "Service Detection",
                        "Version Detection",
                        "OS Detection",
                        "Traceroute",
                        "DNS Resolution",
                    ],
                },
                {
                    "name": "Host Discovery",
                    "details": "Checks host reachability before deeper probing to reduce unnecessary traffic.",
                },
                {
                    "name": "Service Detection",
                    "details": "Identifies running services such as nginx, apache, ssh, mysql, and similar.",
                },
                {
                    "name": "Version Detection",
                    "details": "Attempts service version fingerprinting for patch/vulnerability triage.",
                },
                {
                    "name": "OS Detection",
                    "details": "Infers operating system characteristics to improve inventory context.",
                },
                {
                    "name": "Traceroute",
                    "details": "Collects network path hops to aid routing and segmentation troubleshooting.",
                },
                {
                    "name": "DNS Resolution",
                    "details": "Resolves hostnames where possible to improve readability and reporting context.",
                },
                {
                    "name": "Notes",
                    "details": (
                        "Operational and audit context field used for approvals, intent, and compliance tracking."
                    ),
                    "examples": ["Weekly security scan for production API servers"],
                },
            ],
            "examples": [
                "Production API baseline: Target 10.10.20.0/24, Scan Type Top 1000, Timing Balanced, Notes with change-ticket ID.",
                "Urgent verification: Target app.example.com, Quick TCP + Service Detection, limited Port Scope 22,80,443.",
            ],
            "best_practices": [
                "Start with Safe Basic or conservative profiles before enabling deeper options.",
                "Keep Port Scope focused on required business services when scanning critical infrastructure.",
                "Always populate Notes with owner, purpose, and approval reference.",
                "Use live preview feedback before submission to catch configuration mistakes early.",
            ],
            "warnings": [
                "Fast timing and broad Port Scope can increase target/network load significantly.",
                "Incorrect Target format or scope selection can scan unintended systems.",
                "Enabling multiple deep-detection toggles may increase runtime and noise.",
            ],
        },
        {
            "id": "running",
            "title": "Running",
            "icon": "sync",
            "what_is": (
                "Running is the live execution monitor for active and recently processed scan jobs."
            ),
            "why_used": [
                "Gives real-time visibility into execution progress and stage transitions.",
                "Enables quick intervention for failed, stalled, or misconfigured runs.",
                "Provides worker and queue context needed for runtime troubleshooting.",
            ],
            "how_to_use": [
                "Open Running and review summary cards for Running, Queued, Completed, and Failed states.",
                "Filter the table using Status, Queue State, User, Target, and Search.",
                "Open Monitor for live status panel and event log stream.",
                "Use Cancel or Retry actions when role permissions allow.",
            ],
            "fields": [
                {"name": "Search", "details": "Matches target values, execution IDs, and worker names."},
                {"name": "Status", "details": "Execution state filter: Queued, Running, Completed, Failed, Cancelled."},
                {"name": "Queue State", "details": "Queue lifecycle filter: Waiting, Assigned, Processing, Done, Error."},
                {"name": "User", "details": "Requested-by filter for multi-user operational teams."},
                {"name": "Target", "details": "Target-specific execution filter."},
                {"name": "Progress", "details": "Shows progress percent and current stage for each execution."},
                {"name": "Worker", "details": "Displays assigned worker_name, or Unassigned when pending."},
            ],
            "examples": [
                "During incident response, filter Status=Running and Target=<affected host> for immediate visibility.",
                "For recovery ops, filter Status=Failed then use Retry where policy permits.",
            ],
            "best_practices": [
                "Use Monitor view for confirmed runtime diagnosis before cancelling jobs.",
                "Correlate Worker and Queue State when troubleshooting throughput issues.",
                "Review Completed vs Failed trend per shift to detect pipeline instability.",
            ],
            "warnings": [
                "Frequent cancel/retry loops can create queue churn and delay other jobs.",
            ],
        },
        {
            "id": "scan-queue",
            "title": "Scan Queue",
            "icon": "queue",
            "what_is": (
                "Scan Queue displays jobs waiting for execution or currently being assigned/processed by workers."
            ),
            "why_used": [
                "Provides queue depth and position visibility before jobs start running.",
                "Helps operators prioritize workloads and estimate execution start times.",
                "Supports capacity planning by highlighting assignment and processing bottlenecks.",
            ],
            "how_to_use": [
                "Review queue summary cards for Total Queued, Assigned, Processing, and Failed Queue State.",
                "Filter by Queue State, Target, Submitted By, and Search.",
                "Use Position, Priority, and Est. Wait columns to estimate dispatch timing.",
                "Open Monitor to jump into execution detail once assignment begins.",
            ],
            "fields": [
                {"name": "Queue State", "details": "Primary filter for waiting/assigned/processing/error queue stages."},
                {"name": "Target", "details": "Limits queue rows to a target or subnet-specific workload."},
                {"name": "Submitted By", "details": "Identifies owner/user pipeline load in shared teams."},
                {"name": "Priority", "details": "Displayed as P<value>; lower queue order and dispatch behavior are role-policy dependent."},
                {"name": "Est. Wait", "details": "Approximate wait indicator for planning, not an SLA guarantee."},
                {"name": "Assigned Worker", "details": "Shows selected worker or pending assignment state."},
            ],
            "examples": [
                "Before maintenance windows, confirm high-priority jobs are near top queue positions.",
                "If queue backlog grows, validate worker availability in Queue & Worker Status.",
            ],
            "best_practices": [
                "Keep queue filters focused during incident periods to avoid operator overload.",
                "Use Submitted By filter during team handovers to reassign ownership quickly.",
            ],
            "warnings": [
                "Estimated wait values are approximations and can shift with new higher-priority jobs.",
            ],
        },
        {
            "id": "results",
            "title": "Results",
            "icon": "analytics",
            "what_is": (
                "Results is the structured findings workspace for completed scan executions."
            ),
            "why_used": [
                "Turns raw execution output into operator-friendly risk and service intelligence.",
                "Supports remediation prioritization through host state and service evidence.",
                "Provides exportable evidence for audits and incident workflows.",
            ],
            "how_to_use": [
                "Filter using Target, Execution Status, Profile, Service Detected, Risk Level, and date range.",
                "Open a result to inspect host status, open ports, services, and raw/parsed outputs.",
                "Use Compare to evaluate drift between two snapshots.",
                "Use Export actions for downstream analysis and reporting.",
            ],
            "fields": [
                {"name": "Search", "details": "Find by scan ID, hostname, or target snapshot text."},
                {"name": "Target", "details": "Target-specific result filter."},
                {"name": "Execution Status", "details": "Filters results by execution lifecycle state."},
                {"name": "Profile", "details": "Filters by associated scan profile used during request."},
                {"name": "Service Detected", "details": "Matches service strings such as http, ssh, mysql."},
                {"name": "Risk Level", "details": "Port/service risk classification filter."},
                {"name": "Date From / Date To", "details": "Time-bounds result review windows."},
                {"name": "Actions", "details": "Open, Compare, Re-run, and Export based on capability."},
            ],
            "examples": [
                "Post-release validation: filter by Target + Date From and compare against previous baseline.",
                "Threat hunt: filter Service Detected=ssh and Risk Level=high for fast triage.",
            ],
            "best_practices": [
                "Validate suspicious findings with raw output before escalation.",
                "Use comparison mode for change-driven investigations rather than ad hoc guesswork.",
                "Review host-down results alongside execution logs to separate network issues from host outages.",
            ],
            "warnings": [
                "Do not assume low-risk labels eliminate business impact; verify service context.",
            ],
        },
        {
            "id": "history",
            "title": "History",
            "icon": "history",
            "what_is": (
                "History is the long-term execution ledger for completed, active, and archived runs."
            ),
            "why_used": [
                "Preserves operational traceability for audits and incident post-analysis.",
                "Enables trend review and replay operations such as clone/re-run workflows.",
                "Supports lifecycle management through archive, restore, and controlled delete actions.",
            ],
            "how_to_use": [
                "Choose the correct tab: All History, My History, or Archived.",
                "Apply filters for Search, Status, Target, Profile, User (when available), and date range.",
                "Use row actions for Monitor/Result, Re-run, Clone, Compare, or Archive based on state and role.",
                "Use Archived tab for restore/delete lifecycle tasks where authorized.",
            ],
            "fields": [
                {"name": "Page Mode Tabs", "details": "All History, My History, and Archived context selection."},
                {"name": "Status", "details": "Execution state filter for lifecycle analysis."},
                {"name": "Target", "details": "Target-specific historical analysis."},
                {"name": "Profile", "details": "Profile-level historical behavior and policy traceability."},
                {"name": "User", "details": "Requested-by filter for multi-operator reviews."},
                {"name": "Archived", "details": "Indicates whether a record is in archived lifecycle state."},
                {"name": "Actions", "details": "Re-run, Clone, Compare, Archive, Restore, Delete as permitted."},
            ],
            "examples": [
                "Quarterly audit: pull Archived records for retention and compliance checks.",
                "Change impact study: use Compare across historical executions on the same target.",
            ],
            "best_practices": [
                "Prefer archive over delete for audit-safe retention when policy requires traceability.",
                "Use clone for repeatability when recreating prior scan conditions.",
            ],
            "warnings": [
                "Delete actions are irreversible and should follow approval policy.",
            ],
        },
        {
            "id": "reports",
            "title": "Reports",
            "icon": "description",
            "what_is": (
                "Reports provides governed generation, review, and export of operational and executive reporting."
            ),
            "why_used": [
                "Converts scan and asset evidence into stakeholder-ready formats.",
                "Improves communication between technical teams and decision makers.",
                "Supports compliance, audit narratives, and remediation planning artifacts.",
            ],
            "how_to_use": [
                "Open Reports to review previously generated documents with filters.",
                "Use Generate Report to choose source type and report type.",
                "Select source records, include sections, add summary notes, and generate output.",
                "Preview details, then Download or Print for distribution.",
            ],
            "fields": [
                {"name": "Report Title", "details": "Custom title; system can auto-generate when left blank."},
                {"name": "Source Type", "details": "Scan Result, Scan Execution, Comparison, or Asset."},
                {"name": "Report Type", "details": "Executive Summary, Technical Report, Comparison Report, Per-Host Report."},
                {"name": "Output Format", "details": "HTML, PDF, JSON, or TXT."},
                {"name": "Source Result", "details": "Required when Source Type is Scan Result."},
                {"name": "Source Execution", "details": "Required when Source Type is Scan Execution."},
                {"name": "Comparison Baseline", "details": "Left-side result used as historical baseline."},
                {"name": "Comparison Current", "details": "Right-side result used as current comparison target."},
                {"name": "Asset", "details": "Required when Source Type is Asset."},
                {"name": "Include Sections", "details": "Summary, Ports, Services, Findings, Timeline toggles."},
                {"name": "Summary Notes", "details": "Narrative context for business and audit consumers."},
                {"name": "List Filters", "details": "Search, Type, Format, Status, Generated By, From, To."},
            ],
            "examples": [
                "Executive weekly update: Executive Summary in PDF with Summary + Findings sections.",
                "Technical diff review: Comparison Report between baseline and current result snapshots.",
            ],
            "best_practices": [
                "Use consistent naming conventions for report titles (system, scope, date).",
                "Keep Summary Notes concise and action-oriented for faster stakeholder review.",
                "Verify source objects belong to the intended environment before publishing output.",
            ],
            "warnings": [
                "Comparison reports require two distinct results; selecting the same result is invalid.",
            ],
        },
        {
            "id": "schedule",
            "title": "Schedule",
            "icon": "calendar_clock",
            "what_is": (
                "Schedule manages recurring scan orchestration for continuous security monitoring."
            ),
            "why_used": [
                "Automates repeatable scan operations without manual request creation each cycle.",
                "Supports predictable monitoring cadence for critical systems and environments.",
                "Creates execution history for recurring controls and audit evidence.",
            ],
            "how_to_use": [
                "Open Schedule and review Active, Paused, and Due Soon summary cards.",
                "Create a schedule and define frequency, timing window, and scan options.",
                "Use Run Now for immediate execution, or toggle enable state for lifecycle control.",
                "Review Schedule History for triggered run status and linked reports.",
            ],
            "fields": [
                {"name": "Schedule Name", "details": "Human-readable identifier for recurring job intent."},
                {"name": "Target", "details": "Target to be scanned on each scheduled run."},
                {"name": "Profile", "details": "Optional profile to standardize recurring scan behavior."},
                {"name": "Scan Type", "details": "Host Discovery, Quick TCP, Top 100, Top 1000, Service Detection, or Safe Basic."},
                {"name": "Timing Profile", "details": "Normal, Balanced, or Fast runtime behavior control."},
                {"name": "Frequency", "details": "One Time, Daily, Weekly, Monthly, or Custom."},
                {"name": "Port Scope", "details": "Ports/ranges to probe per scheduled execution."},
                {"name": "Custom Recurrence Rule", "details": "Required in Custom frequency mode."},
                {"name": "Start At / End At", "details": "Execution window boundaries for schedule validity."},
                {"name": "Host Discovery", "details": "Reachability check before deeper probes."},
                {"name": "Service Detection", "details": "Service fingerprinting toggle."},
                {"name": "Version Detection", "details": "Version fingerprinting toggle."},
                {"name": "OS Detection", "details": "Operating system inference toggle."},
                {"name": "Traceroute", "details": "Path analysis toggle."},
                {"name": "DNS Resolution", "details": "Hostname resolution toggle."},
                {"name": "Enabled", "details": "Controls whether the schedule is active for trigger processing."},
                {"name": "Notify on Run", "details": "Emits notification events for schedule-triggered executions."},
                {"name": "List Filters", "details": "Search, Frequency, State, Owner, Next Run From, Next Run To."},
            ],
            "examples": [
                "Daily perimeter check at off-peak hours with Balanced timing and targeted Port Scope.",
                "Weekly service baseline collection with Notify on Run enabled for SOC visibility.",
            ],
            "best_practices": [
                "Name schedules with environment + objective + cadence.",
                "Use conservative timing for large network ranges to reduce scan pressure.",
                "Review Due Soon and Schedule History regularly to catch missed or failed triggers.",
            ],
            "warnings": [
                "Custom recurrence rules can create high-frequency runs if configured incorrectly.",
                "Large scope plus deep detection toggles can increase queue load during peak windows.",
            ],
        },
        {
            "id": "notifications",
            "title": "Notifications",
            "icon": "notifications",
            "what_is": (
                "Notifications is the operational alert inbox for scan, schedule, report, policy, asset, and system events."
            ),
            "why_used": [
                "Reduces missed events by centralizing action-required alerts.",
                "Provides direct links to related execution, result, schedule, report, and asset records.",
                "Supports workload triage using severity and read state.",
            ],
            "how_to_use": [
                "Review summary cards for Total, Unread, and Critical Unread.",
                "Filter by Read State, Type, Severity, and date range.",
                "Open detail view to inspect context and related objects.",
                "Use Mark Read/Unread actions to keep the queue operationally clean.",
            ],
            "fields": [
                {"name": "Search", "details": "Matches notification title, message, execution ID, or related asset name."},
                {"name": "Read State", "details": "All, Unread, or Read filter."},
                {"name": "Type", "details": "Scan Completed, Scan Failed, Schedule Triggered, Report Generated, Asset Changed, Policy Alert, System Alert."},
                {"name": "Severity", "details": "Info, Success, Warning, or Error."},
                {"name": "From / To", "details": "Date range filters for alert timeline review."},
                {"name": "Detail Fields", "details": "Title, message, type badge, severity badge, read state, related links, and activity timeline."},
            ],
            "examples": [
                "Filter Severity=Error + Unread to prioritize high-impact failures first.",
                "Open schedule-triggered alerts to validate recurring job outcomes.",
            ],
            "best_practices": [
                "Process unread critical alerts first during each shift.",
                "Mark notifications after investigation to keep handoff clean.",
            ],
            "warnings": [
                "Ignoring unread policy or system alerts can hide control drift and runtime degradation.",
            ],
        },
        {
            "id": "assets",
            "title": "Assets",
            "icon": "inventory_2",
            "what_is": (
                "Assets is the discovered infrastructure inventory built from scan results and change telemetry."
            ),
            "why_used": [
                "Creates a living asset inventory tied directly to technical evidence.",
                "Enables risk-driven prioritization through risk level, risk score, and service exposure.",
                "Tracks longitudinal change through snapshots and asset change logs.",
            ],
            "how_to_use": [
                "Use list filters to isolate target networks, owners, risk level, and status.",
                "Open an asset to review risk posture, ports, services, and linked scan history.",
                "Switch tabs (Overview, Snapshots, Change History, Related Results, Notes) for deep investigation.",
                "Use Sync from Results to refresh inventory from latest findings where permitted.",
            ],
            "fields": [
                {"name": "Search", "details": "Find by asset name, IP, or hostname."},
                {"name": "Target", "details": "Limit inventory to a network/target context."},
                {"name": "Owner", "details": "Owner/team metadata filter via owner_name."},
                {"name": "Risk Level", "details": "Info, Low, Medium, High, Critical classification filter."},
                {"name": "Status", "details": "Active, Inactive, Monitoring, Archived lifecycle state."},
                {"name": "Last Seen From / To", "details": "Temporal filter for asset recency tracking."},
                {"name": "Detail Metrics", "details": "Risk Score, Risk Level, Status, Open Ports, Last Scanned."},
                {"name": "Detail Tabs", "details": "Overview, Snapshots, Change History, Related Results, Notes."},
                {"name": "Change Types", "details": "Ports Added, Ports Removed, Service Changed, OS Changed, Asset Created, Asset Updated."},
            ],
            "examples": [
                "Identify stale exposure: Status=Monitoring with old Last Seen dates for verification.",
                "Investigate service drift: open Change History for recent Service Changed events.",
            ],
            "best_practices": [
                "Review high and critical risk assets first each cycle.",
                "Validate ownership fields for accountability and routing.",
                "Correlate Related Results before opening remediation tickets.",
            ],
            "warnings": [
                "Asset data reflects scan observations; unknown services still need manual validation.",
            ],
        },
        {
            "id": "user-logs-analytics",
            "title": "User Logs Analytics",
            "icon": "query_stats",
            "what_is": (
                "User Logs Analytics is the Super Admin audit dashboard for authentication events, "
                "access activity, and admin action telemetry from stored user logs."
            ),
            "why_used": [
                "Provides centralized visibility into login success/failure and user action behavior.",
                "Supports incident triage with filters across user, action, result, IP, and path.",
                "Helps governance teams identify anomalous usage patterns and high-risk activity.",
            ],
            "how_to_use": [
                "Open User Logs Analytics from the sidebar (Super Admin only).",
                "Apply Period and optional custom Start/End dates, then refine with username/action/result/IP/path filters.",
                "Review summary cards, daily trend, top users/actions/IPs, and recent logs.",
                "Use pagination in Recent Logs for deeper event review.",
            ],
            "fields": [
                {"name": "Period", "details": "Today, Yesterday, This Week, This Month, This Year, or Custom date range."},
                {"name": "Username", "details": "Matches username snapshot and user email/username fields."},
                {"name": "Action Type", "details": "Filters login, logout, failed login, and admin action categories."},
                {"name": "Result", "details": "Success or Failed outcome filter."},
                {"name": "IP / Path", "details": "Substring filters for IP address and request path."},
                {"name": "Summary Metrics", "details": "Total logs, time-window counts, success/failure, unique users/IPs, login/logout."},
                {"name": "Daily Trend", "details": "Day-level totals with success/failure split for charting and review."},
                {"name": "Recent Logs", "details": "Timestamp, actor, action, result, IP, path, description, and browser/agent context."},
            ],
            "examples": [
                "Investigate brute-force behavior by filtering Result=Failed and IP contains suspected source.",
                "Audit privileged changes by filtering Action Type to admin create/update/delete actions.",
            ],
            "best_practices": [
                "Start with a broad period, then narrow with user/action/IP filters.",
                "Correlate repeated failures and unusual paths with system alerts before escalation.",
                "Use recent logs table details (path and browser/user-agent) for incident context.",
            ],
            "warnings": [
                "This module contains sensitive audit data and is restricted to Super Admin accounts only.",
            ],
        },
        {
            "id": "system-health",
            "title": "System Health",
            "icon": "monitor_heart",
            "what_is": (
                "System Health is the platform reliability console for core dependencies and worker runtime."
            ),
            "why_used": [
                "Detects service degradation before it impacts scan operations.",
                "Supports rapid root-cause analysis for queue delays and failed execution spikes.",
                "Provides auditable health snapshots for operational governance.",
            ],
            "how_to_use": [
                "Open System Health and review Overall Status first.",
                "Inspect service cards and alerts for Database, Queue, Scheduler, Storage, and tooling checks.",
                "Use Queue & Workers to inspect worker fleet state and job backlog.",
                "Review timeline to confirm whether issues are persistent or transient.",
            ],
            "fields": [
                {"name": "Overall Status", "details": "Roll-up health state derived from service check severity."},
                {"name": "Service Cards", "details": "Django App, Database, Nmap Binary, Queue Service, Scheduler, Storage."},
                {"name": "Alerts", "details": "Warning/Error snapshots auto-refreshed for recent anomalies."},
                {"name": "Recent Health Timeline", "details": "Service, status, summary, and checked_at history rows."},
                {"name": "Worker Summary", "details": "Total Workers, Online, Degraded, Offline, Active Jobs, Queue Backlog, Failed Jobs."},
                {"name": "Worker Status", "details": "Per-worker heartbeat, active jobs, queued jobs, failed jobs, and derived runtime status."},
            ],
            "examples": [
                "If queue backlog rises while workers show degraded/offline, escalate runtime capacity review.",
                "If scheduler is warning with overdue runs, verify schedule trigger pipeline and worker health.",
            ],
            "best_practices": [
                "Check System Health before diagnosing scan-level failures.",
                "Correlate health anomalies with execution failure windows in Running/History.",
                "Use timeline history in post-incident reports.",
            ],
            "warnings": [
                "Ignoring repeated warning states can lead to silent operational failure over time.",
            ],
        },
    ]

    return {
        "page": {
            "title": "ScanOps Documentation",
            "subtitle": (
                "Enterprise operational guide for ScanOps modules, field-level controls, and secure usage patterns."
            ),
            "authorized_notice": (
                "ScanOps is for authorized internal security operations only. "
                "Use of this platform outside approved scope is prohibited."
            ),
        },
        "getting_started_steps": [
            "Access ScanOps via /login/ and review this documentation before first use.",
            "Sign in with an approved role and verify your sidebar module access.",
            "Create or confirm target inventory, then submit a controlled New Scan request.",
            "Monitor runtime in Running and Scan Queue, then review Results and History.",
            "Generate Reports for stakeholders and configure Schedule for recurring controls.",
        ],
        "security_access_points": [
            "Role-based access control governs module capabilities and action buttons.",
            "User-owned data isolation limits private records to their owners.",
            "Scoped users cannot access other users' private targets, scans, results, reports, schedules, notifications, or assets.",
            "Administrative roles can have broader operational visibility based on policy.",
            "All scans must remain within approved authorization boundaries.",
        ],
        "recommended_workflow": [
            "Login and validate your operational scope.",
            "Add/select authorized targets.",
            "Create New Scan request with safe defaults.",
            "Observe Running and Queue states until completion.",
            "Analyze Results and compare with History.",
            "Generate and distribute Reports.",
            "Create recurring Schedule entries for ongoing monitoring.",
        ],
        "global_best_practices": [
            "Prefer conservative scan configurations before deep fingerprinting in production.",
            "Capture meaningful Notes and report summaries for audit readiness.",
            "Investigate failed or degraded runtime indicators before increasing scan load.",
            "Use comparative analysis to identify true change instead of one-off anomalies.",
            "Only scan assets explicitly authorized by policy.",
        ],
        "support": {
            "title": "Support / Help",
            "content": (
                "For access issues, role changes, failed workflows, or platform anomalies, contact your "
                "ScanOps administrator or security operations lead. Include time window, module name, "
                "target scope, and execution/report IDs to accelerate triage. "
                "For product improvements use /feedback/suggestions/, and for defects or operational incidents "
                "use /feedback/issues/ with optional evidence attachments."
            ),
        },
        "modules": modules,
    }
