import { AlertTriangle, CheckCircle2, CircleHelp } from "lucide-react";
import { redirect } from "next/navigation";

import {
  getSagaProjectIdentityEvidence,
  type SagaIdentityMention,
} from "@/server/story/identity-data";
import { SagaStoryOperationError } from "@/server/story/story-data";

function humanize(value: string) {
  return value.replaceAll("_", " ");
}

function mentionLabel(mention: SagaIdentityMention) {
  const locator = mention.structuralLocator ? ` · ${mention.structuralLocator}` : "";
  return `${mention.surfaceText} · ${humanize(mention.mentionKind)} · ${mention.startOffset}–${mention.endOffset}${locator}`;
}

export async function CharacterEvidenceSection({ projectId }: { projectId: string }) {
  let runs;
  try {
    runs = await getSagaProjectIdentityEvidence(projectId);
  } catch (error) {
    if (error instanceof SagaStoryOperationError && error.code === "unavailable") {
      redirect("/access/unavailable");
    }
    throw error;
  }

  return (
    <section className="max-w-6xl" aria-labelledby="characters-heading">
      <div className="border-b border-[var(--app-separator)] pb-4">
        <h2 id="characters-heading" className="text-base font-semibold text-[var(--app-text)]">
          Characters
        </h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--app-muted)]">
          Canonicals are admitted conservatively from strong character evidence. Ambiguous or rejected evidence remains visible instead of being promoted into identity truth.
        </p>
      </div>

      {runs.length === 0 ? (
        <p className="border-b border-[var(--app-separator)] py-8 text-sm leading-6 text-[var(--app-muted)]">
          No successful character identity run yet. A normalized source can queue identity work without changing the original story text.
        </p>
      ) : (
        <div className="divide-y divide-[var(--app-separator)] border-b border-[var(--app-separator)]">
          {runs.map((run) => (
            <article key={run.id} className="py-7">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
                <div>
                  <h3 className="text-sm font-semibold text-[var(--app-text)]">{run.sourceDisplayName}</h3>
                  <p className="mt-1 text-xs leading-5 text-[var(--app-muted)]">
                    {run.characters.length} canonical{run.characters.length === 1 ? "" : "s"} · {run.unresolvedMentions.length} unresolved · {run.quarantinedMentions.length} quarantined
                  </p>
                </div>
                <details className="text-xs text-[var(--app-muted)] sm:max-w-md sm:text-right">
                  <summary className="cursor-pointer font-semibold text-[var(--app-text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
                    Run provenance
                  </summary>
                  <p className="mt-2 leading-5">
                    Resolver {run.resolverVersion} · evidence {run.providerName}{run.providerModel ? ` / ${run.providerModel}` : ""} · revision {run.providerRevision}
                  </p>
                  <p className="mt-1 break-all font-mono text-[11px] leading-4">{run.outputFingerprint}</p>
                </details>
              </div>

              {run.characters.length === 0 ? (
                <p className="mt-6 text-sm leading-6 text-[var(--app-muted)]">
                  This run admitted no canonical characters. That can be a valid precision-first result.
                </p>
              ) : (
                <ul className="mt-6 divide-y divide-[var(--app-separator)] border-y border-[var(--app-separator)]">
                  {run.characters.map((character) => (
                    <li key={character.id} className="py-5">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="size-4 shrink-0 text-[var(--app-muted)]" aria-hidden="true" />
                            <h4 className="truncate text-sm font-semibold text-[var(--app-text)]">{character.canonicalName}</h4>
                          </div>
                          <p className="mt-2 text-xs leading-5 text-[var(--app-muted)]">
                            {humanize(character.admissionTier)} · {character.evidenceCount} linked evidence item{character.evidenceCount === 1 ? "" : "s"}
                          </p>
                          {character.aliases.length > 0 ? (
                            <p className="mt-2 text-sm leading-6 text-[var(--app-muted)]">
                              <span className="font-semibold text-[var(--app-text)]">Aliases:</span>{" "}
                              {character.aliases.map((alias) => alias.surfaceForm).join(", ")}
                            </p>
                          ) : null}
                        </div>
                      </div>

                      {character.mentions.length > 0 ? (
                        <details className="mt-4">
                          <summary className="cursor-pointer text-xs font-semibold text-[var(--app-text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]">
                            Representative linked mentions
                          </summary>
                          <ul className="mt-3 space-y-2 text-xs leading-5 text-[var(--app-muted)]">
                            {character.mentions.map((mention) => (
                              <li key={mention.id}>
                                {mentionLabel(mention)} · {humanize(mention.evidenceTier)}
                              </li>
                            ))}
                          </ul>
                        </details>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}

              {(run.unresolvedMentions.length > 0 || run.quarantinedMentions.length > 0) ? (
                <div className="mt-6 grid gap-5 lg:grid-cols-2">
                  <div>
                    <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.11em] text-[var(--app-muted)]">
                      <CircleHelp className="size-4" aria-hidden="true" /> Unresolved evidence
                    </h4>
                    {run.unresolvedMentions.length === 0 ? (
                      <p className="mt-3 text-xs text-[var(--app-muted)]">None in this run.</p>
                    ) : (
                      <ul className="mt-3 space-y-2 text-xs leading-5 text-[var(--app-muted)]">
                        {run.unresolvedMentions.slice(0, 8).map((mention) => (
                          <li key={mention.id}>{mentionLabel(mention)} · {humanize(mention.decisionReason)}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div>
                    <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.11em] text-[var(--app-muted)]">
                      <AlertTriangle className="size-4" aria-hidden="true" /> Quarantined evidence
                    </h4>
                    {run.quarantinedMentions.length === 0 ? (
                      <p className="mt-3 text-xs text-[var(--app-muted)]">None in this run.</p>
                    ) : (
                      <ul className="mt-3 space-y-2 text-xs leading-5 text-[var(--app-muted)]">
                        {run.quarantinedMentions.slice(0, 8).map((mention) => (
                          <li key={mention.id}>{mentionLabel(mention)} · {humanize(mention.decisionReason)}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
