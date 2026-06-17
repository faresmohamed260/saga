from typing import Dict


class CausalGraphMetrics:
    """
    Computes summary metrics for a validated causal graph.
    """

    def compute(self, graph: Dict) -> Dict:
        events = graph.get("events", [])
        total_links = sum(len(event.get("causes", [])) + len(event.get("caused_by", [])) for event in events)

        return {
            "total_events": len(events),
            "total_links": total_links,
            "avg_links_per_event": round(total_links / len(events), 2) if events else 0,
            "critical_path_length": len(graph.get("critical_path", [])),
            "causal_chain_count": len(graph.get("causal_chains", [])),
            "divergence_count": len(graph.get("divergence_points", [])),
            "flexible_event_count": len(graph.get("flexible_events", [])),
        }
