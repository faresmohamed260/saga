import { EmptyState, Panel } from "../primitives";
import { GeneratedStoryCard } from "./GeneratedStoryCard";

export function GeneratedStoriesPanel({ stories }) {
  return (
    <Panel title="Generated Stories" subtitle="Persisted stories and export links.">
      {stories.length ? (
        <div className="space-y-3">
          {stories.map((story) => (
            <GeneratedStoryCard key={story.id} story={story} />
          ))}
        </div>
      ) : (
        <EmptyState title="No generated stories" />
      )}
    </Panel>
  );
}
