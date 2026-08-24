from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "apps/studio/api/generate.js"
text = PATH.read_text(encoding="utf-8")

old_import = '''import {\n  createGenerationJob,\n  setProviderJobId,\n  transitionGenerationJob,\n} from './_generation-jobs.js';\n'''
new_import = '''import {\n  createGenerationJob,\n  transitionGenerationJob,\n  updateGenerationWorkerAssignment,\n} from './_generation-jobs.js';\n'''
if old_import in text:
    text = text.replace(old_import, new_import, 1)
elif new_import not in text:
    raise SystemExit("Generation job import fragment not found")

old_assignment = '''    const updatedJob = await setProviderJobId(job.id, submitted.providerJobId);\n'''
new_assignment = '''    const submissionFailures = Array.isArray(submitted.worker?.failedWorkers) ? submitted.worker.failedWorkers : [];\n    const submittedAt = new Date().toISOString();\n    const updatedJob = await updateGenerationWorkerAssignment(job.id, submitted.providerJobId, {\n      assignedWorkerId: submitted.worker?.workerId || null,\n      workerFailoverHistory: submissionFailures.map((failure) => ({\n        fromWorkerId: failure.workerId || null,\n        reason: failure.kind || 'unavailable',\n        errorCode: failure.code || null,\n        at: submittedAt,\n      })),\n    });\n'''
if old_assignment in text:
    text = text.replace(old_assignment, new_assignment, 1)
elif new_assignment not in text:
    raise SystemExit("Provider assignment fragment not found")

PATH.write_text(text, encoding="utf-8")
print("Initial worker assignment metadata patch applied.")
