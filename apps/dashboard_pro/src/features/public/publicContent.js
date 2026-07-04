export const publicNavLinks = [
  { href: "#workflow", label: "Product Workflow" },
  { href: "#studio", label: "Studio" },
  { href: "#security", label: "Security" },
];

export const heroMetrics = [
  { label: "Canon records", value: "24k" },
  { label: "Pipeline stages", value: "9" },
  { label: "Provider checks", value: "live" },
];

export const studioPreviewRows = [
  { label: "Import plan", detail: "validated", tone: "green" },
  { label: "Canon memory", detail: "scenes indexed", tone: "blue" },
  { label: "Visual assets", detail: "render queue ready", tone: "slate" },
  { label: "Audiobook run", detail: "chapters staged", tone: "green" },
];

export const workflowSteps = [
  {
    title: "Import and validate",
    body: "Stage source books, normalize metadata, and review execution settings before the pipeline starts.",
  },
  {
    title: "Analyze canon memory",
    body: "Inspect scenes, entities, events, relationships, timelines, and character state from the persisted store.",
  },
  {
    title: "Produce downstream assets",
    body: "Generate stories, manage visual prompts, render character assets, and prepare audiobook outputs.",
  },
];

export const capabilityGroups = [
  {
    title: "Operational dashboard",
    body: "Track jobs, logs, provider health, uploads, and database-backed artifacts from one focused command surface.",
  },
  {
    title: "Canon-aware generation",
    body: "Use structured memory to keep generated stories and visual assets grounded in the source material.",
  },
  {
    title: "Production handoff",
    body: "Export generated stories, review prompt versions, and stage audio chapters without leaving the studio.",
  },
];

export const trustItems = [
  "Local runtime by default",
  "MongoDB-backed account creation",
  "Provider status visibility",
  "Structured validation before long runs",
];
